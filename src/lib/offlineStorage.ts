/**
 * Pocket Offline Cache (docs/ideas/mobile-offline-reader.md, fase 2).
 *
 * Menyimpan bab terjemahan di IndexedDB browser HP supaya tetap bisa dibaca saat
 * laptop/server tidak terjangkau. Tanpa dependensi tambahan (IndexedDB mentah).
 *
 * Isolasi workspace (CLAUDE.md invariant #3): nama database dibungkus
 * getWorkspaceStorageKey(), jadi data `main` dan `ghost` tidak pernah bercampur.
 */
import { getActiveWorkspace, getApiUrl, getWorkspaceStorageKey } from "@/lib/api";
import type { ChapterContent, ThreadDetail } from "@/components/reader/types";

const DB_VERSION = 1;
const CHAPTER_STORE = "chapters";
const THREAD_STORE = "threads";

export const DEFAULT_OFFLINE_CHAPTER_COUNT = 20;

interface StoredChapter {
  key: string;
  threadId: number;
  chapterId: number;
  savedAt: number;
  bytes: number;
  content: ChapterContent;
}

interface StoredThread {
  threadId: number;
  savedAt: number;
  thread: ThreadDetail;
}

export interface OfflineStats {
  chapters: number;
  threads: number;
  bytes: number;
}

const DB_BASE_NAME = "readomni_offline_v1";

/**
 * Nama database untuk workspace aktif, atau untuk `workspace` yang diberikan eksplisit
 * (dipakai proses panjang seperti cacheChaptersAhead agar tidak berpindah workspace di tengah jalan).
 * Formatnya sama dengan getWorkspaceStorageKey(): `${base}_${workspace}`.
 */
export function getOfflineDbName(workspace?: string): string {
  return workspace ? `${DB_BASE_NAME}_${workspace}` : getWorkspaceStorageKey(DB_BASE_NAME);
}

export function isOfflineCacheSupported(): boolean {
  try {
    return typeof indexedDB !== "undefined" && indexedDB !== null;
  } catch {
    return false;
  }
}

/**
 * Status dari proxy (Vite / launcher) saat backend tidak terjangkau. Dianggap sama dengan
 * gagal jaringan; error HTTP lain (404, 500) berasal dari backend yang hidup.
 */
export function isServerUnreachableStatus(status: number): boolean {
  return status === 502 || status === 503 || status === 504;
}

function chapterKey(threadId: number, chapterId: number): string {
  return `${threadId}_${chapterId}`;
}

function promisify<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function txDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    // On a request-level error tx.error is still null while the event bubbles; use the request's error
    tx.onerror = (ev) =>
      reject(
        tx.error ??
          (ev.target as IDBRequest | null)?.error ??
          new DOMException("IndexedDB transaction failed", "UnknownError")
      );
    tx.onabort = () =>
      reject(tx.error ?? new DOMException("IndexedDB transaction aborted", "AbortError"));
  });
}

function isQuotaError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "QuotaExceededError";
}

function openDb(workspace?: string): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!isOfflineCacheSupported()) {
      reject(new Error("IndexedDB tidak tersedia di browser ini"));
      return;
    }
    const req = indexedDB.open(getOfflineDbName(workspace), DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(CHAPTER_STORE)) {
        const store = db.createObjectStore(CHAPTER_STORE, { keyPath: "key" });
        store.createIndex("threadId", "threadId", { unique: false });
      }
      if (!db.objectStoreNames.contains(THREAD_STORE)) {
        db.createObjectStore(THREAD_STORE, { keyPath: "threadId" });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withDb<T>(
  fn: (db: IDBDatabase) => Promise<T>,
  workspace?: string
): Promise<T> {
  const db = await openDb(workspace);
  try {
    return await fn(db);
  } finally {
    db.close();
  }
}

/**
 * Pilih bab yang akan disimpan: mulai dari `startIndex`, hanya bab yang sudah
 * diterjemahkan. Bab tanpa terjemahan dilewati karena GET bab kosong bisa memicu
 * scraping on-demand di server.
 */
export function selectChaptersToCache(
  thread: ThreadDetail,
  startIndex: number,
  count: number
): ThreadDetail["chapters"] {
  const from = Math.max(0, startIndex);
  return thread.chapters
    .slice(from)
    .filter((ch) => ch.has_translation)
    .slice(0, Math.max(0, count));
}

export async function saveOfflineThread(thread: ThreadDetail, workspace?: string): Promise<void> {
  await withDb(async (db) => {
    const tx = db.transaction(THREAD_STORE, "readwrite");
    const record: StoredThread = { threadId: thread.id, savedAt: Date.now(), thread };
    tx.objectStore(THREAD_STORE).put(record);
    await txDone(tx);
  }, workspace);
}

export async function getOfflineThread(threadId: number): Promise<ThreadDetail | null> {
  try {
    return await withDb(async (db) => {
      const tx = db.transaction(THREAD_STORE, "readonly");
      const rec = (await promisify(tx.objectStore(THREAD_STORE).get(threadId))) as
        | StoredThread
        | undefined;
      return rec ? rec.thread : null;
    });
  } catch {
    return null;
  }
}

export async function saveOfflineChapter(
  threadId: number,
  content: ChapterContent,
  workspace?: string
): Promise<void> {
  const json = JSON.stringify(content);
  await withDb(async (db) => {
    const tx = db.transaction(CHAPTER_STORE, "readwrite");
    const record: StoredChapter = {
      key: chapterKey(threadId, content.id),
      threadId,
      chapterId: content.id,
      savedAt: Date.now(),
      bytes: json.length * 2,
      content,
    };
    tx.objectStore(CHAPTER_STORE).put(record);
    await txDone(tx);
  }, workspace);
}

export async function getOfflineChapter(
  threadId: number,
  chapterId: number
): Promise<ChapterContent | null> {
  try {
    return await withDb(async (db) => {
      const tx = db.transaction(CHAPTER_STORE, "readonly");
      const rec = (await promisify(
        tx.objectStore(CHAPTER_STORE).get(chapterKey(threadId, chapterId))
      )) as StoredChapter | undefined;
      return rec ? rec.content : null;
    });
  } catch {
    return null;
  }
}

export async function getOfflineChapterIds(threadId: number): Promise<Set<number>> {
  try {
    return await withDb(async (db) => {
      const tx = db.transaction(CHAPTER_STORE, "readonly");
      const index = tx.objectStore(CHAPTER_STORE).index("threadId");
      // Keys only (`${threadId}_${chapterId}`): avoids deserializing every chapter body
      const keys = (await promisify(index.getAllKeys(threadId))) as IDBValidKey[];
      return new Set(keys.map((k) => Number(String(k).split("_")[1])));
    });
  } catch {
    return new Set();
  }
}

/**
 * Perbarui salinan offline bila bab ini memang sudah pernah disimpan. Respons tanpa
 * terjemahan (mis. sedang diterjemahkan ulang) tidak boleh menimpa salinan yang bagus.
 */
export async function refreshOfflineChapterIfCached(
  threadId: number,
  content: ChapterContent
): Promise<void> {
  if (!isUsableTranslation(content)) return;
  try {
    const existing = await getOfflineChapter(threadId, content.id);
    if (existing) await saveOfflineChapter(threadId, content);
  } catch {
    /* best effort */
  }
}

function isUsableTranslation(content: ChapterContent): boolean {
  return Boolean(content.content_translated?.trim()) && content.translation_status !== "processing";
}

/**
 * Selaraskan snapshot daftar bab saat server terjangkau. Bila `created_at` berbeda, ID novel ini
 * sudah dipakai ulang oleh novel lain (SQLite tanpa AUTOINCREMENT) sehingga cache lama dibuang.
 * Judul sengaja tidak dipakai: rename, "Translate titles", dan scrape metadata mengubahnya secara sah.
 */
export async function refreshOfflineThreadIfCached(thread: ThreadDetail): Promise<void> {
  try {
    const existing = await getOfflineThread(thread.id);
    if (!existing) return;
    if (existing.created_at && thread.created_at && existing.created_at !== thread.created_at) {
      await clearOfflineThread(thread.id);
      return;
    }
    if (JSON.stringify(existing) !== JSON.stringify(thread)) await saveOfflineThread(thread);
  } catch {
    /* best effort */
  }
}

export interface CacheAheadResult {
  saved: number;
  failed: number;
  requested: number;
}

/**
 * Unduh dan simpan `count` bab terjemahan mulai dari `startIndex`, plus snapshot
 * daftar bab (agar daftar isi tetap tampil saat offline).
 */
export async function cacheChaptersAhead(
  thread: ThreadDetail,
  startIndex: number,
  count: number,
  onProgress?: (done: number, total: number) => void
): Promise<CacheAheadResult> {
  // Workspace tab ini (dikunci saat halaman dimuat, lihat api.ts); dipakai eksplisit untuk fetch & IndexedDB
  const workspace = getActiveWorkspace();
  const targets = selectChaptersToCache(thread, startIndex, count);
  await saveOfflineThread(thread, workspace);
  // Minta penyimpanan persisten agar browser (terutama Safari iOS) tidak menghapusnya diam-diam
  try {
    await navigator.storage?.persist?.();
  } catch {
    /* best effort */
  }

  let saved = 0;
  let failed = 0;
  for (let i = 0; i < targets.length; i++) {
    const ch = targets[i];
    try {
      // track=0: unduhan massal tidak boleh memindahkan posisi baca atau memicu prefetch di server
      const res = await fetch(
        getApiUrl(`/api/threads/${thread.id}/chapters/${ch.id}?track=0`),
        { headers: { "X-Workspace": workspace } }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ChapterContent = await res.json();
      // Jangan simpan bab yang terjemahannya kosong/sedang diproses (mis. setelah fix-truncated)
      if (!isUsableTranslation(data)) throw new Error("No usable translation");
      await saveOfflineChapter(thread.id, data, workspace);
      saved++;
    } catch (err) {
      if (isQuotaError(err)) {
        // Penyimpanan perangkat penuh: bab sisanya pasti gagal juga
        failed += targets.length - i;
        onProgress?.(targets.length, targets.length);
        break;
      }
      failed++;
    }
    onProgress?.(i + 1, targets.length);
  }
  return { saved, failed, requested: targets.length };
}

export async function clearOfflineThread(threadId: number): Promise<number> {
  return withDb(async (db) => {
    const tx = db.transaction([CHAPTER_STORE, THREAD_STORE], "readwrite");
    const index = tx.objectStore(CHAPTER_STORE).index("threadId");
    const keys = (await promisify(index.getAllKeys(threadId))) as IDBValidKey[];
    keys.forEach((k) => tx.objectStore(CHAPTER_STORE).delete(k));
    tx.objectStore(THREAD_STORE).delete(threadId);
    await txDone(tx);
    return keys.length;
  });
}

/** Hapus seluruh cache offline untuk workspace aktif. */
export async function clearAllOffline(): Promise<void> {
  await withDb(async (db) => {
    const tx = db.transaction([CHAPTER_STORE, THREAD_STORE], "readwrite");
    tx.objectStore(CHAPTER_STORE).clear();
    tx.objectStore(THREAD_STORE).clear();
    await txDone(tx);
  });
}

export async function getOfflineStats(): Promise<OfflineStats> {
  try {
    return await withDb(async (db) => {
      const tx = db.transaction([CHAPTER_STORE, THREAD_STORE], "readonly");
      const chapters = (await promisify(
        tx.objectStore(CHAPTER_STORE).getAll()
      )) as StoredChapter[];
      const threads = await promisify(tx.objectStore(THREAD_STORE).count());
      return {
        chapters: chapters.length,
        threads,
        bytes: chapters.reduce((sum, c) => sum + (c.bytes || 0), 0),
      };
    });
  } catch {
    return { chapters: 0, threads: 0, bytes: 0 };
  }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
