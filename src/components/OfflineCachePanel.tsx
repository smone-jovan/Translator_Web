import { useEffect, useState } from "react";
import { Download, Trash2, WifiOff } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useConfirm } from "@/hooks/use-confirm";
import type { ThreadDetail } from "@/components/reader/types";
import {
  DEFAULT_OFFLINE_CHAPTER_COUNT,
  cacheChaptersAhead,
  clearAllOffline,
  clearOfflineThread,
  formatBytes,
  getOfflineChapterIds,
  getOfflineStats,
  isOfflineCacheSupported,
  selectChaptersToCache,
  type OfflineStats,
} from "@/lib/offlineStorage";

const COUNT_OPTIONS = [10, 20, 50];

interface OfflineCachePanelProps {
  /** Mode reader: simpan/hapus bab novel ini. Tanpa thread: ringkasan + hapus semua. */
  thread?: ThreadDetail | null;
  /** Indeks bab yang sedang dibaca; penyimpanan dimulai dari bab ini. */
  currentIndex?: number | null;
  compact?: boolean;
}

export default function OfflineCachePanel({
  thread,
  currentIndex,
  compact = false,
}: OfflineCachePanelProps) {
  const { confirm } = useConfirm();
  const supported = isOfflineCacheSupported();
  const [count, setCount] = useState(DEFAULT_OFFLINE_CHAPTER_COUNT);
  const [threadCached, setThreadCached] = useState(0);
  const [stats, setStats] = useState<OfflineStats>({ chapters: 0, threads: 0, bytes: 0 });
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [reloadTick, setReloadTick] = useState(0);

  const refresh = () => setReloadTick((t) => t + 1);
  const threadId = thread?.id;

  useEffect(() => {
    if (!supported) return;
    let cancelled = false;
    (async () => {
      const nextStats = await getOfflineStats();
      const nextThreadCached =
        threadId !== undefined ? (await getOfflineChapterIds(threadId)).size : 0;
      if (cancelled) return;
      setStats(nextStats);
      setThreadCached(nextThreadCached);
    })();
    return () => {
      cancelled = true;
    };
  }, [supported, threadId, reloadTick]);

  if (!supported) {
    return (
      <p className="text-[10px] text-[var(--muted-foreground)]">
        Browser ini tidak mendukung penyimpanan offline (IndexedDB).
      </p>
    );
  }

  const startIndex = currentIndex ?? 0;
  const available = thread ? selectChaptersToCache(thread, startIndex, count).length : 0;

  const handleSave = async () => {
    if (!thread || busy) return;
    if (available === 0) {
      toast.info("Tidak ada bab terjemahan setelah posisi ini untuk disimpan.");
      return;
    }
    setBusy(true);
    setProgress({ done: 0, total: available });
    try {
      const res = await cacheChaptersAhead(thread, startIndex, count, (done, total) =>
        setProgress({ done, total })
      );
      if (res.failed > 0) {
        toast.warning(`${res.saved} bab tersimpan offline, ${res.failed} gagal.`);
      } else {
        toast.success(`${res.saved} bab tersimpan untuk dibaca offline.`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Gagal menyimpan bab offline");
    } finally {
      setBusy(false);
      setProgress(null);
      refresh();
    }
  };

  const handleClearThread = async () => {
    if (!thread || busy) return;
    const ok = await confirm({
      title: "Hapus cache offline novel ini?",
      description: `${threadCached} bab tersimpan di perangkat ini akan dihapus. Data di server tidak terpengaruh.`,
      confirmText: "Hapus",
      variant: "destructive",
    });
    if (!ok) return;
    setBusy(true);
    try {
      const removed = await clearOfflineThread(thread.id);
      toast.success(`${removed} bab offline dihapus.`);
    } catch {
      toast.error("Gagal menghapus cache offline");
    } finally {
      setBusy(false);
      refresh();
    }
  };

  const handleClearAll = async () => {
    if (busy) return;
    const ok = await confirm({
      title: "Hapus semua cache offline?",
      description: `${stats.chapters} bab (${formatBytes(stats.bytes)}) dari ${stats.threads} novel akan dihapus dari perangkat ini. Data di server tidak terpengaruh.`,
      confirmText: "Hapus semua",
      variant: "destructive",
    });
    if (!ok) return;
    setBusy(true);
    try {
      await clearAllOffline();
      toast.success("Semua cache offline dihapus.");
    } catch {
      toast.error("Gagal menghapus cache offline");
    } finally {
      setBusy(false);
      refresh();
    }
  };

  return (
    <div className={cn("space-y-3", compact && "space-y-2")}>
      <div className="flex items-center gap-2">
        <WifiOff className="w-3.5 h-3.5 text-[var(--muted-foreground)]" />
        <span className="text-xs font-semibold text-[var(--foreground)]">Baca Offline</span>
      </div>

      {thread ? (
        <>
          <p className="text-[10px] text-[var(--muted-foreground)]">
            {threadCached} bab novel ini tersimpan di perangkat. Simpan bab terjemahan
            berikutnya agar tetap bisa dibaca saat laptop mati atau di luar Wi-Fi.
          </p>
          <div className="grid grid-cols-3 gap-2" role="group" aria-label="Jumlah bab">
            {COUNT_OPTIONS.map((n) => (
              <Button
                key={n}
                type="button"
                variant={count === n ? "default" : "outline"}
                size="sm"
                className="text-[10px] h-9"
                onClick={() => setCount(n)}
                disabled={busy}
              >
                {n} bab
              </Button>
            ))}
          </div>
          <Button
            type="button"
            size="sm"
            className="w-full text-xs h-11 gap-1.5"
            onClick={handleSave}
            disabled={busy}
          >
            <Download className="w-3.5 h-3.5" />
            {progress
              ? `Menyimpan ${progress.done}/${progress.total}...`
              : `Simpan ${available} bab berikutnya`}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full text-xs h-11 gap-1.5 border-rose-500/30 text-rose-500 hover:bg-rose-500/10"
            onClick={handleClearThread}
            disabled={busy || threadCached === 0}
          >
            <Trash2 className="w-3.5 h-3.5" />
            Hapus cache novel ini
          </Button>
        </>
      ) : (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <p className="text-sm text-[var(--foreground)]">
            Tersimpan di perangkat ini:{" "}
            <span className="font-mono font-bold text-[var(--primary)]">{stats.chapters} bab</span>{" "}
            dari {stats.threads} novel,{" "}
            <span className="font-mono font-bold text-[var(--primary)]">{formatBytes(stats.bytes)}</span>
          </p>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="rounded-xl h-9 gap-1.5 border-rose-500/30 text-rose-500 hover:bg-rose-500/10 font-bold text-xs w-full sm:w-auto"
            onClick={handleClearAll}
            disabled={busy || (stats.chapters === 0 && stats.threads === 0)}
          >
            <Trash2 className="w-3.5 h-3.5" />
            Hapus Semua Cache Offline
          </Button>
        </div>
      )}
    </div>
  );
}
