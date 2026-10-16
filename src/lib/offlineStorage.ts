/**
 * Pocket Offline Cache (docs/ideas/mobile-offline-reader.md, fase 2).
 *
 * Menyimpan bab terjemahan di IndexedDB browser HP supaya tetap bisa dibaca saat
 * laptop/server tidak terjangkau. Tanpa dependensi tambahan (IndexedDB mentah).
 *
 * Isolasi workspace (CLAUDE.md invariant #3): nama database dibungkus
 * getWorkspaceStorageKey(), jadi data `main` dan `ghost` tidak pernah bercampur.
 */
import { getApiUrl, getWorkspaceStorageKey } from "@/lib/api";
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

export function getOfflineDbName(): string {
  return getWorkspaceStorageKey("readomni_offline_v1");
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
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!isOfflineCacheSupported()) {
      reject(new Error("IndexedDB tidak tersedia di browser ini"));
      return;
    }
    const req = indexedDB.open(getOfflineDbName(), DB_VERSION);
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

async function withDb<T>(fn: (db: IDBDatabase) => Promise<T>): Promise<T> {
  const db = await openDb();
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

export async function saveOfflineThread(thread: ThreadDetail): Promise<void> {
  await withDb(async (db) => {
    const tx = db.transaction(THREAD_STORE, "readwrite");
    const record: StoredThread = { threadId: thread.id, savedAt: Date.now(), thread };
    tx.objectStore(THREAD_STORE).put(record);
    await txDone(tx);
  });
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
  content: ChapterContent
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
  });
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
      const recs = (await promisify(index.getAll(threadId))) as StoredChapter[];
      return new Set(recs.map((r) => r.chapterId));
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
  if (!content.content_translated?.trim() || content.translation_status === "processing") return;
  try {
    const existing = await getOfflineChapter(threadId, content.id);
    if (existing) await saveOfflineChapter(threadId, content);
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
  const targets = selectChaptersToCache(thread, startIndex, count);
  await saveOfflineThread(thread);
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
        getApiUrl(`/api/threads/${thread.id}/chapters/${ch.id}?track=0`)
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ChapterContent = await res.json();
      await saveOfflineChapter(thread.id, data);
      saved++;
    } catch (err) {
      if (err instanceof DOMException && err.name === "QuotaExceededError") {
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
