import { useState, useEffect, useRef, useCallback } from "react";
import {
  Loader2,
  Save,
  Settings,
  ArrowLeft,
  Download,
  Layout,
  Sparkles,
  Eraser,
  Wand2,
  WifiOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  getApiUrl,
  getActiveWorkspace,
  getWorkspaceStorageKey,
  invalidateThreadCache,
} from "@/lib/api";
import ExportModal from "@/components/ExportModal";
import BulkTranslateModal from "@/components/BulkTranslateModal";
import BulkFetchModal from "@/components/BulkFetchModal";
import FidelityManagementModal from "@/components/FidelityManagementModal";
import { toast } from "sonner";
import { useConfirm } from "@/hooks/use-confirm";
import {
  getStoredEngineLoadMode,
  syncEngineLoadMode,
  ENGINE_LOAD_MODE_EVENT,
} from "@/lib/settingsSync";

// Subcomponents and types
import SettingsOverlay from "@/components/reader/SettingsOverlay";
import NovelHeader from "@/components/reader/NovelHeader";
import ChapterListControls from "@/components/reader/ChapterListControls";
import ChapterGrid from "@/components/reader/ChapterGrid";
import ThreadImageGallery from "@/components/reader/ThreadImageGallery";
import ChapterReader from "@/components/reader/ChapterReader";
import type { ThreadDetail, ChapterContent } from "@/components/reader/types";
import {
  getOfflineChapter,
  getOfflineThread,
  isServerUnreachableStatus,
  refreshOfflineChapterIfCached,
  refreshOfflineThreadIfCached,
} from "@/lib/offlineStorage";

// How long to wait for the server before showing the copy saved for offline reading
const OFFLINE_FALLBACK_DELAY_MS = 5000;
const SLOW_TOAST_ID = "reader-slow-load";

interface ReaderPageProps {
  threadId: number;
  initialChapterId?: number | null;
  onBack: () => void;
  onReadingChapterChange?: (isReading: boolean) => void;
  onActiveChapterChange?: (chapterId: number | null) => void;
}

const READER_SESSION_MAX_IDLE_MS = 6 * 60 * 60 * 1000;

interface ReaderSessionState {
  threadId: number;
  selectedChapterId: number | null;
  showChapterList: boolean;
  lastActiveAt: number;
}

function getReaderSessionKey(threadId: number): string {
  return `readomni_reader_session_v1_${getActiveWorkspace()}_${threadId}`;
}

function readReaderSession(threadId: number): ReaderSessionState | null {
  try {
    const raw = localStorage.getItem(getReaderSessionKey(threadId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ReaderSessionState>;
    if (
      parsed.threadId !== threadId ||
      typeof parsed.showChapterList !== "boolean" ||
      typeof parsed.lastActiveAt !== "number"
    ) {
      localStorage.removeItem(getReaderSessionKey(threadId));
      return null;
    }
    if (Date.now() - parsed.lastActiveAt > READER_SESSION_MAX_IDLE_MS) {
      localStorage.removeItem(getReaderSessionKey(threadId));
      return null;
    }
    return {
      threadId,
      selectedChapterId:
        typeof parsed.selectedChapterId === "number"
          ? parsed.selectedChapterId
          : null,
      showChapterList: parsed.showChapterList,
      lastActiveAt: parsed.lastActiveAt,
    };
  } catch {
    localStorage.removeItem(getReaderSessionKey(threadId));
    return null;
  }
}

/* eslint-disable react-hooks/exhaustive-deps */
/* eslint-disable @typescript-eslint/no-explicit-any */

export default function ReaderPage({
  threadId,
  initialChapterId,
  onBack,
  onReadingChapterChange,
  onActiveChapterChange,
}: ReaderPageProps) {
  const { confirm } = useConfirm();
  const initialReaderSession = readReaderSession(threadId);
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedChapterIdx, setSelectedChapterIdx] = useState<number | null>(
    null
  );
  const [chapterContent, setChapterContent] = useState<ChapterContent | null>(
    null
  );
  const [loadingContent, setLoadingContent] = useState(false);
  // Pocket Offline Cache: true while content is being served from IndexedDB
  const [isOffline, setIsOffline] = useState(false);
  // Guards the offline thread fallback against stale (slower) failed polls
  const threadRequestIdRef = useRef(0);
  const threadSuccessIdRef = useRef(0);
  const threadLiveLoadedRef = useRef(false);
  const [translatedText, setTranslatedText] = useState("");
  const [isTranslating, setIsTranslating] = useState(false);
  const [showChapterList, setShowChapterList] = useState(
    initialReaderSession?.showChapterList ?? true
  );
  const [fontSize, setFontSize] = useState(18);
  const [showSettings, setShowSettings] = useState(false);
  const [displayMode, setDisplayMode] = useState(
    localStorage.getItem("display_mode") || "translated"
  );

  const updateDisplayMode = (mode: string) => {
    setDisplayMode(mode);
    try {
      localStorage.setItem("display_mode", mode);
    } catch {
      /* ignore */
    }
    fetch(getApiUrl("/api/settings"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_mode: mode }),
    }).catch(() => {});
  };

  useEffect(() => {
    fetch(getApiUrl("/api/global-context"))
      .then((res) => res.json())
      .then((data) => {
        if (data.display_mode) {
          setDisplayMode(data.display_mode);
          try {
            localStorage.setItem("display_mode", data.display_mode);
          } catch {
            /* ignore */
          }
        }
        if (data.always_hide_thoughts !== undefined) {
          setAlwaysHideThoughts(data.always_hide_thoughts === 1);
        }
        if (data.prefetch_enabled !== undefined) {
          setPrefetchEnabled(data.prefetch_enabled === 1);
        }
        if (data.prefetch_count !== undefined) {
          setPrefetchCount(data.prefetch_count);
        }
        if (data.prefetch_mode) {
          setPrefetchMode(data.prefetch_mode);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const handleModeChange = (e: Event) => {
      const customEvent = e as CustomEvent<string>;
      if (customEvent.detail === "hard" || customEvent.detail === "soft") {
        setPrefetchMode(customEvent.detail);
      } else {
        setPrefetchMode(getStoredEngineLoadMode());
      }
    };
    window.addEventListener(ENGINE_LOAD_MODE_EVENT, handleModeChange);
    return () =>
      window.removeEventListener(ENGINE_LOAD_MODE_EVENT, handleModeChange);
  }, []);

  const [isTranslatingTitles, setIsTranslatingTitles] = useState(false);
  const [lastReadId, setLastReadId] = useState<number | null>(null);
  const [prefetchEnabled, setPrefetchEnabled] = useState(false);
  const [prefetchCount, setPrefetchCount] = useState(2);
  const [prefetchMode, setPrefetchMode] = useState<"soft" | "hard">(
    getStoredEngineLoadMode
  );
  const [globalSettings, setGlobalSettings] = useState<{
    lm_url?: string;
    lm_model?: string;
    target_language?: string;
  }>({});
  const [polishMode, setPolishMode] = useState<"soft" | "hard">("soft");
  const [polishSoftLimit, setPolishSoftLimit] = useState<number>(100);
  const [alwaysHideThoughts, setAlwaysHideThoughts] = useState<boolean>(true);

  const [autoDetectStart, setAutoDetectStart] = useState<boolean>(() => {
    const saved = localStorage.getItem(
      getWorkspaceStorageKey("auto_detect_start", threadId)
    );
    return saved !== null ? saved === "true" : true;
  });
  const [manualStartNum, setManualStartNum] = useState<number>(() => {
    const saved = localStorage.getItem(
      getWorkspaceStorageKey("manual_start_num", threadId)
    );
    return saved !== null ? parseInt(saved, 10) : 1;
  });
  const [volumeMode, setVolumeMode] = useState<boolean>(() => {
    const saved = localStorage.getItem(
      getWorkspaceStorageKey("volume_mode", threadId)
    );
    return saved !== null ? saved === "true" : true;
  });
  const [autoDetectVolume, setAutoDetectVolume] = useState<boolean>(() => {
    const saved = localStorage.getItem(
      getWorkspaceStorageKey("auto_detect_volume", threadId)
    );
    return saved !== null ? saved === "true" : true;
  });
  const [manualStartVolume, setManualStartVolume] = useState<number>(() => {
    const saved = localStorage.getItem(
      getWorkspaceStorageKey("manual_start_volume", threadId)
    );
    return saved !== null ? parseInt(saved, 10) : 1;
  });
  const [volumeBoundaries, setVolumeBoundaries] = useState<string>(() => {
    return (
      localStorage.getItem(
        getWorkspaceStorageKey("volume_boundaries", threadId)
      ) || ""
    );
  });
  const [volumeBoundaryType, setVolumeBoundaryType] = useState<string>(() => {
    return (
      localStorage.getItem(
        getWorkspaceStorageKey("volume_boundary_type", threadId)
      ) || "raw"
    );
  });
  const [chaptersPerVolume, setChaptersPerVolume] = useState<number>(() => {
    const saved = localStorage.getItem(
      getWorkspaceStorageKey("chapters_per_volume", threadId)
    );
    return saved !== null ? parseInt(saved, 10) : 0;
  });

  useEffect(() => {
    onReadingChapterChange?.(!showChapterList && selectedChapterIdx !== null);
    return () => onReadingChapterChange?.(false);
  }, [onReadingChapterChange, selectedChapterIdx, showChapterList]);

  useEffect(() => {
    if (
      thread &&
      selectedChapterIdx !== null &&
      thread.chapters?.[selectedChapterIdx]
    ) {
      onActiveChapterChange?.(thread.chapters[selectedChapterIdx].id);
    } else if (showChapterList) {
      onActiveChapterChange?.(null);
    }
  }, [onActiveChapterChange, selectedChapterIdx, showChapterList, thread]);

  useEffect(() => {
    localStorage.setItem(
      getWorkspaceStorageKey("auto_detect_start", threadId),
      String(autoDetectStart)
    );
    localStorage.setItem(
      getWorkspaceStorageKey("manual_start_num", threadId),
      String(manualStartNum)
    );
    localStorage.setItem(
      getWorkspaceStorageKey("volume_mode", threadId),
      String(volumeMode)
    );
    localStorage.setItem(
      getWorkspaceStorageKey("auto_detect_volume", threadId),
      String(autoDetectVolume)
    );
    localStorage.setItem(
      getWorkspaceStorageKey("manual_start_volume", threadId),
      String(manualStartVolume)
    );
    localStorage.setItem(
      getWorkspaceStorageKey("volume_boundaries", threadId),
      volumeBoundaries
    );
    localStorage.setItem(
      getWorkspaceStorageKey("volume_boundary_type", threadId),
      volumeBoundaryType
    );
    localStorage.setItem(
      getWorkspaceStorageKey("chapters_per_volume", threadId),
      String(chaptersPerVolume)
    );
  }, [
    threadId,
    autoDetectStart,
    manualStartNum,
    volumeMode,
    autoDetectVolume,
    manualStartVolume,
    volumeBoundaries,
    volumeBoundaryType,
    chaptersPerVolume,
  ]);

  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [isBulkModalOpen, setIsBulkModalOpen] = useState(false);
  const [isFetchModalOpen, setIsFetchModalOpen] = useState(false);
  const [isFidelityModalOpen, setIsFidelityModalOpen] = useState(false);
  const [bulkFetchInitialTab, setBulkFetchInitialTab] = useState<
    "missing" | "crawl"
  >("missing");
  const [chapterSearch, setChapterSearch] = useState("");
  const [controlsVisible, setControlsVisible] = useState(true);
  const [chapterFilter, setChapterFilter] = useState<
    "all" | "translated" | "illustrated" | "images"
  >("all");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [mobileToolbarVisible, setMobileToolbarVisible] = useState(true);

  const initialChapterHandledRef = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastFetchedIdRef = useRef<number | null>(null);
  const activeRequestIdRef = useRef<number>(0);
  const autoTranslatePendingRef = useRef(false);
  const initialReaderSessionRef = useRef<ReaderSessionState | null>(
    initialReaderSession
  );

  // App feeds `initialChapterId` from the active chapter, so it changes on every chapter switch.
  // Read it through a ref: as a dependency it re-created fetchThread and re-ran the initial load
  // (resetting the live-data guard and re-fetching) on each switch.
  // Keep ONLY the value from mount: right after mounting (chapter list still showing) this page
  // reports `null` to App, which feeds it back here before the thread has loaded. Following that
  // update made the restore below lose the requested chapter. ReaderPage mounts once per opened
  // thread, so the mount value is the one the restore needs.
  const initialChapterIdRef = useRef(initialChapterId);

  // Jump to initial chapter if provided (only once on initial load)
  useEffect(() => {
    if (thread && initialChapterId && !initialChapterHandledRef.current) {
      const idx = thread.chapters.findIndex((c) => c.id === initialChapterId);
      if (idx !== -1) {
        initialChapterHandledRef.current = true;
        goToChapter(idx);
      }
    }
  }, [thread, initialChapterId]);

  const fetchThread = useCallback(
    async (opts?: { silent?: boolean; force?: boolean }) => {
      const CACHE_KEY = getWorkspaceStorageKey(
        "readomni_thread_cache",
        threadId
      );

      // On silent refresh (polling), skip if tab is hidden unless forced
      if (opts?.silent && !opts?.force && document.hidden) return;

      const applyThreadData = (data: ThreadDetail, keepLoaded = false) => {
        // keepLoaded: an offline snapshot must not overwrite fresher data already on screen
        if (keepLoaded) {
          setThread((prev) => prev ?? data);
        } else {
          setThread(data);
          if (data.last_read_id) setLastReadId(data.last_read_id);
        }

        // Only restore chapter index ONCE on initial load if not yet chosen/handled
        if (!initialChapterHandledRef.current) {
          const storedSession = initialReaderSessionRef.current;
          const targetChapterId =
            initialChapterIdRef.current ||
            storedSession?.selectedChapterId ||
            data.last_read_id ||
            null;
          if (targetChapterId) {
            const restoredIdx = data.chapters.findIndex(
              (chapter) => chapter.id === targetChapterId
            );
            if (restoredIdx !== -1) {
              setSelectedChapterIdx(restoredIdx);
              initialChapterHandledRef.current = true;
              if (storedSession) {
                setShowChapterList(storedSession.showChapterList);
              } else if (initialChapterIdRef.current) {
                setShowChapterList(false);
              }
            }
          }
          initialReaderSessionRef.current = null;
        }
      };

      const requestId = ++threadRequestIdRef.current;
      let networkFailed = false;
      // Serve the offline snapshot only while no live thread data is on screen (a slow poll
      // must not flip a live reader into "offline"); the chapter fallback covers that case.
      const serveOfflineSnapshot = async () => {
        if (threadLiveLoadedRef.current) return;
        const offlineThread = await getOfflineThread(threadId);
        if (
          offlineThread &&
          threadSuccessIdRef.current < requestId &&
          !threadLiveLoadedRef.current
        ) {
          applyThreadData(offlineThread, true);
          setIsOffline(true);
          // A cold open waits on `loading`; the snapshot is readable now
          setLoading(false);
        }
      };
      // A LAN request from mobile data can hang for a long time instead of failing;
      // show the offline snapshot meanwhile (the request keeps running and replaces it).
      const slowTimer = window.setTimeout(serveOfflineSnapshot, OFFLINE_FALLBACK_DELAY_MS);
      try {
        const res = await fetch(
          getApiUrl(`/api/threads/${threadId}?t=${Date.now()}`),
          {
            cache: "no-store",
          }
        ).catch((err) => {
          networkFailed = true;
          throw err;
        });
        if (!res.ok) {
          networkFailed = isServerUnreachableStatus(res.status);
          throw new Error("Network response not ok");
        }
        const data: ThreadDetail = await res.json();
        window.clearTimeout(slowTimer);
        threadSuccessIdRef.current = Math.max(threadSuccessIdRef.current, requestId);
        threadLiveLoadedRef.current = true;
        applyThreadData(data);
        setIsOffline(false);
        refreshOfflineThreadIfCached(data);

        // Cache to sessionStorage for fast restore after mobile screen-off reload
        try {
          sessionStorage.setItem(
            CACHE_KEY,
            JSON.stringify({ data, ts: Date.now() })
          );
        } catch {
          /* quota exceeded — ignore */
        }
      } catch (err) {
        window.clearTimeout(slowTimer);
        console.error("Failed to fetch thread:", err);
        // Server unreachable (not an HTTP error): fall back to the chapter list saved offline
        if (networkFailed) await serveOfflineSnapshot();
      }
    },
    [threadId]
  );

  useEffect(() => {
    const persistReaderSession = () => {
      if (!thread) return;
      const currentChapterId =
        selectedChapterIdx !== null && thread.chapters?.[selectedChapterIdx]
          ? thread.chapters[selectedChapterIdx].id
          : null;

      const savedRaw = localStorage.getItem(getReaderSessionKey(threadId));
      let prevSession: ReaderSessionState | null = null;
      try {
        if (savedRaw) prevSession = JSON.parse(savedRaw);
      } catch {
        /* ignore */
      }

      const finalChapterId =
        currentChapterId !== null
          ? currentChapterId
          : (prevSession?.selectedChapterId ?? null);

      const payload: ReaderSessionState = {
        threadId,
        selectedChapterId: finalChapterId,
        showChapterList,
        lastActiveAt: Date.now(),
      };
      localStorage.setItem(
        getReaderSessionKey(threadId),
        JSON.stringify(payload)
      );
    };

    // Save session immediately when state changes
    persistReaderSession();

    window.addEventListener("pagehide", persistReaderSession);
    document.addEventListener("visibilitychange", persistReaderSession);

    return () => {
      window.removeEventListener("pagehide", persistReaderSession);
      document.removeEventListener("visibilitychange", persistReaderSession);
    };
  }, [thread, threadId, selectedChapterIdx, showChapterList]);

  // Real-time live update for chapter translation status (green dots & progress)
  useEffect(() => {
    let lastFetchedCompleted = -1;
    let lastFetchedCurrentChId: number | null = null;

    const handleBatchProgress = (e: Event) => {
      const customEv = e as CustomEvent;
      const detail = customEv.detail;
      if (!detail || detail.thread_id !== threadId) return;

      // Always re-fetch when completed count or active chapter changes
      if (
        detail.completed !== lastFetchedCompleted ||
        detail.current_chapter_id !== lastFetchedCurrentChId
      ) {
        lastFetchedCompleted = detail.completed;
        lastFetchedCurrentChId = detail.current_chapter_id;
        fetchThread({ silent: true, force: true });
      }
    };

    const handleBatchCompleted = (e: Event) => {
      const customEv = e as CustomEvent;
      const detail = customEv.detail;
      if (detail && detail.thread_id && detail.thread_id !== threadId) return;
      fetchThread({ silent: true, force: true });
    };

    window.addEventListener("batch-progress", handleBatchProgress);
    window.addEventListener("batch-completed", handleBatchCompleted);

    return () => {
      window.removeEventListener("batch-progress", handleBatchProgress);
      window.removeEventListener("batch-completed", handleBatchCompleted);
    };
  }, [threadId, fetchThread]);

  const handleStartBatch = async (
    chapterIds: number[],
    aiExtract: boolean,
    loadMode: "soft" | "hard",
    targetLang: string,
    overwrite: boolean,
    translationMode: "quality" | "fast" = "quality"
  ) => {
    if (!thread) return;

    syncEngineLoadMode(loadMode);
    setPrefetchMode(loadMode);

    try {
      const res = await fetch(
        getApiUrl(`/api/threads/${threadId}/batch-translate`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chapter_ids: chapterIds,
            ai_extract: aiExtract,
            overwrite: overwrite,
            target_lang: targetLang,
            translation_mode: translationMode,
            load_mode: loadMode,
          }),
        }
      );

      if (!res.ok) throw new Error("Failed to start batch");

      // Re-fetch thread to update chapter statuses to "processing" and trigger the polling mechanism
      await fetchThread({ silent: true, force: true });
    } catch (e: any) {
      console.error(e);
      toast.error(e.message || "Failed to start batch translation");
    }
  };

  const handleStartBulkFetch = async (
    chapterIds: number[],
    fetchOnly: boolean
  ) => {
    if (!thread) return;

    try {
      const res = await fetch(
        getApiUrl(`/api/threads/${threadId}/batch-translate`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chapter_ids: chapterIds,
            fetch_only: fetchOnly,
          }),
        }
      );

      if (!res.ok) throw new Error("Failed to start bulk fetch");

      await fetchThread({ silent: true, force: true });
    } catch (err: any) {
      toast.error(err.message || "Failed to start bulk fetch");
    }
  };

  // Initial Load — parallel fetch with sessionStorage fast-restore
  useEffect(() => {
    const CACHE_KEY = getWorkspaceStorageKey("readomni_thread_cache", threadId);
    const CACHE_TTL = 5 * 60 * 1000;

    const init = async () => {
      threadLiveLoadedRef.current = false; // new thread: nothing live on screen yet
      // Instant restore from cache while real fetch runs in background
      try {
        const raw = sessionStorage.getItem(CACHE_KEY);
        if (raw) {
          const { data, ts } = JSON.parse(raw) as {
            data: ThreadDetail;
            ts: number;
          };
          if (Date.now() - ts < CACHE_TTL) {
            setThread(data);
            if (data.last_read_id) setLastReadId(data.last_read_id);
            const storedSession = initialReaderSessionRef.current;
            const targetId =
              initialChapterIdRef.current ||
              storedSession?.selectedChapterId ||
              data.last_read_id ||
              null;
            if (targetId && !initialChapterHandledRef.current) {
              const restoredIdx = data.chapters.findIndex(
                (c) => c.id === targetId
              );
              if (restoredIdx !== -1) {
                setSelectedChapterIdx(restoredIdx);
                initialChapterHandledRef.current = true;
                if (storedSession) {
                  setShowChapterList(storedSession.showChapterList);
                } else if (initialChapterIdRef.current) {
                  setShowChapterList(false);
                }
              }
              initialReaderSessionRef.current = null;
            }
            setLoading(false);
          }
        }
      } catch {
        /* ignore */
      }

      // Parallel: fetch thread + global settings simultaneously
      const [, gsData] = await Promise.allSettled([
        fetchThread(),
        fetch(getApiUrl("/api/global-context")).then((r) =>
          r.ok ? r.json() : null
        ),
      ]);

      if (gsData.status === "fulfilled" && gsData.value) {
        const gs = gsData.value;
        setPrefetchEnabled(gs.prefetch_enabled === 1);
        setPrefetchCount(gs.prefetch_count || 2);
        setPrefetchMode(gs.prefetch_mode || "soft");
        setPolishMode(gs.polish_mode || "soft");
        setPolishSoftLimit(gs.polish_soft_limit || 100);
        setAlwaysHideThoughts(gs.always_hide_thoughts !== 0);

        const provider = gs.llm_provider || "lm_studio";
        const activeModel =
          provider === "gemini"
            ? gs.gemini_model || "gemini-2.5-flash"
            : provider === "openai"
              ? gs.openai_model || "gpt-4o-mini"
              : provider === "openrouter"
                ? gs.openrouter_model || "deepseek/deepseek-chat"
                : gs.lm_model || "qwen2.5-7b";

        setGlobalSettings({
          lm_url: gs.lm_url,
          lm_model: activeModel,
          target_language: gs.target_language,
        });
      }

      setLoading(false);
    };
    init();
  }, [fetchThread, threadId]);

  // Polling for background updates (ADR-013) — paused when tab is hidden
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    const hasProcessing =
      thread?.chapters?.some((c) => c.translation_status === "processing") ||
      false;

    if (prefetchEnabled || hasProcessing) {
      interval = setInterval(() => {
        fetchThread({ silent: true }); // skip if tab hidden
      }, 5000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [prefetchEnabled, fetchThread, thread?.chapters]);

  const handleTranslateChapter = useCallback(
    async (
      isResume = false,
      initialText = "",
      overrideContent?: string,
      overrideId?: number,
      forceOverwrite = false
    ) => {
      const textToTranslate =
        overrideContent || chapterContent?.content_original || "";
      const chId = overrideId || chapterContent?.id;

      if (isTranslating || !chId) return;
      setIsTranslating(true);
      if (!isResume) setTranslatedText("");
      else setTranslatedText(initialText);

      try {
        const lmUrl = globalSettings.lm_url;
        const lmModel = globalSettings.lm_model;
        const targetLang = globalSettings.target_language || "Indonesian";

        const res = await fetch(getApiUrl("/api/translate/stream"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: textToTranslate,
            lm_url: lmUrl,
            model: lmModel,
            target_lang: targetLang,
            thread_id: threadId,
            chapter_id: chId,
            force_overwrite: forceOverwrite,
          }),
        });

        if (!res.body) throw new Error("No stream");
        const reader = res.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value);
          const lines = chunk.split("\n");
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const dataStr = line.slice(6);
              if (dataStr === "[DONE]") break;
              try {
                const data = JSON.parse(dataStr);
                if (data.final_text) {
                  setTranslatedText(data.final_text);
                  setChapterContent((prev) =>
                    prev
                      ? { ...prev, content_translated: data.final_text }
                      : prev
                  );
                } else if (data.content) {
                  setTranslatedText((prev) => prev + data.content);
                } else if (data.error) {
                  setTranslatedText((prev) => prev + "\n⚠️ " + data.error);
                }
              } catch {
                // Ignore invalid JSON chunks gracefully
              }
            }
          }
        }

        // Optimistically update thread state so green dot lights up immediately
        if (chId) {
          invalidateThreadCache(threadId, chId);
          setThread((prev) => {
            if (!prev) return prev;
            return {
              ...prev,
              chapters: prev.chapters.map((c) =>
                c.id === chId
                  ? { ...c, has_translation: true, translation_status: "done" }
                  : c
              ),
            };
          });
        }

        // Update thread state from server
        await fetchThread({ force: true });
      } catch (err) {
        console.error("Translation error:", err);
        setTranslatedText((prev) => prev + "\n⚠️ Translation failed.");
      } finally {
        setIsTranslating(false);
      }
    },
    [
      isTranslating,
      threadId,
      fetchThread,
      chapterContent?.content_original,
      chapterContent?.id,
      globalSettings,
    ]
  );

  const lastFetchedStatusRef = useRef<string | null>(null);

  // Header (and its Offline badge) is hidden while reading, so announce offline mode once
  useEffect(() => {
    if (isOffline) {
      toast.info("Mode offline: membaca dari cache perangkat", { id: "reader-offline-mode" });
    }
  }, [isOffline]);

  // Handle Chapter Selection & Mobile Screen Wake Recovery
  useEffect(() => {
    if (!thread || selectedChapterIdx === null) return;
    const ch = thread.chapters[selectedChapterIdx];
    if (!ch) return;

    const CH_CACHE_KEY = getWorkspaceStorageKey(
      "readomni_chapter_cache",
      `${threadId}_${ch.id}`
    );

    // Prevent re-fetching ONLY if we already have valid chapterContent AND id matches AND translation_status matches
    if (
      chapterContent &&
      chapterContent.id === ch.id &&
      lastFetchedIdRef.current === ch.id &&
      lastFetchedStatusRef.current === ch.translation_status
    ) {
      return;
    }

    const abortController = new AbortController();
    const currentRequestId = ++activeRequestIdRef.current;

    // Chapter whose text is on screen when this request starts (for the offline-miss revert)
    const previousContentId = chapterContent?.id ?? null;
    let shownForThisChapter = previousContentId === ch.id;

    const fetchContent = async () => {
      // Instant restore from sessionStorage cache before network fetch
      if (!chapterContent || chapterContent.id !== ch.id) {
        try {
          const cachedRaw = sessionStorage.getItem(CH_CACHE_KEY);
          if (cachedRaw) {
            const cachedData: ChapterContent = JSON.parse(cachedRaw);
            if (
              cachedData.id === ch.id &&
              activeRequestIdRef.current === currentRequestId
            ) {
              setChapterContent(cachedData);
              setTranslatedText(cachedData.content_translated || "");
              shownForThisChapter = true;
            }
          }
        } catch {
          /* ignore */
        }
      }

      setLoadingContent(true);
      let networkFailed = false;
      let networkSettled = false;
      let httpStatus: number | null = null;
      const serveOfflineChapter = async (): Promise<boolean> => {
        const offlineData = await getOfflineChapter(threadId, ch.id);
        if (!offlineData || activeRequestIdRef.current !== currentRequestId) return false;
        if (networkSettled && !networkFailed) return false; // live data already arrived
        setChapterContent(offlineData);
        setTranslatedText(offlineData.content_translated || "");
        setIsOffline(true);
        // The reader hides text behind a spinner while loading; the saved copy is readable now
        // (a late live response still replaces it).
        setLoadingContent(false);
        shownForThisChapter = true;
        return true;
      };
      // Slow/hanging network (e.g. LAN address over mobile data): show the saved copy meanwhile
      const slowTimer = window.setTimeout(async () => {
        const served = await serveOfflineChapter();
        if (served || networkSettled || activeRequestIdRef.current !== currentRequestId) return;
        if (shownForThisChapter) {
          // A session copy of this chapter is already rendered but hidden behind the spinner:
          // reveal it while waiting (a late live response still replaces it).
          setLoadingContent(false);
          return;
        }
        // Nothing to show yet. This is often just a slow server (e.g. on-demand scraping), so
        // inform rather than alarm; mention offline only for novels saved for offline reading.
        const usesOffline = (await getOfflineThread(threadId)) !== null;
        if (networkSettled || activeRequestIdRef.current !== currentRequestId) return;
        toast.info(
          usesOffline ? "Bab ini belum disimpan untuk dibaca offline" : "Server lambat — masih memuat bab…",
          {
            id: SLOW_TOAST_ID,
            description: usesOffline ? "Server lambat atau tidak terjangkau; masih menunggu…" : undefined,
          }
        );
      }, OFFLINE_FALLBACK_DELAY_MS);
      // Go back to the chapter still on screen so its text never appears under another
      // chapter's number; with nothing to go back to, show the chapter list.
      const revertToPreviousChapter = () => {
        const prevIdx =
          previousContentId !== null
            ? (thread?.chapters.findIndex((c) => c.id === previousContentId) ?? -1)
            : -1;
        if (prevIdx >= 0) {
          setSelectedChapterIdx(prevIdx);
        } else {
          setChapterContent(null);
          setShowChapterList(true);
        }
      };
      try {
        const res = await fetch(
          getApiUrl(`/api/threads/${threadId}/chapters/${ch.id}`),
          {
            signal: abortController.signal,
          }
        ).catch((err) => {
          networkFailed = true;
          throw err;
        });
        if (!res.ok) {
          httpStatus = res.status;
          networkFailed = isServerUnreachableStatus(res.status);
          throw new Error("Failed to fetch chapter content");
        }
        const data: ChapterContent = await res.json();
        networkSettled = true;
        window.clearTimeout(slowTimer);
        toast.dismiss(SLOW_TOAST_ID);

        // Only commit state if this is still the active request
        if (activeRequestIdRef.current === currentRequestId) {
          lastFetchedIdRef.current = ch.id;
          lastFetchedStatusRef.current =
            ch.translation_status || data.translation_status || null;
          setChapterContent(data);
          setTranslatedText(data.content_translated || "");
          setLastReadId(ch.id);
          setIsOffline(false);
          refreshOfflineChapterIfCached(threadId, data);

          try {
            sessionStorage.setItem(CH_CACHE_KEY, JSON.stringify(data));
          } catch {
            /* quota exceeded — ignore */
          }

          // Background prefetch adjacent chapters (N+1, N-1) into sessionStorage
          if (thread?.chapters) {
            [selectedChapterIdx + 1, selectedChapterIdx - 1].forEach(
              (adjIdx) => {
                const adjCh = thread.chapters[adjIdx];
                if (!adjCh) return;
                const adjKey = getWorkspaceStorageKey(
                  "readomni_chapter_cache",
                  `${threadId}_${adjCh.id}`
                );
                if (sessionStorage.getItem(adjKey)) return;
                // track=0: warming N±1 must not move the server-side reading position
                fetch(
                  getApiUrl(
                    `/api/threads/${threadId}/chapters/${adjCh.id}?track=0`
                  )
                )
                  .then((r) => (r.ok ? r.json() : null))
                  .then((adjData) => {
                    if (adjData) {
                      try {
                        sessionStorage.setItem(adjKey, JSON.stringify(adjData));
                      } catch {
                        /* ignore quota */
                      }
                    }
                  })
                  .catch(() => {});
              }
            );
          }
        }
      } catch (err: unknown) {
        networkSettled = true;
        window.clearTimeout(slowTimer);
        toast.dismiss(SLOW_TOAST_ID);
        if (err instanceof Error && err.name !== "AbortError") {
          // Do not set chapterContent to null on abort/error if we already have cached content!
          if (activeRequestIdRef.current === currentRequestId) {
            lastFetchedIdRef.current = null;
            lastFetchedStatusRef.current = null;
          }
          // Server unreachable (not an HTTP error): serve the chapter saved offline, if any
          if (networkFailed) {
            const served = await serveOfflineChapter();
            if (
              !served &&
              !shownForThisChapter &&
              activeRequestIdRef.current === currentRequestId
            ) {
              toast.error("Bab ini belum disimpan untuk dibaca offline", {
                id: "reader-offline-missing",
              });
              revertToPreviousChapter();
            }
          } else if (
            httpStatus !== null &&
            !shownForThisChapter &&
            activeRequestIdRef.current === currentRequestId
          ) {
            // Server answered with an error (e.g. 404 deleted, 500): say so and keep the
            // previous chapter's text from being shown under this chapter's number.
            toast.error(`Gagal memuat bab (HTTP ${httpStatus})`, { id: "reader-chapter-error" });
            revertToPreviousChapter();
          }
        }
      } finally {
        window.clearTimeout(slowTimer);
        // Only clear loading if this is still the active request
        if (activeRequestIdRef.current === currentRequestId) {
          setLoadingContent(false);
        }
      }
    };

    fetchContent();
    return () => {
      abortController.abort();
      toast.dismiss(SLOW_TOAST_ID);
    };
  }, [selectedChapterIdx, threadId, thread]);

  // While offline, retry as soon as the device signals the network/server may be back.
  // Event-driven (no interval), and at most one retry in flight: `focus` and
  // `visibilitychange` fire together on every return to the tab, and on a hanging LAN
  // address each retry would otherwise add another request that never settles.
  const offlineRetryInFlightRef = useRef(false);
  useEffect(() => {
    if (!isOffline) return;
    const retry = () => {
      if (document.visibilityState === "hidden" || offlineRetryInFlightRef.current) return;
      offlineRetryInFlightRef.current = true;
      lastFetchedIdRef.current = null;
      lastFetchedStatusRef.current = null;
      fetchThread({ silent: true, force: true }).finally(() => {
        offlineRetryInFlightRef.current = false;
      });
    };
    window.addEventListener("online", retry);
    window.addEventListener("focus", retry);
    document.addEventListener("visibilitychange", retry);
    return () => {
      window.removeEventListener("online", retry);
      window.removeEventListener("focus", retry);
      document.removeEventListener("visibilitychange", retry);
    };
  }, [isOffline, fetchThread]);

  // Mobile Screen Lock/Wake recovery: re-verify chapter content when document becomes visible
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (
        !document.hidden &&
        !showChapterList &&
        selectedChapterIdx !== null &&
        thread
      ) {
        const ch = thread.chapters[selectedChapterIdx];
        if (ch && (!chapterContent || chapterContent.id !== ch.id)) {
          // Force reset lastFetchedIdRef to trigger fetchContent
          lastFetchedIdRef.current = null;
          lastFetchedStatusRef.current = null;
          fetchThread({ silent: true });
        }
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("focus", handleVisibilityChange);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("focus", handleVisibilityChange);
    };
  }, [
    showChapterList,
    selectedChapterIdx,
    thread,
    chapterContent,
    fetchThread,
  ]);

  // Auto-translate on fetch next chapter
  useEffect(() => {
    if (
      autoTranslatePendingRef.current &&
      chapterContent?.id &&
      !isTranslating
    ) {
      autoTranslatePendingRef.current = false;
      // Small delay ensures UI has rendered the chapter view before kicking off the heavy translation stream
      setTimeout(() => {
        handleTranslateChapter(
          false,
          "",
          chapterContent.content_original ?? undefined,
          chapterContent.id,
          false
        );
      }, 100);
    }
  }, [chapterContent, handleTranslateChapter, isTranslating]);

  // Auto-detect starting chapter number based on the first chapter's original title
  const getAutoStartNum = useCallback(() => {
    if (!thread || !thread.chapters || thread.chapters.length === 0) return 1;
    const firstTitle = thread.chapters[0].title_original || "";

    const parseChineseNumerals = (cn: string): number => {
      if (!cn) return 0;
      cn = cn.trim();

      const cnNums: { [key: string]: number } = {
        零: 0,
        〇: 0,
        一: 1,
        二: 2,
        两: 2,
        三: 3,
        四: 4,
        五: 5,
        六: 6,
        七: 7,
        八: 8,
        九: 9,
        壹: 1,
        贰: 2,
        叁: 3,
        肆: 4,
        伍: 5,
        陆: 6,
        柒: 7,
        捌: 8,
        玖: 9,
        倆: 2,
      };
      const cnUnits: { [key: string]: number } = {
        十: 10,
        拾: 10,
        百: 100,
        佰: 100,
        千: 1000,
        仟: 1000,
        万: 10000,
        萬: 10000,
        亿: 100000000,
        億: 100000000,
      };

      const chars = Array.from(cn);
      const hasUnit = chars.some((char) => char in cnUnits);
      if (!hasUnit) {
        let valStr = "";
        for (const char of chars) {
          if (char in cnNums) {
            valStr += cnNums[char].toString();
          }
        }
        return valStr ? parseInt(valStr, 10) : 0;
      }

      let total = 0;
      let currentSection = 0;
      let currentValue = 0;

      for (const char of chars) {
        if (char in cnNums) {
          currentValue = cnNums[char];
        } else if (char in cnUnits) {
          const unitVal = cnUnits[char];
          if (unitVal === 10000 || unitVal === 100000000) {
            let sectionVal = currentSection + currentValue;
            if (sectionVal === 0) {
              sectionVal = 1;
            }
            total += sectionVal * unitVal;
            currentSection = 0;
            currentValue = 0;
          } else {
            if (currentValue === 0) {
              currentValue = 1;
            }
            currentSection += currentValue * unitVal;
            currentValue = 0;
          }
        }
      }

      return total + currentSection + currentValue;
    };

    // Strip common volume prefixes like v\d+[-_]? (case-insensitive) to prevent matching the volume number
    const titleToParse = firstTitle.replace(/^[vV]\d+[-_]?/, "").trim();

    // 1. Try standard Arabic digit pattern with prefix
    const arabicMatch = titleToParse.match(
      /(?:chapter|bab|vol|volume|ch|第)\s*(\d+)/i
    );
    if (arabicMatch) return parseInt(arabicMatch[1], 10);

    // 2. Try standard Arabic digit pattern without prefix
    const digitMatch = titleToParse.match(/\d+/);
    if (digitMatch) return parseInt(digitMatch[0], 10);

    // 3. Try Chinese numeral pattern with prefix
    const cnMatch = titleToParse.match(
      /(?:chapter|bab|vol|volume|ch|第)\s*([一二三四五六七八九十百千万零两]+)/i
    );
    if (cnMatch) return parseChineseNumerals(cnMatch[1]);

    // 4. Try Chinese numeral pattern without prefix
    const cnDigitMatch =
      titleToParse.match(/[一二三四五六七八九十百千万零两]+/);
    if (cnDigitMatch) return parseChineseNumerals(cnDigitMatch[0]);

    return 1;
  }, [thread]);

  // Infinite Polish - Single Title
  const handleSingleTitlePolish = async (
    chapterId: number,
    e: React.MouseEvent
  ) => {
    e.stopPropagation(); // VERY IMPORTANT: Don't open the chapter!
    if (isTranslatingTitles) return;

    setIsTranslatingTitles(true);
    try {
      const targetLang =
        globalSettings.target_language ||
        localStorage.getItem("target_language") ||
        "Indonesian";
      const autoStart = getAutoStartNum();
      const startNum = autoDetectStart ? autoStart : manualStartNum || 1;
      const url = getApiUrl(
        `/api/threads/${threadId}/translate-titles?repolish=true&chapter_id=${chapterId}&target_lang=${targetLang}&start_number=${startNum}&volume_mode=${volumeMode}&auto_detect_volume=${autoDetectVolume}&start_volume=${manualStartVolume}&volume_boundaries=${encodeURIComponent(volumeBoundaries)}&volume_boundary_type=${volumeBoundaryType}&chapters_per_volume=${chaptersPerVolume}`
      );

      const res = await fetch(url, { method: "POST" });
      if (res.ok) {
        await fetchThread();
      }
    } catch (err) {
      console.error("Polish failed:", err);
    } finally {
      setIsTranslatingTitles(false);
    }
  };

  // Delete single chapter
  const handleDeleteChapter = async (
    chapterId: number,
    e: React.MouseEvent
  ) => {
    e.stopPropagation();
    const chapter = thread?.chapters.find((c) => c.id === chapterId);
    const chapterName =
      chapter?.title_translated ||
      chapter?.title_original ||
      `Chapter ${(chapter?.order ?? 0) + 1}`;

    const isConfirmed = await confirm({
      title: "Delete Chapter?",
      description: `Are you sure you want to delete "${chapterName}"? This cannot be undone.`,
      confirmText: "Delete",
      variant: "destructive",
    });
    if (!isConfirmed) return;

    try {
      const res = await fetch(
        getApiUrl(`/api/threads/${threadId}/chapters/${chapterId}`),
        { method: "DELETE" }
      );
      if (res.ok) {
        invalidateThreadCache(threadId, chapterId);
        setSelectedChapterIdx((prev) =>
          prev !== null && prev > 0 ? prev - 1 : prev
        );
        toast.success("Chapter deleted");
        await fetchThread({ force: true });
      }
    } catch {
      toast.error("Failed to delete chapter");
    }
  };

  // Infinite Polish - All
  const handleTranslateTitles = async (isRepolish = false) => {
    if (!thread || isTranslatingTitles) return;

    if (isRepolish) {
      const isConfirmed = await confirm({
        title: "Repolish Titles",
        description:
          "All existing polished titles will be overwritten by AI. Continue?",
        confirmText: "Overwrite",
        variant: "destructive",
      });
      if (!isConfirmed) return;
    }

    setIsTranslatingTitles(true);
    try {
      const targetLang = globalSettings.target_language || "Indonesian";
      const autoStart = getAutoStartNum();
      const startNum = autoDetectStart ? autoStart : manualStartNum || 1;
      const url = getApiUrl(
        `/api/threads/${threadId}/translate-titles?target_lang=${targetLang}${isRepolish ? "&repolish=true" : ""}&start_number=${startNum}&volume_mode=${volumeMode}&auto_detect_volume=${autoDetectVolume}&start_volume=${manualStartVolume}&volume_boundaries=${encodeURIComponent(volumeBoundaries)}&volume_boundary_type=${volumeBoundaryType}&chapters_per_volume=${chaptersPerVolume}`
      );

      const res = await fetch(url, { method: "POST" });
      if (!res.ok) throw new Error("Failed");

      if (res.body) {
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            if (!line.trim()) continue;
            let payload: any;
            try {
              payload = JSON.parse(line);
            } catch {
              continue;
            }
            if (payload.status === "error" || payload.error) {
              throw new Error(
                payload.message || payload.error || "Failed to polish titles"
              );
            }
          }
        }
      }

      await fetchThread();
      toast.success("Titles polished successfully.");
    } catch (err: any) {
      console.error("Title translation failed:", err);
      toast.error(err?.message || "Title translation failed.");
    } finally {
      setIsTranslatingTitles(false);
    }
  };

  const handlePolishLanguageChange = async (lang: string) => {
    setGlobalSettings((prev) => ({ ...prev, target_language: lang }));
    try {
      await fetch(getApiUrl("/api/settings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_language: lang }),
      });
    } catch (err) {
      console.error("Failed to update target language", err);
    }
  };

  const handlePolishModeChange = async (mode: "soft" | "hard") => {
    setPolishMode(mode);
    try {
      await fetch(getApiUrl("/api/settings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ polish_mode: mode }),
      });
    } catch (err) {
      console.error("Failed to update polish mode", err);
    }
  };

  const handlePolishLimitChange = async (limit: number) => {
    setPolishSoftLimit(limit);
    try {
      await fetch(getApiUrl("/api/settings"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ polish_soft_limit: limit }),
      });
    } catch (err) {
      console.error("Failed to update polish limit", err);
    }
  };

  const handleSaveTranslation = async () => {
    if (!translatedText || !chapterContent) return;
    try {
      const res = await fetch(
        getApiUrl(
          `/api/threads/${threadId}/chapters/${chapterContent.id}/translation`
        ),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ translated_text: translatedText }),
        }
      );
      if (!res.ok) throw new Error("Failed to save translation");
      const updatedChapter: ChapterContent = {
        ...chapterContent,
        content_translated: translatedText,
        translation_status: "done",
      };
      setChapterContent(updatedChapter);
      invalidateThreadCache(threadId, chapterContent.id);
      try {
        sessionStorage.setItem(
          getWorkspaceStorageKey(
            "readomni_chapter_cache",
            `${threadId}_${chapterContent.id}`
          ),
          JSON.stringify(updatedChapter)
        );
      } catch {
        /* ignore quota */
      }
      toast.success("Translation saved");
      await fetchThread({ force: true });
    } catch (err) {
      console.error("Failed to save:", err);
      toast.error("Failed to save translation");
    }
  };

  const handleFetchNextChapter = async () => {
    if (!thread || !chapterContent) return;
    try {
      const toastId = toast.loading("Fetching next chapter from web...");
      const res = await fetch(
        getApiUrl(
          `/api/threads/${threadId}/chapters/${chapterContent.id}/fetch-next`
        ),
        {
          method: "POST",
        }
      );
      const data = await res.json();
      if (!res.ok) {
        toast.error(data.detail || "Failed to fetch next chapter", {
          id: toastId,
        });
        return;
      }
      toast.success(data.message || "Next chapter fetched successfully!", {
        id: toastId,
      });

      // Refresh thread to get the new chapter
      await fetchThread();

      // Auto-navigate to the next chapter since it's now fetched
      if (selectedChapterIdx !== null) {
        autoTranslatePendingRef.current = true;
        goToChapter(selectedChapterIdx + 1);
      }
    } catch (err) {
      console.error("Failed to fetch next chapter:", err);
      toast.error("Network error while fetching next chapter");
    }
  };

  const runCleanerTool = async (tool: "txt-cleaner" | "epub-cleaner") => {
    const label = tool === "txt-cleaner" ? "TXT Cleaner" : "EPUB Cleaner";
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/${tool}`), {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `${label} failed`);
      invalidateThreadCache(threadId);
      await fetchThread({ force: true });

      const message = `${label}: ${data.chapters_updated}/${data.chapters_scanned} chapters updated (${data.lines_removed} lines removed).`;
      if (
        data.chapters_updated > 0 ||
        (data.chapters_deleted && data.chapters_deleted > 0)
      ) {
        toast.success(message);
      } else {
        toast.info(message);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      toast.error(`${label} failed: ${msg}`);
    }
  };

  function goToChapter(idx: number) {
    setSelectedChapterIdx(idx);
    setShowChapterList(false);
    setControlsVisible(true);
    setIsTranslating(false);
    setMobileToolbarVisible(true);
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-[var(--primary)]" />
        <p className="text-[var(--muted-foreground)] font-medium animate-pulse">
          Consulting the archives...
        </p>
      </div>
    );
  }

  if (!thread) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-6 text-center gap-4">
        <div className="w-16 h-16 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-500 mb-2">
          <Loader2 className="w-8 h-8" />
        </div>
        <h3 className="text-xl font-bold text-[var(--foreground)]">
          Gagal Memuat Novel
        </h3>
        <p className="text-sm text-[var(--muted-foreground)] max-w-md">
          Aplikasi tidak dapat terhubung ke server backend di HP. Pastikan:
        </p>
        <ul className="text-xs text-[var(--muted-foreground)] text-left list-disc list-inside space-y-1 bg-[var(--card)] p-4 rounded-xl border border-[var(--border)] max-w-md">
          <li>Laptop dan HP berada di jaringan Wi-Fi yang sama.</li>
          <li>
            Backend Uvicorn dijalankan dengan <b>--host 0.0.0.0</b> (misal:{" "}
            <code className="text-[var(--primary)] font-mono">
              py -m uvicorn main:app --reload --port 8000 --host 0.0.0.0
            </code>
            ).
          </li>
          <li>Windows Firewall di laptop mengizinkan Port 8000.</li>
        </ul>
        <div className="flex gap-3 mt-4">
          <Button variant="outline" onClick={onBack}>
            Kembali
          </Button>
          <Button
            onClick={() => {
              setLoading(true);
              fetchThread().finally(() => setLoading(false));
            }}
          >
            Coba Lagi
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen h-[100dvh] w-full overflow-hidden bg-[var(--background)] relative">
      {/* Settings Overlay */}
      {showSettings && (
        <SettingsOverlay
          fontSize={fontSize}
          setFontSize={setFontSize}
          displayMode={displayMode}
          setDisplayMode={updateDisplayMode}
          prefetchEnabled={prefetchEnabled}
          setPrefetchEnabled={setPrefetchEnabled}
          prefetchCount={prefetchCount}
          setPrefetchCount={setPrefetchCount}
          prefetchMode={prefetchMode}
          setPrefetchMode={setPrefetchMode}
          alwaysHideThoughts={alwaysHideThoughts}
          setAlwaysHideThoughts={setAlwaysHideThoughts}
          onClose={() => setShowSettings(false)}
          mobileMode={!showChapterList}
          threadId={threadId}
          offlineThread={thread}
          offlineStartIndex={selectedChapterIdx}
        />
      )}

      {/* Header Bar — overlays the reader (out of flow) so hiding it never moves the text */}
      <div
        className={`flex items-center gap-2 sm:gap-4 px-3 sm:px-6 border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-md z-30 transition-all duration-300 ease-in-out ${
          showChapterList ? "" : "absolute inset-x-0 top-0"
        } ${
          showChapterList || controlsVisible
            ? "h-16 py-4 border-b opacity-100"
            : "h-0 py-0 border-b-0 opacity-0 overflow-hidden pointer-events-none"
        }`}
      >
        <button
          onClick={onBack}
          aria-label="Kembali ke Library"
          title="Kembali ke Library"
          className="p-1.5 sm:p-2 hover:bg-[var(--secondary)] rounded-full transition-all active:scale-95 border-none bg-transparent cursor-pointer shrink-0"
        >
          <ArrowLeft className="w-5 h-5 text-[var(--foreground)]" />
        </button>
        <div className="flex-1 min-w-0 text-left">
          <h1 className="text-sm md:text-lg font-bold truncate tracking-tight">
            {thread.title}
          </h1>
          <p className="text-[10px] text-[var(--muted-foreground)] font-medium uppercase tracking-widest flex items-center gap-2 min-w-0">
            {isOffline && (
              // Before the truncating text + shrink-0 so it is never clipped on narrow phones;
              // amber-800 on light themes keeps contrast >= 4.5:1, amber-400 on dark ones.
              <span
                className="shrink-0 flex items-center gap-1 rounded-full px-1.5 py-0.5 bg-amber-500/15 text-amber-400 [:root[data-theme=white]_&]:text-amber-800 [:root[data-theme=sepia]_&]:text-amber-800"
                title="Server tidak terjangkau — membaca dari cache perangkat"
                role="status"
              >
                <WifiOff className="w-2.5 h-2.5" />
                Offline
              </span>
            )}
            {/* On the narrowest phones the Offline badge takes this line's room; hide the count there */}
            <span className={`truncate min-w-0 ${isOffline ? "max-[359px]:hidden" : ""}`}>
              {thread.chapter_count} chapters • {thread.source_type}
            </span>
            {isTranslatingTitles && (
              <span className="flex items-center gap-1 text-[var(--accent)] animate-pulse">
                <Loader2 className="w-2.5 h-2.5 animate-spin" />
                Polishing...
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          {showChapterList && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => runCleanerTool("txt-cleaner")}
                className="rounded-xl border-[var(--border)] hidden sm:inline-flex"
                title="TXT Cleaner"
              >
                <Eraser className="w-4 h-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => runCleanerTool("epub-cleaner")}
                className="rounded-xl border-[var(--border)] hidden sm:inline-flex"
                title="EPUB Cleaner"
              >
                <Wand2 className="w-4 h-4" />
              </Button>
            </>
          )}
          {!showChapterList && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleSaveTranslation}
              className="rounded-xl border-[var(--border)] flex gap-1.5 px-2.5 sm:px-3"
              title="Save Translation"
            >
              <Save className="w-4 h-4" />
              <span className="hidden sm:inline">Save</span>
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsBulkModalOpen(true)}
            className="rounded-xl border-[var(--border)] text-[var(--accent)] hover:bg-[var(--accent)]/10"
            title="Batch Translate"
            aria-label="Batch Translate"
          >
            <Sparkles className="w-4 h-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsExportModalOpen(true)}
            className="rounded-xl border-[var(--border)]"
            aria-label="Export buku"
            title="Export buku"
          >
            <Download className="w-4 h-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowSettings(!showSettings)}
            className="rounded-xl border-[var(--border)]"
            aria-label="Pengaturan reader"
            aria-expanded={showSettings}
            title="Pengaturan reader"
          >
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div
        className={`flex-1 bg-[var(--background)] custom-scrollbar ${showChapterList ? "overflow-auto" : "overflow-hidden"}`}
        ref={scrollRef}
      >
        {showChapterList ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 text-left pb-16">
            <NovelHeader
              thread={thread}
              onReadNow={() => {
                const startIdx = thread.chapters.findIndex(
                  (ch) => ch.id === lastReadId
                );
                goToChapter(startIdx !== -1 ? startIdx : 0);
              }}
              onOpenBulkModal={() => setIsBulkModalOpen(true)}
              onOpenFetchModal={() => {
                setBulkFetchInitialTab("missing");
                setIsFetchModalOpen(true);
              }}
            />

            <ChapterListControls
              thread={thread}
              chapterFilter={chapterFilter}
              setChapterFilter={setChapterFilter}
              sortOrder={sortOrder}
              setSortOrder={setSortOrder}
              chapterSearch={chapterSearch}
              setChapterSearch={setChapterSearch}
              targetLanguage={globalSettings.target_language || "Indonesian"}
              handlePolishLanguageChange={handlePolishLanguageChange}
              polishMode={polishMode}
              handlePolishModeChange={handlePolishModeChange}
              polishSoftLimit={polishSoftLimit}
              handlePolishLimitChange={handlePolishLimitChange}
              autoDetectStart={autoDetectStart}
              setAutoDetectStart={setAutoDetectStart}
              manualStartNum={manualStartNum}
              setManualStartNum={setManualStartNum}
              volumeMode={volumeMode}
              setVolumeMode={setVolumeMode}
              autoDetectVolume={autoDetectVolume}
              setAutoDetectVolume={setAutoDetectVolume}
              manualStartVolume={manualStartVolume}
              setManualStartVolume={setManualStartVolume}
              volumeBoundaries={volumeBoundaries}
              setVolumeBoundaries={setVolumeBoundaries}
              volumeBoundaryType={volumeBoundaryType}
              setVolumeBoundaryType={setVolumeBoundaryType}
              chaptersPerVolume={chaptersPerVolume}
              setChaptersPerVolume={setChaptersPerVolume}
              isTranslatingTitles={isTranslatingTitles}
              handleTranslateTitles={handleTranslateTitles}
              getAutoStartNum={getAutoStartNum}
              onOpenFidelityModal={() => setIsFidelityModalOpen(true)}
            />

            {chapterFilter === "images" ? (
              <ThreadImageGallery
                threadId={thread.id}
                chapterSearch={chapterSearch}
                onSelectChapter={(chapterId) => {
                  const idx = thread.chapters.findIndex(
                    (ch) => ch.id === chapterId
                  );
                  if (idx !== -1) goToChapter(idx);
                }}
              />
            ) : (
              <ChapterGrid
                thread={thread}
                chapterSearch={chapterSearch}
                chapterFilter={chapterFilter}
                sortOrder={sortOrder}
                lastReadId={lastReadId}
                isTranslatingTitles={isTranslatingTitles}
                goToChapter={goToChapter}
                handleSingleTitlePolish={handleSingleTitlePolish}
                handleDeleteChapter={handleDeleteChapter}
              />
            )}
          </div>
        ) : (
          selectedChapterIdx !== null && (
            <ChapterReader
              thread={thread}
              selectedChapterIdx={selectedChapterIdx}
              setSelectedChapterIdx={setSelectedChapterIdx}
              onSelectChapter={(idx) => goToChapter(idx)}
              chapterContent={chapterContent}
              loadingContent={loadingContent}
              translatedText={translatedText}
              isTranslating={isTranslating}
              displayMode={displayMode}
              setDisplayMode={updateDisplayMode}
              fontSize={fontSize}
              setFontSize={setFontSize}
              handleTranslateChapter={handleTranslateChapter}
              setShowChapterList={setShowChapterList}
              alwaysHideThoughts={alwaysHideThoughts}
              setAlwaysHideThoughts={setAlwaysHideThoughts}
              controlsVisible={controlsVisible}
              setControlsVisible={setControlsVisible}
              mobileToolbarVisible={mobileToolbarVisible}
              setMobileToolbarVisible={setMobileToolbarVisible}
              handleFetchNextChapter={handleFetchNextChapter}
              handleOpenBulkCrawl={() => {
                setBulkFetchInitialTab("crawl");
                setIsFetchModalOpen(true);
              }}
              onRefreshThread={() => fetchThread({ silent: true })}
              onOpenFidelityModal={() => setIsFidelityModalOpen(true)}
              setChapterContent={setChapterContent}
              setTranslatedText={setTranslatedText}
            />
          )
        )}
      </div>

      {/* Mobile Floating Bottom Toolbar (Only visible when reading a chapter) */}
      {!showChapterList && (
        <div
          className={`fixed bottom-0 left-0 right-0 z-40 md:hidden px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-2 transition-all duration-300 ease-in-out ${
            mobileToolbarVisible
              ? "translate-y-0 opacity-100"
              : "translate-y-28 opacity-0 pointer-events-none"
          }`}
        >
          <div className="bg-[var(--card)]/80 backdrop-blur-xl border border-[var(--border)] rounded-2xl shadow-2xl flex items-center justify-around p-2">
            <button
              onClick={() => {
                if (selectedChapterIdx !== null && selectedChapterIdx > 0) {
                  goToChapter(selectedChapterIdx - 1);
                }
              }}
              disabled={selectedChapterIdx === null || selectedChapterIdx === 0}
              className="flex flex-col items-center gap-1.5 p-3 rounded-xl transition-all duration-300 text-[var(--muted-foreground)] hover:text-[var(--foreground)] active:scale-95 disabled:opacity-30 disabled:pointer-events-none"
            >
              <ArrowLeft size={24} />
              <span className="text-[10px] font-bold uppercase tracking-widest">
                Prev
              </span>
            </button>
            <button
              onClick={() => {
                setShowChapterList(true);
                setControlsVisible(true);
                setMobileToolbarVisible(true);
              }}
              className="flex flex-col items-center gap-1.5 p-3 rounded-xl transition-all duration-300 text-[var(--muted-foreground)] hover:text-[var(--foreground)] active:scale-95"
            >
              <Layout size={24} />
              <span className="text-[10px] font-bold uppercase tracking-widest">
                List
              </span>
            </button>
            <button
              onClick={() => {
                setShowSettings(true);
                setControlsVisible(true);
                setMobileToolbarVisible(true);
              }}
              className="flex flex-col items-center gap-1.5 p-3 rounded-xl transition-all duration-300 text-[var(--muted-foreground)] hover:text-[var(--foreground)] active:scale-95"
            >
              <Settings size={24} />
              <span className="text-[10px] font-bold uppercase tracking-widest">
                Settings
              </span>
            </button>
            <button
              onClick={() => {
                if (
                  selectedChapterIdx !== null &&
                  thread &&
                  selectedChapterIdx < thread.chapters.length - 1
                ) {
                  goToChapter(selectedChapterIdx + 1);
                }
              }}
              disabled={
                selectedChapterIdx === null ||
                !thread ||
                selectedChapterIdx >= thread.chapters.length - 1
              }
              className="flex flex-col items-center gap-1.5 p-3 rounded-xl transition-all duration-300 text-[var(--muted-foreground)] hover:text-[var(--foreground)] active:scale-95 disabled:opacity-30 disabled:pointer-events-none"
            >
              <ArrowLeft size={24} className="rotate-180" />
              <span className="text-[10px] font-bold uppercase tracking-widest">
                Next
              </span>
            </button>
          </div>
        </div>
      )}

      {/* Export Modal */}
      <ExportModal
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        threadId={threadId}
        threadTitle={thread.title}
        threadAuthor={thread.author || undefined}
        currentCover={thread.cover_image || null}
        chapters={thread.chapters}
      />

      {thread && (
        <BulkTranslateModal
          isOpen={isBulkModalOpen}
          onClose={() => setIsBulkModalOpen(false)}
          threadId={threadId}
          threadTitle={thread.title}
          chapters={thread.chapters}
          onStartBatch={handleStartBatch}
          onSuccess={() => fetchThread({ silent: true })}
        />
      )}

      <BulkFetchModal
        isOpen={isFetchModalOpen}
        onClose={() => setIsFetchModalOpen(false)}
        threadId={threadId}
        threadTitle={thread?.title || ""}
        chapters={thread?.chapters || []}
        onStartBatch={handleStartBulkFetch}
        onCrawlSuccess={() => fetchThread({ silent: true })}
        initialTab={bulkFetchInitialTab}
      />

      {thread && (
        <FidelityManagementModal
          isOpen={isFidelityModalOpen}
          onClose={() => setIsFidelityModalOpen(false)}
          threadId={threadId}
          threadTitle={thread.title}
          onRefresh={() => fetchThread({ silent: true })}
          onOpenReader={(chapterId) => {
            const idx = thread.chapters.findIndex((c) => c.id === chapterId);
            if (idx !== -1) {
              goToChapter(idx);
            }
          }}
        />
      )}
    </div>
  );
}
