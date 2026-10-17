import { useState, useRef, useEffect, useMemo } from "react";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  Info,
  Loader2,
  Sparkles,
  Languages,
  ArrowUp,
  Star,
  CloudDownload,
  Menu,
  X,
  Search,
  Palette,
  RefreshCw,
  BookOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  getApiUrl,
  getActiveWorkspace,
  invalidateThreadCache,
} from "@/lib/api";
import { renderMarkdown, cn } from "@/lib/utils";
import { toast } from "sonner";
import type { ThreadDetail, ChapterContent } from "./types";

function cleanThoughts(text: string | null | undefined): string {
  if (!text) return "";

  // 1. Strip fully enclosed <think>...</think> and <thought>...</thought> (case-insensitive)
  let cleaned = text.replace(/<(think|thought)\b[^>]*>[\s\S]*?<\/\1>/gi, "");

  // 2. Remove unclosed trailing <think> or <thought> tags
  cleaned = cleaned.replace(/<(think|thought)\b[^>]*>[\s\S]*$/gi, "");

  return cleaned;
}

interface ChapterReaderProps {
  thread: ThreadDetail;
  selectedChapterIdx: number;
  setSelectedChapterIdx: (idx: number) => void;
  onSelectChapter?: (idx: number) => void;
  chapterContent: ChapterContent | null;
  loadingContent: boolean;
  translatedText: string;
  isTranslating: boolean;
  displayMode: string;
  setDisplayMode: (mode: string) => void;
  fontSize: number;
  setFontSize?: (size: number | ((prev: number) => number)) => void;
  handleTranslateChapter: (
    isResume: boolean,
    initialText: string,
    overrideContent?: string,
    overrideId?: number,
    forceOverwrite?: boolean
  ) => Promise<void>;
  setShowChapterList: (show: boolean) => void;
  alwaysHideThoughts: boolean;
  setAlwaysHideThoughts: (val: boolean) => void;
  controlsVisible: boolean;
  setControlsVisible: (val: boolean | ((prev: boolean) => boolean)) => void;
  mobileToolbarVisible: boolean;
  setMobileToolbarVisible: (
    val: boolean | ((prev: boolean) => boolean)
  ) => void;
  handleFetchNextChapter?: () => Promise<void>;
  handleOpenBulkCrawl?: () => void;
  onRefreshThread?: () => void;
  onOpenFidelityModal?: () => void;
  setChapterContent?: React.Dispatch<
    React.SetStateAction<ChapterContent | null>
  >;
  setTranslatedText?: (text: string) => void;
}

export default function ChapterReader({
  thread,
  selectedChapterIdx,
  setSelectedChapterIdx,
  onSelectChapter,
  chapterContent,
  loadingContent,
  translatedText,
  isTranslating,
  displayMode,
  setDisplayMode,
  fontSize,
  setFontSize,
  handleTranslateChapter,
  setShowChapterList,
  alwaysHideThoughts,
  setAlwaysHideThoughts,
  controlsVisible,
  setControlsVisible,
  mobileToolbarVisible,
  setMobileToolbarVisible,
  handleFetchNextChapter,
  handleOpenBulkCrawl,
  onRefreshThread,
  onOpenFidelityModal,
  setChapterContent,
  setTranslatedText,
}: ChapterReaderProps) {
  const showOriginal = displayMode === "both" || displayMode === "original";
  const showTranslated = displayMode === "both" || displayMode === "translated";

  const [isBookmarked, setIsBookmarked] = useState(
    chapterContent?.is_bookmarked || false
  );
  const [prevChapterContent, setPrevChapterContent] = useState(chapterContent);
  const [isTocOpen, setIsTocOpen] = useState(false);
  const [tocSearch, setTocSearch] = useState("");
  const activeChapterItemRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isTocOpen) {
      requestAnimationFrame(() => {
        activeChapterItemRef.current?.scrollIntoView({
          block: "center",
          behavior: "instant" as ScrollBehavior,
        });
      });
    }
  }, [isTocOpen]);
  const [isAppearanceOpen, setIsAppearanceOpen] = useState(false);
  const [currentTheme, setCurrentTheme] = useState(
    () => localStorage.getItem("theme") || "sepia"
  );
  const [fontFamily, setFontFamily] = useState<"serif" | "sans" | "mono">(
    () => {
      const saved = localStorage.getItem("reader_font_family");
      return saved === "sans" || saved === "mono" ? saved : "serif";
    }
  );
  const [lineHeight, setLineHeight] = useState<number>(
    () => Number(localStorage.getItem("reader_line_height")) || 1.8
  );

  if (chapterContent !== prevChapterContent) {
    setIsBookmarked(chapterContent?.is_bookmarked || false);
    setPrevChapterContent(chapterContent);
  }

  const handleDismissWarning = async () => {
    if (!chapterContent?.id || !thread?.id) return;
    try {
      const res = await fetch(
        getApiUrl(
          `/api/threads/${thread.id}/chapters/${chapterContent.id}/dismiss-fidelity`
        ),
        {
          method: "POST",
        }
      );
      if (!res.ok) throw new Error("Gagal mengabaikan");
      invalidateThreadCache(thread.id, chapterContent.id);
      toast.success("Peringatan fidelity berhasil diabaikan");
      if (setChapterContent) {
        setChapterContent((prev) =>
          prev ? { ...prev, fidelity_warning: null } : null
        );
      }
      if (onRefreshThread) onRefreshThread();
    } catch (err) {
      console.error(err);
      toast.error("Gagal mengabaikan peringatan");
    }
  };

  const handleRetranslateCurrent = async () => {
    if (!chapterContent?.id || !thread?.id) return;
    try {
      const res = await fetch(
        getApiUrl(
          `/api/threads/${thread.id}/chapters/${chapterContent.id}/retranslate-fidelity`
        ),
        {
          method: "POST",
        }
      );
      if (!res.ok) throw new Error("Gagal");
      invalidateThreadCache(thread.id, chapterContent.id);
      toast.success("Bab telah masuk antrean perbaikan terjemahan");
      if (setChapterContent) {
        setChapterContent((prev) =>
          prev
            ? {
                ...prev,
                fidelity_warning: null,
                translation_status: "translating",
              }
            : null
        );
      }
      if (onRefreshThread) onRefreshThread();
    } catch (err) {
      console.error(err);
      toast.error("Gagal memulai perbaikan");
    }
  };

  const [isReapplyingGlossary, setIsReapplyingGlossary] = useState(false);

  const handleReapplyGlossary = async () => {
    if (!chapterContent?.id || !thread?.id) return;
    setIsReapplyingGlossary(true);
    try {
      const res = await fetch(
        getApiUrl(
          `/api/threads/${thread.id}/chapters/${chapterContent.id}/reapply-glossary`
        ),
        {
          method: "POST",
        }
      );
      if (!res.ok) throw new Error("Gagal menyinkronkan");
      const data = await res.json();
      if (data.content_translated) {
        invalidateThreadCache(thread.id, chapterContent.id);
        if (setChapterContent) {
          setChapterContent((prev) =>
            prev
              ? { ...prev, content_translated: data.content_translated }
              : null
          );
        }
        if (setTranslatedText) {
          setTranslatedText(data.content_translated);
        }
        toast.success("Glosarium bab ini berhasil disinkronkan! (0 token)");
      } else {
        toast.info("Tidak ada perubahan glosarium pada teks ini");
      }
    } catch (err) {
      console.error(err);
      toast.error("Gagal menerapkan glosarium");
    } finally {
      setIsReapplyingGlossary(false);
    }
  };

  const toggleBookmark = async () => {
    if (!chapterContent) return;
    try {
      const res = await fetch(
        getApiUrl(
          `/api/threads/${thread.id}/chapters/${chapterContent.id}/bookmark`
        ),
        {
          method: "PUT",
        }
      );
      if (res.ok) {
        setIsBookmarked(!isBookmarked);
      }
    } catch (err) {
      console.error("Failed to toggle bookmark:", err);
    }
  };

  // PERFORMANCE FIX: Use refs for scroll progress to avoid re-rendering huge HTML chunks
  const scrollProgressRef = useRef(0);
  const progressCircleRef = useRef<SVGCircleElement>(null);
  const progressTextRef = useRef<HTMLSpanElement>(null);
  const scrollBtnRef = useRef<HTMLButtonElement>(null);
  const saveProgressTimeout = useRef<ReturnType<typeof setTimeout> | null>(
    null
  );
  const controlsVisibleRef = useRef(controlsVisible);
  const mobileToolbarVisibleRef = useRef(mobileToolbarVisible);
  const loadingContentRef = useRef(loadingContent);

  useEffect(() => {
    loadingContentRef.current = loadingContent;
  }, [loadingContent]);

  // Helper tunggal untuk mengatur visibilitas tombol mengambang Scroll-to-Top:
  // HANYA tampil jika navbar terlihat (bukan mode immersive) DAN posisi baca > 8%.
  // Mencegah jempol kanan tidak sengaja menekan tombol ini saat slide di pojok kanan bawah!
  const syncScrollButtonVisibility = (
    pct: number,
    isControlsShown: boolean
  ) => {
    if (!scrollBtnRef.current) return;
    if (isControlsShown && pct > 8) {
      scrollBtnRef.current.classList.remove(
        "translate-y-28",
        "opacity-0",
        "scale-75",
        "pointer-events-none"
      );
      scrollBtnRef.current.classList.add(
        "translate-y-0",
        "opacity-100",
        "scale-100"
      );
    } else {
      scrollBtnRef.current.classList.add(
        "translate-y-28",
        "opacity-0",
        "scale-75",
        "pointer-events-none"
      );
      scrollBtnRef.current.classList.remove(
        "translate-y-0",
        "opacity-100",
        "scale-100"
      );
    }
  };

  useEffect(() => {
    controlsVisibleRef.current = controlsVisible;
    mobileToolbarVisibleRef.current = mobileToolbarVisible;
    syncScrollButtonVisibility(
      scrollProgressRef.current,
      controlsVisible || mobileToolbarVisible
    );
  }, [controlsVisible, mobileToolbarVisible]);

  // Refs untuk scroll containers & cumulative directional physics
  const originalScrollContainerRef = useRef<HTMLDivElement>(null);
  const translatedScrollContainerRef = useRef<HTMLDivElement>(null);
  const lastScrollTopOriginal = useRef(0);
  const lastScrollTopTranslated = useRef(0);
  const lastWindowScrollTop = useRef(0);

  const scrollRafOriginalId = useRef<number | null>(null);
  const scrollRafTranslatedId = useRef<number | null>(null);
  const scrollRafWindowId = useRef<number | null>(null);

  // Cumulative scroll delta & gesture protection refs
  const accumulatedDeltaRef = useRef(0);
  const lastControlsToggleTimeRef = useRef(0);
  const lastScrollEventTimeRef = useRef(0);
  const userInteractedRef = useRef(false);
  const pointerStartRef = useRef<{
    x: number;
    y: number;
    time: number;
    scrollTop: number;
    moved: boolean;
    wasScrolling: boolean;
  } | null>(null);

  const lastSavedScrollTopRef = useRef<number | null>(null);
  const prevChapterIdRef = useRef<number | null>(null);

  const getScrollStorageKey = (chapterId: number) =>
    `readomni_scroll_${getActiveWorkspace()}_${thread.id}_${chapterId}`;

  const saveScrollPosition = (pct: number, top?: number) => {
    if (!chapterContent || loadingContentRef.current) return;
    const key = getScrollStorageKey(chapterContent.id);
    try {
      localStorage.setItem(key, JSON.stringify({ pct, top, ts: Date.now() }));
    } catch {
      /* ignore */
    }
  };

  // Shared DOM update logic
  const updateScrollUI = (
    pct: number,
    scrollTop?: number,
    shouldPersist: boolean = true
  ) => {
    scrollProgressRef.current = pct;
    if (scrollTop !== undefined) {
      lastSavedScrollTopRef.current = scrollTop;
    }

    if (
      shouldPersist &&
      chapterContent &&
      !loadingContentRef.current &&
      pct >= 0
    ) {
      saveScrollPosition(
        pct,
        scrollTop ?? lastSavedScrollTopRef.current ?? undefined
      );
    }

    if (progressCircleRef.current) {
      progressCircleRef.current.style.strokeDashoffset = `${163.4 - (pct / 100) * 163.4}`;
    }
    if (progressTextRef.current) {
      progressTextRef.current.innerText = `${Math.round(pct)}%`;
    }
    if (scrollBtnRef.current) {
      scrollBtnRef.current.style.borderRadius = `${Math.min(50, 16 + (pct / 100) * 34)}%`;
      scrollBtnRef.current.title = `Scroll to Top (${Math.round(pct)}%)`;
      syncScrollButtonVisibility(
        pct,
        controlsVisibleRef.current || mobileToolbarVisibleRef.current
      );
    }

    // Debounced API save
    if (shouldPersist && !loadingContentRef.current) {
      if (saveProgressTimeout.current)
        clearTimeout(saveProgressTimeout.current);
      saveProgressTimeout.current = setTimeout(() => {
        if (chapterContent && !loadingContentRef.current && pct > 0) {
          fetch(
            getApiUrl(
              `/api/threads/${thread.id}/chapters/${chapterContent.id}/progress`
            ),
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ scroll_progress: pct }),
            }
          ).catch((err) =>
            console.error("Failed to save scroll progress", err)
          );
        }
      }, 1000);
    }
  };

  // Cumulative Directional Scroll Evaluators (Anti-Bounce / Anti-Mental)
  const evaluateDirectionalScroll = (
    scrollTop: number,
    scrollHeight: number,
    delta: number
  ) => {
    const now = Date.now();
    lastScrollEventTimeRef.current = now;

    // 1. Cooldown guard: ignore synthetic scroll shifts during 380ms header height animation
    if (now - lastControlsToggleTimeRef.current < 380) {
      accumulatedDeltaRef.current = 0;
      return;
    }

    // 2. Always show controls at the very top of the chapter
    if (scrollTop < 24) {
      accumulatedDeltaRef.current = 0;
      if (!controlsVisibleRef.current || !mobileToolbarVisibleRef.current) {
        lastControlsToggleTimeRef.current = now;
        setControlsVisible(true);
        setMobileToolbarVisible(true);
      }
      return;
    }

    // 3. Ignore bottom rubber-band / overscroll bounce zone
    if (scrollHeight > 0 && scrollHeight - scrollTop < 48 && delta < 0) {
      return;
    }

    // 4. Ignore sub-pixel / touch-release micro-jitter (< 3px per frame)
    if (Math.abs(delta) < 3) {
      return;
    }

    // 5. Reset accumulator if user reverses scroll direction
    if (
      (delta > 0 && accumulatedDeltaRef.current < 0) ||
      (delta < 0 && accumulatedDeltaRef.current > 0)
    ) {
      accumulatedDeltaRef.current = 0;
    }

    accumulatedDeltaRef.current += delta;

    // 6. Hysteresis thresholds:
    // - Hide controls after cumulative 45px downward scroll
    // - Show controls ONLY after deliberate cumulative 75px upward scroll
    if (
      accumulatedDeltaRef.current > 45 &&
      (controlsVisibleRef.current || mobileToolbarVisibleRef.current)
    ) {
      accumulatedDeltaRef.current = 0;
      lastControlsToggleTimeRef.current = now;
      setControlsVisible(false);
      setMobileToolbarVisible(false);
    } else if (
      accumulatedDeltaRef.current < -75 &&
      (!controlsVisibleRef.current || !mobileToolbarVisibleRef.current)
    ) {
      accumulatedDeltaRef.current = 0;
      lastControlsToggleTimeRef.current = now;
      setControlsVisible(true);
      setMobileToolbarVisible(true);
    }
  };

  const handleScrollOriginal = (e: React.UIEvent<HTMLDivElement>) => {
    if (loadingContentRef.current) return;
    if (scrollRafOriginalId.current !== null) return;
    const target = e.currentTarget;
    const scrollTop = target.scrollTop;
    const scrollHeight = target.scrollHeight - target.clientHeight;

    scrollRafOriginalId.current = requestAnimationFrame(() => {
      if (loadingContentRef.current) {
        scrollRafOriginalId.current = null;
        return;
      }
      const pct = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
      updateScrollUI(pct, scrollTop, true);

      const delta = scrollTop - lastScrollTopOriginal.current;
      evaluateDirectionalScroll(scrollTop, scrollHeight, delta);

      lastScrollTopOriginal.current = scrollTop;
      scrollRafOriginalId.current = null;
    });
  };

  const handleScrollTranslated = (e: React.UIEvent<HTMLDivElement>) => {
    if (loadingContentRef.current) return;
    if (scrollRafTranslatedId.current !== null) return;
    const target = e.currentTarget;
    const scrollTop = target.scrollTop;
    const scrollHeight = target.scrollHeight - target.clientHeight;

    scrollRafTranslatedId.current = requestAnimationFrame(() => {
      if (loadingContentRef.current) {
        scrollRafTranslatedId.current = null;
        return;
      }
      const pct = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
      updateScrollUI(pct, scrollTop, true);

      const delta = scrollTop - lastScrollTopTranslated.current;
      evaluateDirectionalScroll(scrollTop, scrollHeight, delta);

      lastScrollTopTranslated.current = scrollTop;
      scrollRafTranslatedId.current = null;
    });
  };

  // Pointer / Touch Gesture Recognizer to distinguish a true stationary tap from a slide/scroll stop
  const handleReaderPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    userInteractedRef.current = true;
    const now = Date.now();
    pointerStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      time: now,
      scrollTop: e.currentTarget.scrollTop,
      moved: false,
      wasScrolling: now - lastScrollEventTimeRef.current < 320,
    };
  };

  const handleReaderPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!pointerStartRef.current || pointerStartRef.current.moved) return;
    const dx = e.clientX - pointerStartRef.current.x;
    const dy = e.clientY - pointerStartRef.current.y;
    if (Math.hypot(dx, dy) > 8) {
      pointerStartRef.current.moved = true;
    }
  };

  const handleContentClick = (e: React.MouseEvent<HTMLDivElement>) => {
    // 1. Ignore if user is selecting text
    if (window.getSelection()?.toString()) return;

    // 2. Ignore clicks on interactive child elements (buttons, links, images, inputs)
    const targetEl = e.target as HTMLElement | null;
    if (
      targetEl?.closest(
        'button, a, input, select, textarea, label, img, [role="button"], [data-no-reader-toggle]'
      )
    ) {
      return;
    }

    const now = Date.now();
    const pStart = pointerStartRef.current;

    // 3. Ignore if container was scrolling within the last 320ms (e.g. tapping to stop momentum scroll)
    if (now - lastScrollEventTimeRef.current < 320) {
      return;
    }

    // 4. Validate pointer gesture metrics (must be a clean, short < 260ms, stationary < 8px tap)
    if (pStart) {
      const duration = now - pStart.time;
      const scrollDiff = Math.abs(e.currentTarget.scrollTop - pStart.scrollTop);
      if (
        pStart.moved ||
        pStart.wasScrolling ||
        duration > 260 ||
        scrollDiff > 2
      ) {
        return;
      }
    }

    // 5. Edge-Zone Guard: When in immersive mode (controls hidden), ignore accidental touches
    // at the very top (< 12%) or bottom (> 85%) where thumbs start a swipe gesture.
    const isCurrentlyVisible = controlsVisible || mobileToolbarVisible;
    if (!isCurrentlyVisible && window.innerHeight > 0) {
      const relY = e.clientY / window.innerHeight;
      if (relY < 0.12 || relY > 0.85) {
        return;
      }
    }

    const nextState = !isCurrentlyVisible;
    lastControlsToggleTimeRef.current = now;
    accumulatedDeltaRef.current = 0;
    setControlsVisible(nextState);
    setMobileToolbarVisible(nextState);
  };

  useEffect(() => {
    const handleWindowScroll = () => {
      if (loadingContentRef.current) return;
      if (scrollRafWindowId.current !== null) return;

      scrollRafWindowId.current = requestAnimationFrame(() => {
        if (loadingContentRef.current) {
          scrollRafWindowId.current = null;
          return;
        }
        const scrollTop =
          window.scrollY ||
          document.documentElement.scrollTop ||
          document.body.scrollTop;
        const scrollHeight =
          document.documentElement.scrollHeight - window.innerHeight;
        const pct = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;

        updateScrollUI(pct, scrollTop, true);

        const delta = scrollTop - lastWindowScrollTop.current;
        evaluateDirectionalScroll(scrollTop, scrollHeight, delta);

        lastWindowScrollTop.current = scrollTop;
        scrollRafWindowId.current = null;
      });
    };

    window.addEventListener("scroll", handleWindowScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", handleWindowScroll);
      if (scrollRafWindowId.current !== null)
        cancelAnimationFrame(scrollRafWindowId.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Save scroll position immediately on mobile screen-lock / visibility change
  useEffect(() => {
    const handlePageHide = () => {
      if (
        chapterContent &&
        !loadingContentRef.current &&
        scrollProgressRef.current > 0
      ) {
        const pct = scrollProgressRef.current;
        const top = lastSavedScrollTopRef.current ?? undefined;
        saveScrollPosition(pct, top);

        try {
          const blob = new Blob([JSON.stringify({ scroll_progress: pct })], {
            type: "application/json",
          });
          navigator.sendBeacon(
            getApiUrl(
              `/api/threads/${thread.id}/chapters/${chapterContent.id}/progress`
            ),
            blob
          );
        } catch {
          /* ignore */
        }
      }
    };

    window.addEventListener("pagehide", handlePageHide);
    document.addEventListener("visibilitychange", handlePageHide);

    return () => {
      window.removeEventListener("pagehide", handlePageHide);
      document.removeEventListener("visibilitychange", handlePageHide);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterContent, thread.id]);

  // Multi-stage Scroll Position Restoration (local storage + backend progress)
  useEffect(() => {
    if (!chapterContent) return;

    const currentId = chapterContent.id;
    const isSameChapter = prevChapterIdRef.current === currentId;
    prevChapterIdRef.current = currentId;
    userInteractedRef.current = false;
    accumulatedDeltaRef.current = 0;

    // Read saved local scroll position first (with fallback to legacy unscoped key)
    const scopedKey = getScrollStorageKey(currentId);
    const legacyKey = `readomni_scroll_${thread.id}_${currentId}`;
    let savedLocal: { pct?: number; top?: number } | null = null;
    try {
      const raw =
        localStorage.getItem(scopedKey) || localStorage.getItem(legacyKey);
      if (raw) savedLocal = JSON.parse(raw);
    } catch {
      /* ignore */
    }

    const targetPct = savedLocal?.pct ?? chapterContent.scroll_progress ?? 0;
    const targetTop = savedLocal?.top;
    const hasSavedPosition =
      (targetTop !== undefined && targetTop > 0) || targetPct > 0;

    // CRITICAL FIX: Properly reset scroll to 0 when switching to a chapter at 0%
    // (even when savedLocal has { pct: 0, top: 0 } where targetTop is 0, not undefined!)
    if (!hasSavedPosition) {
      if (!isSameChapter) {
        if (originalScrollContainerRef.current)
          originalScrollContainerRef.current.scrollTop = 0;
        if (translatedScrollContainerRef.current)
          translatedScrollContainerRef.current.scrollTop = 0;
        window.scrollTo(0, 0);
        lastScrollTopOriginal.current = 0;
        lastScrollTopTranslated.current = 0;
        lastWindowScrollTop.current = 0;
        updateScrollUI(0, 0, false);
      }
      return;
    }

    const applyScroll = () => {
      // Stop overriding scroll immediately if the user has already touched/scrolled the screen!
      if (userInteractedRef.current) return;

      if (targetTop !== undefined && targetTop > 0) {
        if (originalScrollContainerRef.current) {
          originalScrollContainerRef.current.scrollTop = targetTop;
          lastScrollTopOriginal.current = targetTop;
        }
        if (translatedScrollContainerRef.current) {
          translatedScrollContainerRef.current.scrollTop = targetTop;
          lastScrollTopTranslated.current = targetTop;
        }
        window.scrollTo(0, targetTop);
        lastWindowScrollTop.current = targetTop;
      } else if (targetPct > 0) {
        if (originalScrollContainerRef.current) {
          const el = originalScrollContainerRef.current;
          const scrollHeight = el.scrollHeight - el.clientHeight;
          if (scrollHeight > 0) {
            const nextTop = (targetPct / 100) * scrollHeight;
            el.scrollTop = nextTop;
            lastScrollTopOriginal.current = nextTop;
          }
        }
        if (translatedScrollContainerRef.current) {
          const el = translatedScrollContainerRef.current;
          const scrollHeight = el.scrollHeight - el.clientHeight;
          if (scrollHeight > 0) {
            const nextTop = (targetPct / 100) * scrollHeight;
            el.scrollTop = nextTop;
            lastScrollTopTranslated.current = nextTop;
          }
        }
        const docHeight =
          document.documentElement.scrollHeight - window.innerHeight;
        if (docHeight > 0) {
          const nextTop = (targetPct / 100) * docHeight;
          window.scrollTo(0, nextTop);
          lastWindowScrollTop.current = nextTop;
        }
      }
    };

    applyScroll();
    const t1 = setTimeout(applyScroll, 50);
    const t2 = setTimeout(applyScroll, 150);
    const t3 = setTimeout(applyScroll, 350);

    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      if (saveProgressTimeout.current)
        clearTimeout(saveProgressTimeout.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterContent?.id, thread.id]);

  const scrollToTop = () => {
    lastControlsToggleTimeRef.current = Date.now();
    accumulatedDeltaRef.current = 0;
    window.scrollTo({ top: 0, behavior: "smooth" });
    document.documentElement.scrollTo({ top: 0, behavior: "smooth" });
    document.body.scrollTo({ top: 0, behavior: "smooth" });

    if (originalScrollContainerRef.current) {
      originalScrollContainerRef.current.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    }
    if (translatedScrollContainerRef.current) {
      translatedScrollContainerRef.current.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    }
    updateScrollUI(0, 0, true);
    setControlsVisible(true);
    setMobileToolbarVisible(true);
  };

  const handlePrevChapter = () => {
    if (selectedChapterIdx > 0) {
      setControlsVisible(true);
      setMobileToolbarVisible(true);
      setSelectedChapterIdx(selectedChapterIdx - 1);
    }
  };

  const handleNextChapter = () => {
    if (selectedChapterIdx < thread.chapters.length - 1) {
      setControlsVisible(true);
      setMobileToolbarVisible(true);
      setSelectedChapterIdx(selectedChapterIdx + 1);
    }
  };

  const handleTranslateClick = () => {
    const hasTranslation =
      !!chapterContent?.content_translated || !!translatedText;
    handleTranslateChapter(false, "", undefined, undefined, hasTranslation);
  };

  const handleThemeChange = (thm: string) => {
    setCurrentTheme(thm);
    localStorage.setItem("theme", thm);
    document.documentElement.setAttribute("data-theme", thm);
  };

  const handleFontFamilyChange = (fam: "serif" | "sans" | "mono") => {
    setFontFamily(fam);
    localStorage.setItem("reader_font_family", fam);
  };

  const handleLineHeightChange = (lh: number) => {
    setLineHeight(lh);
    localStorage.setItem("reader_line_height", String(lh));
  };

  const fontClass =
    fontFamily === "serif"
      ? "font-serif"
      : fontFamily === "sans"
        ? "font-sans"
        : "font-mono";

  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable ||
          target.tagName === "SELECT")
      ) {
        if (e.key === "Escape") {
          setIsTocOpen(false);
          setIsAppearanceOpen(false);
        }
        return;
      }

      if (e.key === "Escape") {
        setIsTocOpen(false);
        setIsAppearanceOpen(false);
        return;
      }

      if (e.key === "[" || (e.altKey && e.key === "ArrowLeft")) {
        e.preventDefault();
        handlePrevChapter();
      } else if (e.key === "]" || (e.altKey && e.key === "ArrowRight")) {
        e.preventDefault();
        handleNextChapter();
      } else if (e.key === "j" || e.key === "J") {
        e.preventDefault();
        const container =
          translatedScrollContainerRef.current ||
          originalScrollContainerRef.current;
        if (container) {
          container.scrollBy({ top: 250, behavior: "smooth" });
        } else {
          window.scrollBy({ top: 250, behavior: "smooth" });
        }
      } else if (e.key === "k" || e.key === "K") {
        e.preventDefault();
        const container =
          translatedScrollContainerRef.current ||
          originalScrollContainerRef.current;
        if (container) {
          container.scrollBy({ top: -250, behavior: "smooth" });
        } else {
          window.scrollBy({ top: -250, behavior: "smooth" });
        }
      } else if (e.key === "t" || e.key === "T") {
        e.preventDefault();
        setDisplayMode(
          displayMode === "translated"
            ? "original"
            : displayMode === "original"
              ? "both"
              : "translated"
        );
      } else if (e.key === "b" || e.key === "B") {
        e.preventDefault();
        toggleBookmark();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedChapterIdx, thread.chapters?.length, displayMode, isBookmarked]);

  const filteredChapters = useMemo(() => {
    if (!thread.chapters) return [];
    const q = tocSearch.trim().toLowerCase();
    if (!q) return thread.chapters;
    return thread.chapters.filter((ch, idx) => {
      const title = (
        ch.title_translated ||
        ch.title_original ||
        ""
      ).toLowerCase();
      const num = String(idx + 1);
      return title.includes(q) || num.includes(q);
    });
  }, [thread.chapters, tocSearch]);

  const originalContentNode = useMemo(() => {
    return chapterContent?.content_original
      ? renderMarkdown(chapterContent.content_original)
      : "No original content found.";
  }, [chapterContent]);

  const currentTranslation = isTranslating
    ? translatedText
    : chapterContent?.content_translated || translatedText;
  const translatedContentNode = useMemo(() => {
    if (!currentTranslation) return null;
    return renderMarkdown(
      alwaysHideThoughts
        ? cleanThoughts(currentTranslation)
        : currentTranslation
    );
  }, [currentTranslation, alwaysHideThoughts]);

  return (
    <div className="relative max-w-screen-2xl mx-auto h-full flex flex-col">
      {/* Top Navigation — overlay (absolute, below the 4rem page header) so toggling it never moves the text */}
      <div
        className={`absolute inset-x-0 top-16 px-3 sm:px-4 md:px-6 flex items-center justify-between gap-2 border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-md transition-all duration-300 ease-in-out z-20 ${
          controlsVisible
            ? "h-14 py-3 border-b opacity-100"
            : "h-0 py-0 border-b-0 opacity-0 overflow-hidden pointer-events-none"
        }`}
      >
        <div className="flex items-center gap-1 sm:gap-2 md:gap-3 min-w-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowChapterList(true)}
            className="rounded-xl gap-1.5 text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] px-2 sm:px-2.5 h-8 shrink-0"
            title="Kembali ke Ringkasan Bab"
            aria-label="Kembali ke Ringkasan Bab"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">List</span>
          </Button>

          {/* Quick Table of Contents Drawer Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsTocOpen(true)}
            className="hidden sm:inline-flex rounded-xl gap-1.5 text-xs border-[var(--border)] bg-[var(--card)]/50 hover:bg-[var(--secondary)] text-[var(--foreground)] px-2.5 h-8 shadow-sm"
            title="Buka Daftar Isi Cepat (TOC Drawer)"
            aria-label="Buka Daftar Isi"
          >
            <Menu className="w-3.5 h-3.5 text-[var(--primary)]" />
            <span className="hidden sm:inline font-bold">Daftar Isi</span>
          </Button>

          <div className="h-4 w-px bg-[var(--border)] hidden sm:block" />

          <button
            onClick={() => setIsTocOpen(true)}
            className="text-[10px] md:text-xs font-bold tracking-tight px-1.5 py-0.5 rounded-lg hover:bg-[var(--secondary)] text-[var(--foreground)] min-w-0 max-w-[140px] sm:max-w-none overflow-hidden cursor-pointer flex items-center gap-1 transition-colors whitespace-nowrap"
            title="Pilih Bab (Table of Contents)"
            aria-label={`Bab ${selectedChapterIdx + 1} dari ${thread.chapters.length} — pilih bab`}
          >
            <span className="truncate">BAB {selectedChapterIdx + 1}</span>
            {/* The total is dropped on the narrowest phones so the label never runs under the star */}
            <span className="text-[var(--muted-foreground)] font-normal text-[9px] max-[359px]:hidden">
              / {thread.chapters.length}
            </span>
          </button>

          <button
            onClick={toggleBookmark}
            title={
              isBookmarked ? "Hapus Bookmark" : "Bookmark Bab Ini (Shortcut: B)"
            }
            aria-label={isBookmarked ? "Hapus Bookmark" : "Bookmark Bab Ini"}
            aria-pressed={isBookmarked}
            className={`p-1.5 rounded-lg transition-colors cursor-pointer shrink-0 ${
              isBookmarked
                ? "text-yellow-500 bg-yellow-500/10"
                : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]"
            }`}
          >
            <Star size={16} className={isBookmarked ? "fill-current" : ""} />
          </button>
        </div>

        {/* Reader Controls (Display Mode) */}
        <div className="flex items-center gap-0.5 sm:gap-1 bg-[var(--secondary)]/50 p-1 rounded-2xl border border-[var(--border)] shrink-0">
          <Button
            variant={displayMode === "original" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setDisplayMode("original")}
            aria-pressed={displayMode === "original"}
            className={`rounded-xl text-[10px] h-7 px-2 sm:px-3 ${displayMode === "original" ? "shadow-sm bg-[var(--background)] font-bold" : ""}`}
          >
            ORI
          </Button>
          <Button
            variant={displayMode === "translated" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setDisplayMode("translated")}
            aria-pressed={displayMode === "translated"}
            className={`rounded-xl text-[10px] h-7 px-2 sm:px-3 ${displayMode === "translated" ? "shadow-sm bg-[var(--background)] font-bold text-[var(--primary)]" : ""}`}
          >
            TRS
          </Button>
          <Button
            variant={displayMode === "both" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setDisplayMode("both")}
            aria-pressed={displayMode === "both"}
            className={`rounded-xl text-[10px] h-7 px-2 sm:px-3 ${displayMode === "both" ? "shadow-sm bg-[var(--background)] font-bold" : ""}`}
          >
            BOTH
          </Button>
        </div>

        {/* Right Controls: Appearance Popover & Chapter Navigation */}
        <div className="flex items-center gap-2 shrink-0">
          {/* In-Reader Appearance Popover Toggle */}
          <div className="relative">
            <Button
              variant={isAppearanceOpen ? "secondary" : "outline"}
              size="sm"
              onClick={() => setIsAppearanceOpen((prev) => !prev)}
              className="rounded-xl border-[var(--border)] h-8 px-2 sm:px-2.5 gap-1.5 text-xs font-bold shadow-sm"
              title="Pengaturan Tampilan & Tema (Aa)"
              aria-label="Pengaturan Tampilan & Tema"
              aria-expanded={isAppearanceOpen}
            >
              <Palette className="w-3.5 h-3.5 text-[var(--primary)]" />
              <span className="hidden sm:inline text-[11px] font-black">Aa</span>
            </Button>

            {/* Appearance Popover Menu */}
            {isAppearanceOpen && (
              <>
                <div
                  className="fixed inset-0 z-40"
                  onClick={() => setIsAppearanceOpen(false)}
                />
                <div className="absolute right-0 top-10 w-72 max-w-[calc(100vw-2rem)] p-4 rounded-3xl bg-[var(--card)]/95 backdrop-blur-2xl border border-[var(--border)] shadow-2xl z-50 animate-in fade-in slide-in-from-top-2 duration-200 space-y-4">
                  <div className="flex items-center justify-between border-b border-[var(--border)]/60 pb-2">
                    <span className="text-xs font-black uppercase tracking-wider text-[var(--foreground)] flex items-center gap-1.5">
                      <Palette size={13} className="text-[var(--primary)]" />{" "}
                      Tampilan & Tema
                    </span>
                    <button
                      onClick={() => setIsAppearanceOpen(false)}
                      className="text-[var(--muted-foreground)] hover:text-[var(--foreground)] p-1 rounded-lg"
                    >
                      <X size={14} />
                    </button>
                  </div>

                  {/* Theme Presets */}
                  <div className="space-y-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                      Tema Warna
                    </span>
                    <div className="grid grid-cols-5 gap-1.5">
                      {[
                        {
                          id: "sepia",
                          label: "Sepia",
                          bg: "#f4ecd8",
                          text: "#5f4b32",
                          border: "#e3d7bf",
                        },
                        {
                          id: "oled",
                          label: "OLED",
                          bg: "#000000",
                          text: "#e5e5e5",
                          border: "#262626",
                        },
                        {
                          id: "black",
                          label: "Obsidian",
                          bg: "#121212",
                          text: "#d4d4d4",
                          border: "#2a2a2a",
                        },
                        {
                          id: "white",
                          label: "White",
                          bg: "#ffffff",
                          text: "#171717",
                          border: "#e5e5e5",
                        },
                        {
                          id: "omni",
                          label: "Omni",
                          bg: "#0b0c16",
                          text: "#c4b5fd",
                          border: "#3b2d68",
                        },
                      ].map((t) => (
                        <button
                          key={t.id}
                          onClick={() => handleThemeChange(t.id)}
                          className={`flex flex-col items-center justify-center p-2 rounded-xl border transition-all cursor-pointer ${
                            currentTheme === t.id
                              ? "ring-2 ring-[var(--primary)] scale-105 border-transparent shadow-md"
                              : "opacity-80 hover:opacity-100 hover:scale-102"
                          }`}
                          style={{
                            backgroundColor: t.bg,
                            borderColor: t.border,
                          }}
                          title={t.label}
                        >
                          <span
                            className="text-[10px] font-black"
                            style={{ color: t.text }}
                          >
                            Aa
                          </span>
                          <span
                            className="text-[8px] font-bold mt-0.5 truncate max-w-full"
                            style={{ color: t.text }}
                          >
                            {t.label}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Font Size */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between items-center text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                      <span>Ukuran Huruf</span>
                      <span className="text-[var(--foreground)] font-mono font-black">
                        {fontSize}px
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 flex-1 rounded-xl font-bold text-xs"
                        onClick={() =>
                          setFontSize?.(Math.max(14, fontSize - 1))
                        }
                        disabled={fontSize <= 14}
                      >
                        A-
                      </Button>
                      <input
                        type="range"
                        min={14}
                        max={32}
                        value={fontSize}
                        onChange={(e) => setFontSize?.(Number(e.target.value))}
                        className="flex-1 accent-[var(--primary)] cursor-pointer"
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-8 flex-1 rounded-xl font-bold text-xs"
                        onClick={() =>
                          setFontSize?.(Math.min(32, fontSize + 1))
                        }
                        disabled={fontSize >= 32}
                      >
                        A+
                      </Button>
                    </div>
                  </div>

                  {/* Font Family */}
                  <div className="space-y-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                      Jenis Font
                    </span>
                    <div className="grid grid-cols-3 gap-1.5">
                      {[
                        {
                          id: "serif" as const,
                          label: "Serif",
                          preview: "font-serif",
                        },
                        {
                          id: "sans" as const,
                          label: "Sans",
                          preview: "font-sans",
                        },
                        {
                          id: "mono" as const,
                          label: "Mono",
                          preview: "font-mono",
                        },
                      ].map((f) => (
                        <button
                          key={f.id}
                          onClick={() => handleFontFamilyChange(f.id)}
                          className={`py-1.5 px-2 rounded-xl text-xs font-bold border transition-all cursor-pointer ${
                            fontFamily === f.id
                              ? "bg-[var(--primary)] text-white border-transparent shadow-sm"
                              : "bg-[var(--secondary)]/60 text-[var(--muted-foreground)] border-[var(--border)] hover:text-[var(--foreground)]"
                          }`}
                        >
                          <span className={f.preview}>{f.label}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Line Height */}
                  <div className="space-y-1.5">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                      Kerapatan Baris
                    </span>
                    <div className="grid grid-cols-3 gap-1.5">
                      {[
                        { val: 1.5, label: "Rapat" },
                        { val: 1.8, label: "Normal" },
                        { val: 2.2, label: "Renggang" },
                      ].map((lh) => (
                        <button
                          key={lh.val}
                          onClick={() => handleLineHeightChange(lh.val)}
                          className={`py-1.5 px-2 rounded-xl text-xs font-bold border transition-all cursor-pointer ${
                            Math.abs(lineHeight - lh.val) < 0.05
                              ? "bg-[var(--primary)] text-white border-transparent shadow-sm"
                              : "bg-[var(--secondary)]/60 text-[var(--muted-foreground)] border-[var(--border)] hover:text-[var(--foreground)]"
                          }`}
                        >
                          {lh.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Hotkey hint */}
                  <div className="pt-2 border-t border-[var(--border)]/40 text-[9px] text-[var(--muted-foreground)] text-center leading-relaxed">
                    Shortcut:{" "}
                    <kbd className="px-1 py-0.5 rounded bg-[var(--secondary)] font-mono">
                      J
                    </kbd>
                    /
                    <kbd className="px-1 py-0.5 rounded bg-[var(--secondary)] font-mono">
                      K
                    </kbd>{" "}
                    scroll,{" "}
                    <kbd className="px-1 py-0.5 rounded bg-[var(--secondary)] font-mono">
                      [
                    </kbd>
                    /
                    <kbd className="px-1 py-0.5 rounded bg-[var(--secondary)] font-mono">
                      ]
                    </kbd>{" "}
                    bab
                  </div>
                </div>
              </>
            )}
          </div>

          <Button
            variant="outline"
            size="icon"
            className="rounded-xl border-[var(--border)] h-8 w-8 hidden md:inline-flex"
            onClick={handlePrevChapter}
            disabled={selectedChapterIdx === 0}
            title="Bab Sebelumnya (Shortcut: [ )"
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <button
            onClick={() => setIsTocOpen(true)}
            className="hidden md:inline-flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold border border-[var(--border)] bg-[var(--card)]/50 hover:bg-[var(--secondary)] text-[var(--foreground)] transition-all cursor-pointer shadow-sm"
            title="Pilih Bab (Table of Contents)"
          >
            <BookOpen className="w-3.5 h-3.5 text-[var(--primary)]" />
            <span className="font-mono">
              {selectedChapterIdx + 1} / {thread.chapters.length}
            </span>
          </button>
          <Button
            variant="outline"
            size="icon"
            className="rounded-xl border-[var(--border)] h-8 w-8 hidden md:inline-flex"
            onClick={handleNextChapter}
            disabled={selectedChapterIdx === thread.chapters.length - 1}
            title="Bab Selanjutnya (Shortcut: ] )"
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Reader Grid */}
      <div
        className={cn(
          "flex-1 overflow-hidden",
          displayMode === "both"
            ? "grid grid-cols-1 md:grid-cols-2 gap-0 divide-y md:divide-y-0 md:divide-x divide-[var(--border)]"
            : "flex flex-col"
        )}
      >
        {/* Original Content */}
        {showOriginal && (
          <div className="relative flex flex-col h-full overflow-hidden bg-[var(--secondary)]/10">
            <div
              className={`absolute inset-x-0 top-[7.5rem] z-10 backdrop-blur-md px-3 sm:px-6 flex items-center justify-between gap-2 border-[var(--border)] bg-[var(--background)]/50 transition-all duration-300 ease-in-out ${
                controlsVisible
                  ? "h-10 py-3 border-b opacity-100"
                  : "h-0 py-0 border-b-0 opacity-0 overflow-hidden pointer-events-none"
              }`}
            >
              <span className="text-[10px] font-black uppercase tracking-widest text-[var(--muted-foreground)]">
                Source Content
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 rounded-lg text-[var(--muted-foreground)]"
              >
                <Info className="w-3 h-3" />
              </Button>
            </div>
            <div
              ref={originalScrollContainerRef}
              className={`flex-1 overflow-auto overscroll-contain [overflow-anchor:auto] px-4 pt-[11.5rem] pb-6 md:px-10 md:pt-[12.5rem] md:pb-10 select-text ${fontClass}`}
              style={{ fontSize: `${fontSize}px`, lineHeight }}
              onScroll={handleScrollOriginal}
              onPointerDown={handleReaderPointerDown}
              onPointerMove={handleReaderPointerMove}
              onWheel={() => {
                userInteractedRef.current = true;
              }}
              onClick={handleContentClick}
            >
              {loadingContent ? (
                <div className="flex flex-col items-center justify-center h-full gap-2 opacity-30">
                  <Loader2 className="w-6 h-6 animate-spin" />
                  <span className="text-xs uppercase tracking-widest font-bold">
                    Summoning text...
                  </span>
                </div>
              ) : (
                <>
                  <div className="whitespace-pre-wrap">
                    {originalContentNode}
                  </div>
                  <div className="py-12 flex flex-col items-center justify-center gap-6 text-center mt-8">
                    <div className="flex items-center gap-4 w-full max-w-xs px-6 opacity-60">
                      <div className="h-px bg-gradient-to-r from-transparent to-[var(--border)] flex-1" />
                      <span className="text-[9px] font-black uppercase tracking-widest text-[var(--muted-foreground)] font-sans">
                        End of Chapter
                      </span>
                      <div className="h-px bg-gradient-to-l from-transparent to-[var(--border)] flex-1" />
                    </div>

                    {selectedChapterIdx < thread.chapters.length - 1 ? (
                      <Button
                        variant="outline"
                        className="rounded-full px-8 py-6 text-sm font-bold shadow-sm hover:bg-[var(--primary)] hover:text-[var(--primary-foreground)] hover:border-transparent transition-all duration-300 group"
                        onClick={handleNextChapter}
                      >
                        Next Chapter{" "}
                        <ChevronRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                      </Button>
                    ) : chapterContent?.source_url ? (
                      <div className="flex flex-wrap items-center justify-center gap-3">
                        {handleFetchNextChapter && (
                          <Button
                            variant="default"
                            className="rounded-full px-6 py-6 text-sm font-bold shadow-lg shadow-[var(--primary)]/20 hover:scale-105 active:scale-95 transition-all duration-300 group"
                            onClick={handleFetchNextChapter}
                          >
                            <Sparkles className="w-4 h-4 mr-2" />
                            Fetch Next Web Chapter
                          </Button>
                        )}
                        {handleOpenBulkCrawl && (
                          <Button
                            variant="outline"
                            className="rounded-full px-5 py-6 text-sm font-bold border-blue-500/30 text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 hover:text-blue-300 hover:border-blue-500/50 shadow-md transition-all duration-300 group"
                            onClick={handleOpenBulkCrawl}
                            title="Crawl multiple upcoming chapters sequentially from web source"
                          >
                            <CloudDownload className="w-4 h-4 mr-2 text-blue-400" />
                            ⚡ Bulk Crawl (+10)
                          </Button>
                        )}
                      </div>
                    ) : (
                      <div className="w-1.5 h-1.5 rounded-full bg-[var(--primary)] opacity-40 shadow-[0_0_8px_rgba(var(--primary-rgb),0.5)]" />
                    )}
                  </div>
                  {/* Bottom spacer to ensure smooth scrolling past content */}
                  <div className="h-20" />
                </>
              )}
            </div>
          </div>
        )}

        {/* Translated Content */}
        {showTranslated && (
          <div className="relative flex flex-col h-full overflow-hidden">
            <div
              className={`absolute inset-x-0 top-[7.5rem] z-10 backdrop-blur-md px-3 sm:px-6 flex items-center justify-between gap-2 border-[var(--border)] bg-[var(--background)]/50 transition-all duration-300 ease-in-out ${
                controlsVisible
                  ? "h-10 py-3 border-b opacity-100"
                  : "h-0 py-0 border-b-0 opacity-0 overflow-hidden pointer-events-none"
              }`}
            >
              <span className="hidden sm:inline text-[10px] font-black uppercase tracking-widest text-[var(--accent)]">
                AI Translation
              </span>
              <div className="flex items-center gap-2 sm:gap-3 ml-auto min-w-0">
                <label className="flex items-center gap-1.5 text-[10px] font-bold text-[var(--muted-foreground)] cursor-pointer select-none hover:text-[var(--foreground)] transition-colors">
                  <input
                    type="checkbox"
                    checked={alwaysHideThoughts}
                    onChange={async (e) => {
                      const checked = e.target.checked;
                      setAlwaysHideThoughts(checked);
                      try {
                        await fetch(getApiUrl("/api/settings"), {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({
                            always_hide_thoughts: checked ? 1 : 0,
                          }),
                        });
                      } catch (err) {
                        console.error(
                          "Failed to save always_hide_thoughts setting:",
                          err
                        );
                      }
                    }}
                    className="rounded border-[var(--border)] bg-transparent text-[var(--accent)] focus:ring-0 cursor-pointer h-3.5 w-3.5"
                  />
                  <span className="hidden sm:inline">Always Hide Thoughts</span>
                  <span className="sm:hidden">Hide Thoughts</span>
                </label>
                {(() => {
                  const hasTranslation =
                    !!chapterContent?.content_translated || !!translatedText;
                  return (
                    <div className="flex items-center gap-1.5">
                      {hasTranslation && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2.5 text-[10px] rounded-lg gap-1 border-emerald-500/30 text-emerald-500 hover:bg-emerald-500/10 hover:text-emerald-400 bg-transparent cursor-pointer"
                          onClick={handleReapplyGlossary}
                          disabled={isReapplyingGlossary || isTranslating}
                          title="Sinkronkan glosarium terbaru ke bab ini tanpa panggil AI (0 token, instan)"
                        >
                          <RefreshCw
                            className={cn(
                              "w-3 h-3",
                              isReapplyingGlossary ? "animate-spin" : ""
                            )}
                          />
                          <span className="hidden sm:inline font-bold">
                            Sync Terms
                          </span>
                        </Button>
                      )}
                      <Button
                        variant={hasTranslation ? "outline" : "default"}
                        size="sm"
                        className={`h-7 px-3 text-[10px] rounded-lg gap-1.5 ${hasTranslation ? "border border-[color-mix(in_srgb,var(--foreground)_30%,transparent)] text-[var(--foreground)] hover:bg-[color-mix(in_srgb,var(--foreground)_10%,transparent)] bg-transparent" : "shadow-lg shadow-[var(--accent)]/20"}`}
                        onClick={handleTranslateClick}
                        disabled={isTranslating}
                      >
                        {isTranslating ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Sparkles className="w-3 h-3" />
                        )}
                        {isTranslating
                          ? hasTranslation
                            ? "RE-TRANSLATING"
                            : "TRANSLATING"
                          : hasTranslation
                            ? "RE-TRANSLATE"
                            : "TRANSLATE"}
                      </Button>
                    </div>
                  );
                })()}
              </div>
            </div>
            <div
              ref={translatedScrollContainerRef}
              className={`flex-1 overflow-auto overscroll-contain [overflow-anchor:auto] px-4 pt-[11.5rem] pb-6 md:px-10 md:pt-[12.5rem] md:pb-10 bg-[var(--background)] select-text ${fontClass}`}
              style={{ fontSize: `${fontSize}px`, lineHeight }}
              onScroll={handleScrollTranslated}
              onPointerDown={handleReaderPointerDown}
              onPointerMove={handleReaderPointerMove}
              onWheel={() => {
                userInteractedRef.current = true;
              }}
              onClick={handleContentClick}
            >
              {loadingContent ? (
                <div className="flex flex-col items-center justify-center h-full gap-2 opacity-30">
                  <Loader2 className="w-6 h-6 animate-spin" />
                  <span className="text-xs uppercase tracking-widest font-bold">
                    Fetching translation...
                  </span>
                </div>
              ) : translatedText ? (
                <>
                  {chapterContent?.fidelity_warning && (
                    <div className="mb-6 p-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-400 text-xs font-sans flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-sm">
                      <div className="flex items-start gap-2.5 flex-1">
                        <span className="text-base leading-none mt-0.5">
                          ⚠️
                        </span>
                        <div className="space-y-1">
                          <span className="font-bold block uppercase tracking-wider text-[10px]">
                            Peringatan Kualitas (Fidelity Warning)
                          </span>
                          <p className="leading-normal">
                            {chapterContent.fidelity_warning}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 self-end sm:self-center flex-wrap">
                        <button
                          onClick={handleDismissWarning}
                          className="px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-background/80 hover:bg-background border border-amber-500/30 text-foreground transition-all cursor-pointer shadow-sm"
                          title="Tandai beres dan abaikan peringatan ini"
                        >
                          ✓ Abaikan
                        </button>
                        <button
                          onClick={handleRetranslateCurrent}
                          className="px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-amber-500 text-white hover:bg-amber-600 shadow-sm transition-all cursor-pointer flex items-center gap-1"
                          title="Terjemahkan ulang bab ini"
                        >
                          <Sparkles className="w-3 h-3 text-amber-100" />
                          Perbaiki
                        </button>
                        {onOpenFidelityModal && (
                          <button
                            onClick={onOpenFidelityModal}
                            className="px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-background/50 hover:bg-background border border-border text-muted-foreground hover:text-foreground transition-all cursor-pointer"
                            title="Buka Fidelity Hub untuk novel ini"
                          >
                            Kelola Semua
                          </button>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="whitespace-pre-wrap">
                    {translatedContentNode}
                  </div>
                  <div className="py-12 flex flex-col items-center justify-center gap-6 text-center mt-8">
                    <div className="flex items-center gap-4 w-full max-w-xs px-6 opacity-60">
                      <div className="h-px bg-gradient-to-r from-transparent to-[var(--border)] flex-1" />
                      <span className="text-[9px] font-black uppercase tracking-widest text-[var(--muted-foreground)] font-sans">
                        End of Chapter
                      </span>
                      <div className="h-px bg-gradient-to-l from-transparent to-[var(--border)] flex-1" />
                    </div>

                    {selectedChapterIdx < thread.chapters.length - 1 ? (
                      <Button
                        variant="outline"
                        className="rounded-full px-8 py-6 text-sm font-bold shadow-sm hover:bg-[var(--primary)] hover:text-[var(--primary-foreground)] hover:border-transparent transition-all duration-300 group"
                        onClick={handleNextChapter}
                      >
                        Next Chapter{" "}
                        <ChevronRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                      </Button>
                    ) : chapterContent?.source_url ? (
                      <div className="flex flex-wrap items-center justify-center gap-3">
                        {handleFetchNextChapter && (
                          <Button
                            variant="default"
                            className="rounded-full px-6 py-6 text-sm font-bold shadow-lg shadow-[var(--primary)]/20 hover:scale-105 active:scale-95 transition-all duration-300 group"
                            onClick={handleFetchNextChapter}
                          >
                            <Sparkles className="w-4 h-4 mr-2" />
                            Fetch Next Web Chapter
                          </Button>
                        )}
                        {handleOpenBulkCrawl && (
                          <Button
                            variant="outline"
                            className="rounded-full px-5 py-6 text-sm font-bold border-blue-500/30 text-blue-400 bg-blue-500/10 hover:bg-blue-500/20 hover:text-blue-300 hover:border-blue-500/50 shadow-md transition-all duration-300 group"
                            onClick={handleOpenBulkCrawl}
                            title="Crawl multiple upcoming chapters sequentially from web source"
                          >
                            <CloudDownload className="w-4 h-4 mr-2 text-blue-400" />
                            ⚡ Bulk Crawl (+10)
                          </Button>
                        )}
                      </div>
                    ) : (
                      <div className="w-1.5 h-1.5 rounded-full bg-[var(--primary)] opacity-40 shadow-[0_0_8px_rgba(var(--primary-rgb),0.5)]" />
                    )}
                  </div>
                  {/* Bottom spacer to ensure smooth scrolling past content */}
                  <div className="h-20" />
                </>
              ) : (
                <div className="flex flex-col items-center justify-center h-full gap-4 text-center opacity-40">
                  <Languages className="w-12 h-12" />
                  <div className="space-y-1">
                    <p className="text-sm font-bold uppercase tracking-tight">
                      No Translation Yet
                    </p>
                    <p className="text-[10px] max-w-[200px]">
                      Click the generate button above to start AI translation
                      for this chapter.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Floating Scroll-To-Top Dynamic Progress Button */}
      <button
        ref={scrollBtnRef}
        onClick={scrollToTop}
        className={`fixed right-4 md:right-6 flex items-center justify-center w-[56px] h-[56px] shadow-2xl z-50 transition-all duration-300 cursor-pointer focus:outline-none ${
          mobileToolbarVisible ? "bottom-28 md:bottom-6" : "bottom-6"
        } translate-y-28 opacity-0 scale-75 pointer-events-none hover:scale-105 active:scale-95`}
        style={{
          backgroundColor: "var(--card)",
          boxShadow: "0 8px 30px rgba(0, 0, 0, 0.25)",
          borderRadius: "16px",
        }}
        title="Scroll to Top (0%)"
      >
        <svg
          className="absolute inset-0 w-full h-full -rotate-90 pointer-events-none"
          viewBox="0 0 56 56"
        >
          <circle
            cx="28"
            cy="28"
            r="26"
            fill="transparent"
            stroke="var(--border)"
            strokeWidth="2.5"
            className="opacity-30"
          />
          <circle
            ref={progressCircleRef}
            cx="28"
            cy="28"
            r="26"
            fill="transparent"
            stroke="var(--primary)"
            strokeWidth="2.5"
            strokeDasharray={163.4}
            strokeDashoffset={163.4}
            strokeLinecap="round"
            className="transition-all duration-300 ease-out"
          />
        </svg>
        <ArrowUp className="w-5 h-5 text-[var(--foreground)] relative z-10 transition-transform duration-200" />
        <span
          ref={progressTextRef}
          className="absolute -top-1.5 -right-1.5 bg-[var(--primary)] text-[var(--primary-foreground)] text-[8px] font-bold h-4 min-w-4 px-1 flex items-center justify-center rounded-full border-2 border-[var(--background)] shadow-sm z-10"
        >
          0%
        </span>
      </button>

      {/* Slide-out Table of Contents (TOC) Drawer */}
      {isTocOpen && (
        <div className="fixed inset-0 z-50 flex animate-in fade-in duration-200">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
            onClick={() => setIsTocOpen(false)}
          />

          {/* Drawer Sidebar */}
          <div className="relative w-full max-w-sm sm:max-w-md bg-[var(--card)] border-r border-[var(--border)] shadow-2xl flex flex-col h-full z-10 animate-in slide-in-from-left duration-300">
            {/* Drawer Header */}
            <div className="p-4 border-b border-[var(--border)] flex items-center justify-between bg-[var(--card)]/90 backdrop-blur-md">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-[var(--primary)]/10 text-[var(--primary)]">
                  <Menu size={18} />
                </div>
                <div>
                  <h3 className="font-extrabold text-sm text-[var(--foreground)] tracking-tight">
                    Daftar Isi
                  </h3>
                  <p className="text-[10px] text-[var(--muted-foreground)] font-medium">
                    Total {thread.chapters.length} Bab • Bab Aktif: #
                    {selectedChapterIdx + 1}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsTocOpen(false)}
                className="p-2 rounded-xl text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)] transition-colors cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>

            {/* Search Box */}
            <div className="p-3 border-b border-[var(--border)]/60 bg-[var(--secondary)]/20">
              <div className="relative">
                <Search
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]"
                  size={14}
                />
                <input
                  type="text"
                  value={tocSearch}
                  onChange={(e) => setTocSearch(e.target.value)}
                  placeholder="Cari nomor bab atau judul..."
                  className="w-full pl-9 pr-8 py-2 rounded-xl bg-[var(--card)] border border-[var(--border)] text-xs text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/20 shadow-sm"
                  autoFocus
                />
                {tocSearch && (
                  <button
                    onClick={() => setTocSearch("")}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] hover:text-[var(--foreground)] cursor-pointer"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
            </div>

            {/* Chapter List */}
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {filteredChapters.length === 0 ? (
                <div className="py-16 text-center text-xs text-[var(--muted-foreground)]">
                  Tidak ada bab yang cocok dengan "{tocSearch}"
                </div>
              ) : (
                filteredChapters.map((ch) => {
                  const actualIdx = thread.chapters.findIndex(
                    (c) => c.id === ch.id
                  );
                  const isCurrent = actualIdx === selectedChapterIdx;
                  const isTrs = ch.translation_status === "translated";

                  return (
                    <button
                      key={ch.id}
                      ref={isCurrent ? activeChapterItemRef : undefined}
                      onClick={() => {
                        if (onSelectChapter) {
                          onSelectChapter(actualIdx);
                        } else {
                          setSelectedChapterIdx(actualIdx);
                        }
                        setIsTocOpen(false);
                      }}
                      className={cn(
                        "w-full text-left px-3.5 py-2.5 rounded-xl transition-all duration-150 flex items-center justify-between gap-3 group cursor-pointer",
                        isCurrent
                          ? "bg-[var(--primary)] text-white font-bold shadow-md shadow-[var(--primary)]/20"
                          : "hover:bg-[var(--secondary)] text-[var(--foreground)]"
                      )}
                    >
                      <div className="flex items-center gap-2.5 min-w-0 flex-1">
                        <span
                          className={cn(
                            "text-[10px] font-black px-1.5 py-0.5 rounded-md flex-shrink-0 font-mono",
                            isCurrent
                              ? "bg-white/20 text-white"
                              : "bg-[var(--secondary)] text-[var(--muted-foreground)]"
                          )}
                        >
                          #{ch.order + 1}
                        </span>
                        <span className="text-xs truncate">
                          {ch.title_translated ||
                            ch.title_original ||
                            `Bab ${ch.order + 1}`}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        {ch.is_bookmarked && (
                          <Star
                            size={12}
                            className={
                              isCurrent
                                ? "text-yellow-300 fill-yellow-300"
                                : "text-yellow-500 fill-yellow-500"
                            }
                          />
                        )}
                        <span
                          className={cn(
                            "w-2 h-2 rounded-full",
                            isTrs
                              ? isCurrent
                                ? "bg-white"
                                : "bg-emerald-500"
                              : "bg-zinc-500/40"
                          )}
                          title={
                            isTrs ? "Terjemahan Selesai" : "Belum Diterjemahkan"
                          }
                        />
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
