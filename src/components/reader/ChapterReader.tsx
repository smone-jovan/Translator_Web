import { useState, useRef, useEffect, useMemo } from 'react';
import { ArrowLeft, ChevronLeft, ChevronRight, Info, Loader2, Sparkles, Languages, ArrowUp, Star } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getApiUrl } from '@/lib/api';
import { renderMarkdown } from '@/lib/utils';
import type { ThreadDetail, ChapterContent } from './types';

function cleanThoughts(text: string | null | undefined): string {
  if (!text) return '';
  
  // 1. Strip fully enclosed <think>...</think> and <thought>...</thought> (case-insensitive)
  let cleaned = text.replace(/<(think|thought)\b[^>]*>[\s\S]*?<\/\1>/gi, '');
  
  // 2. Remove unclosed trailing <think> or <thought> tags
  cleaned = cleaned.replace(/<(think|thought)\b[^>]*>[\s\S]*$/gi, '');
  
  return cleaned;
}

interface ChapterReaderProps {
  thread: ThreadDetail;
  selectedChapterIdx: number;
  setSelectedChapterIdx: (idx: number) => void;
  chapterContent: ChapterContent | null;
  loadingContent: boolean;
  translatedText: string;
  isTranslating: boolean;
  displayMode: string;
  setDisplayMode: (mode: string) => void;
  fontSize: number;
  handleTranslateChapter: (isResume: boolean, initialText: string, overrideContent?: string, overrideId?: number, forceOverwrite?: boolean) => Promise<void>;
  setShowChapterList: (show: boolean) => void;
  alwaysHideThoughts: boolean;
  setAlwaysHideThoughts: (val: boolean) => void;
  controlsVisible: boolean;
  setControlsVisible: (val: boolean | ((prev: boolean) => boolean)) => void;
  mobileToolbarVisible: boolean;
  setMobileToolbarVisible: (val: boolean | ((prev: boolean) => boolean)) => void;
  handleFetchNextChapter?: () => Promise<void>;
}

export default function ChapterReader({
  thread,
  selectedChapterIdx,
  setSelectedChapterIdx,
  chapterContent,
  loadingContent,
  translatedText,
  isTranslating,
  displayMode,
  setDisplayMode,
  fontSize,
  handleTranslateChapter,
  setShowChapterList,
  alwaysHideThoughts,
  setAlwaysHideThoughts,
  controlsVisible,
  setControlsVisible,
  mobileToolbarVisible,
  setMobileToolbarVisible,
  handleFetchNextChapter,
}: ChapterReaderProps) {
  const showOriginal = displayMode === 'both' || displayMode === 'original';
  const showTranslated = displayMode === 'both' || displayMode === 'translated';

  const [isBookmarked, setIsBookmarked] = useState(chapterContent?.is_bookmarked || false);
  const [prevChapterContent, setPrevChapterContent] = useState(chapterContent);

  if (chapterContent !== prevChapterContent) {
    setIsBookmarked(chapterContent?.is_bookmarked || false);
    setPrevChapterContent(chapterContent);
  }

  const toggleBookmark = async () => {
    if (!chapterContent) return;
    try {
      const res = await fetch(getApiUrl(`/api/threads/${thread.id}/chapters/${chapterContent.id}/bookmark`), {
        method: 'PUT',
      });
      if (res.ok) {
        setIsBookmarked(!isBookmarked);
      }
    } catch (err) {
      console.error('Failed to toggle bookmark:', err);
    }
  };

  // PERFORMANCE FIX: Use refs for scroll progress to avoid re-rendering huge HTML chunks
  const scrollProgressRef = useRef(0);
  const progressCircleRef = useRef<SVGCircleElement>(null);
  const progressTextRef = useRef<HTMLSpanElement>(null);
  const scrollBtnRef = useRef<HTMLButtonElement>(null);
  const saveProgressTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const controlsVisibleRef = useRef(controlsVisible);
  
  useEffect(() => {
    controlsVisibleRef.current = controlsVisible;
    // Also update button visibility when controlsVisible changes
    if (scrollBtnRef.current) {
      if (controlsVisible && scrollProgressRef.current > 5) {
        scrollBtnRef.current.classList.remove('translate-y-28', 'opacity-0', 'scale-75', 'pointer-events-none');
        scrollBtnRef.current.classList.add('translate-y-0', 'opacity-100', 'scale-100');
      } else {
        scrollBtnRef.current.classList.add('translate-y-28', 'opacity-0', 'scale-75', 'pointer-events-none');
        scrollBtnRef.current.classList.remove('translate-y-0', 'opacity-100', 'scale-100');
      }
    }
  }, [controlsVisible]);

  const originalScrollContainerRef = useRef<HTMLDivElement>(null);
  const translatedScrollContainerRef = useRef<HTMLDivElement>(null);

  const lastScrollTopOriginal = useRef(0);
  const lastScrollTopTranslated = useRef(0);

  const scrollRafOriginalId = useRef<number | null>(null);

  const lastSavedScrollTopRef = useRef<number | null>(null);
  const prevChapterIdRef = useRef<number | null>(null);

  const saveScrollPosition = (pct: number, top?: number) => {
    if (!chapterContent) return;
    const key = `readomni_scroll_${thread.id}_${chapterContent.id}`;
    try {
      localStorage.setItem(key, JSON.stringify({ pct, top, ts: Date.now() }));
    } catch { /* ignore */ }
  };

  // Shared DOM update logic
  const updateScrollUI = (pct: number, scrollTop?: number) => {
    scrollProgressRef.current = pct;
    if (scrollTop !== undefined) {
      lastSavedScrollTopRef.current = scrollTop;
    }

    if (chapterContent && pct >= 0) {
      saveScrollPosition(pct, scrollTop ?? lastSavedScrollTopRef.current ?? undefined);
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
      
      if (controlsVisibleRef.current && pct > 5) {
        scrollBtnRef.current.classList.remove('translate-y-28', 'opacity-0', 'scale-75', 'pointer-events-none');
        scrollBtnRef.current.classList.add('translate-y-0', 'opacity-100', 'scale-100');
      } else {
        scrollBtnRef.current.classList.add('translate-y-28', 'opacity-0', 'scale-75', 'pointer-events-none');
        scrollBtnRef.current.classList.remove('translate-y-0', 'opacity-100', 'scale-100');
      }
    }

    // Debounced API save
    if (saveProgressTimeout.current) clearTimeout(saveProgressTimeout.current);
    saveProgressTimeout.current = setTimeout(() => {
      if (chapterContent && pct > 0) {
        fetch(getApiUrl(`/api/threads/${thread.id}/chapters/${chapterContent.id}/progress`), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ scroll_progress: pct }),
        }).catch(err => console.error('Failed to save scroll progress', err));
      }
    }, 1000);
  };

  const handleScrollOriginal = (e: React.UIEvent<HTMLDivElement>) => {
    if (scrollRafOriginalId.current !== null) return;
    const target = e.currentTarget;
    const scrollTop = target.scrollTop;
    const scrollHeight = target.scrollHeight - target.clientHeight;
    
    scrollRafOriginalId.current = requestAnimationFrame(() => {
      const pct = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
      updateScrollUI(pct, scrollTop);

      const delta = scrollTop - lastScrollTopOriginal.current;
      
      if (scrollTop < 20) {
        setControlsVisible(true);
      } else if (delta > 30) {
        setControlsVisible(false);
      } else if (delta < -15) {
        setControlsVisible(true);
      }
      
      lastScrollTopOriginal.current = scrollTop;
      scrollRafOriginalId.current = null;
    });
  };

  const scrollRafTranslatedId = useRef<number | null>(null);

  const handleScrollTranslated = (e: React.UIEvent<HTMLDivElement>) => {
    if (scrollRafTranslatedId.current !== null) return;
    const target = e.currentTarget;
    const scrollTop = target.scrollTop;
    const scrollHeight = target.scrollHeight - target.clientHeight;
    
    scrollRafTranslatedId.current = requestAnimationFrame(() => {
      const pct = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
      updateScrollUI(pct, scrollTop);

      const delta = scrollTop - lastScrollTopTranslated.current;
      
      if (scrollTop < 20) {
        setControlsVisible(true);
      } else if (delta > 30) {
        setControlsVisible(false);
      } else if (delta < -15) {
        setControlsVisible(true);
      }
      
      lastScrollTopTranslated.current = scrollTop;
      scrollRafTranslatedId.current = null;
    });
  };

  const handleContentClick = () => {
    if (window.getSelection()?.toString()) return;
    setControlsVisible(prev => !prev);
    setMobileToolbarVisible(prev => !prev);
  };

  const lastWindowScrollTop = useRef(0);
  const scrollRafWindowId = useRef<number | null>(null);

  useEffect(() => {
    const handleWindowScroll = () => {
      if (scrollRafWindowId.current !== null) return;
      
      scrollRafWindowId.current = requestAnimationFrame(() => {
        const scrollTop = window.scrollY || document.documentElement.scrollTop || document.body.scrollTop;
        const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
        const pct = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
        
        updateScrollUI(pct, scrollTop);
        
        const delta = scrollTop - lastWindowScrollTop.current;
        if (scrollTop < 20) {
          setControlsVisible(true);
        } else if (delta > 30) {
          setControlsVisible(false);
        } else if (delta < -15) {
          setControlsVisible(true);
        }
        lastWindowScrollTop.current = scrollTop;
        scrollRafWindowId.current = null;
      });
    };

    window.addEventListener('scroll', handleWindowScroll);
    return () => {
      window.removeEventListener('scroll', handleWindowScroll);
      if (scrollRafWindowId.current !== null) cancelAnimationFrame(scrollRafWindowId.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Save scroll position immediately on mobile screen-lock / visibility change
  useEffect(() => {
    const handlePageHide = () => {
      if (chapterContent && scrollProgressRef.current > 0) {
        const pct = scrollProgressRef.current;
        const top = lastSavedScrollTopRef.current ?? undefined;
        saveScrollPosition(pct, top);

        try {
          navigator.sendBeacon(
            getApiUrl(`/api/threads/${thread.id}/chapters/${chapterContent.id}/progress`),
            JSON.stringify({ scroll_progress: pct })
          );
        } catch { /* ignore */ }
      }
    };

    window.addEventListener('pagehide', handlePageHide);
    document.addEventListener('visibilitychange', handlePageHide);

    return () => {
      window.removeEventListener('pagehide', handlePageHide);
      document.removeEventListener('visibilitychange', handlePageHide);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterContent, thread.id]);

  // Multi-stage Scroll Position Restoration (local storage + backend progress)
  useEffect(() => {
    if (!chapterContent) return;

    const currentId = chapterContent.id;
    const isSameChapter = prevChapterIdRef.current === currentId;
    prevChapterIdRef.current = currentId;

    // Read saved local scroll position first
    const key = `readomni_scroll_${thread.id}_${currentId}`;
    let savedLocal: { pct?: number; top?: number } | null = null;
    try {
      const raw = localStorage.getItem(key);
      if (raw) savedLocal = JSON.parse(raw);
    } catch { /* ignore */ }

    const targetPct = savedLocal?.pct ?? chapterContent.scroll_progress ?? 0;
    const targetTop = savedLocal?.top;

    // If switching to a DIFFERENT chapter and no saved position exists, start at top (0)
    if (!isSameChapter && targetTop === undefined && targetPct === 0) {
      if (originalScrollContainerRef.current) originalScrollContainerRef.current.scrollTop = 0;
      if (translatedScrollContainerRef.current) translatedScrollContainerRef.current.scrollTop = 0;
      window.scrollTo(0, 0);
      updateScrollUI(0, 0);
      return;
    }

    const applyScroll = () => {
      if (targetTop !== undefined && targetTop > 0) {
        if (originalScrollContainerRef.current) originalScrollContainerRef.current.scrollTop = targetTop;
        if (translatedScrollContainerRef.current) translatedScrollContainerRef.current.scrollTop = targetTop;
        window.scrollTo(0, targetTop);
      } else if (targetPct > 0) {
        if (originalScrollContainerRef.current) {
          const el = originalScrollContainerRef.current;
          const scrollHeight = el.scrollHeight - el.clientHeight;
          if (scrollHeight > 0) el.scrollTop = (targetPct / 100) * scrollHeight;
        }
        if (translatedScrollContainerRef.current) {
          const el = translatedScrollContainerRef.current;
          const scrollHeight = el.scrollHeight - el.clientHeight;
          if (scrollHeight > 0) el.scrollTop = (targetPct / 100) * scrollHeight;
        }
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        if (docHeight > 0) window.scrollTo(0, (targetPct / 100) * docHeight);
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
      if (saveProgressTimeout.current) clearTimeout(saveProgressTimeout.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapterContent?.id, thread.id]);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    document.documentElement.scrollTo({ top: 0, behavior: 'smooth' });
    document.body.scrollTo({ top: 0, behavior: 'smooth' });

    if (originalScrollContainerRef.current) {
      originalScrollContainerRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
    if (translatedScrollContainerRef.current) {
      translatedScrollContainerRef.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
    updateScrollUI(0);
    setControlsVisible(true);
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
    const hasTranslation = !!chapterContent?.content_translated || !!translatedText;
    handleTranslateChapter(false, '', undefined, undefined, hasTranslation);
  };

  const originalContentNode = useMemo(() => {
    return chapterContent?.content_original
      ? renderMarkdown(chapterContent.content_original)
      : 'No original content found.';
  }, [chapterContent]);

  const translatedContentNode = useMemo(() => {
    if (!translatedText) return null;
    return renderMarkdown(alwaysHideThoughts ? cleanThoughts(translatedText) : translatedText);
  }, [translatedText, alwaysHideThoughts]);

  return (
    <div className="max-w-screen-2xl mx-auto h-full flex flex-col">
      {/* Top Navigation */}
      <div 
        className={`px-6 flex items-center justify-between border-[var(--border)] bg-[var(--background)]/50 transition-all duration-300 ease-in-out z-20 ${
          controlsVisible 
            ? 'h-14 py-3 border-b opacity-100' 
            : 'h-0 py-0 border-b-0 opacity-0 overflow-hidden pointer-events-none'
        }`}
      >
        <div className="flex items-center gap-4">
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => setShowChapterList(true)}
            className="rounded-xl gap-2 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
          >
            <ArrowLeft className="w-4 h-4" />
            List
          </Button>
          <div className="h-4 w-px bg-[var(--border)]" />
          <span className="text-[10px] md:text-xs font-bold tracking-tight">
            CHAPTER {selectedChapterIdx + 1}
          </span>
          <button 
            onClick={toggleBookmark}
            title={isBookmarked ? "Remove Bookmark" : "Bookmark Chapter"}
            className={`p-1.5 rounded-lg transition-colors ml-2 ${
              isBookmarked 
                ? 'text-yellow-500 bg-yellow-500/10' 
                : 'text-[var(--muted-foreground)] hover:bg-[var(--secondary)]'
            }`}
          >
            <Star size={16} className={isBookmarked ? 'fill-current' : ''} />
          </button>
        </div>
        
        {/* Reader Controls (Display Mode) */}
        <div className="flex items-center gap-1 bg-[var(--secondary)]/50 p-1 rounded-2xl border border-[var(--border)] scale-90 md:scale-100">
          <Button 
            variant={displayMode === 'original' ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => {
              setDisplayMode('original');
              try { localStorage.setItem('display_mode', 'original'); } catch { /* ignore */ }
            }}
            className={`rounded-xl text-[10px] h-7 px-3 ${displayMode === 'original' ? 'shadow-sm bg-[var(--background)]' : ''}`}
          >
            ORI
          </Button>
          <Button 
            variant={displayMode === 'translated' ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => {
              setDisplayMode('translated');
              try { localStorage.setItem('display_mode', 'translated'); } catch { /* ignore */ }
            }}
            className={`rounded-xl text-[10px] h-7 px-3 ${displayMode === 'translated' ? 'shadow-sm bg-[var(--background)]' : ''}`}
          >
            TRS
          </Button>
          <Button 
            variant={displayMode === 'both' ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => {
              setDisplayMode('both');
              try { localStorage.setItem('display_mode', 'both'); } catch { /* ignore */ }
            }}
            className={`rounded-xl text-[10px] h-7 px-3 ${displayMode === 'both' ? 'shadow-sm bg-[var(--background)]' : ''}`}
          >
            BOTH
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="icon" 
            className="rounded-xl border-[var(--border)] h-8 w-8"
            onClick={handlePrevChapter}
            disabled={selectedChapterIdx === 0}
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button 
            variant="outline" 
            size="icon" 
            className="rounded-xl border-[var(--border)] h-8 w-8"
            onClick={handleNextChapter}
            disabled={selectedChapterIdx === thread.chapters.length - 1}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Reader Grid */}
      <div className="flex-1 grid md:grid-cols-2 gap-0 divide-x divide-[var(--border)] overflow-hidden">
        {/* Original Content */}
        {showOriginal && (
          <div className="flex flex-col h-full overflow-hidden bg-[var(--secondary)]/10">
            <div 
              className={`px-6 flex items-center justify-between border-[var(--border)] bg-[var(--background)]/50 transition-all duration-300 ease-in-out ${
                controlsVisible 
                  ? 'h-10 py-3 border-b opacity-100' 
                  : 'h-0 py-0 border-b-0 opacity-0 overflow-hidden pointer-events-none'
              }`}
            >
              <span className="text-[10px] font-black uppercase tracking-widest text-[var(--muted-foreground)]">Source Content</span>
              <Button variant="ghost" size="icon" className="h-6 w-6 rounded-lg text-[var(--muted-foreground)]">
                <Info className="w-3 h-3" />
              </Button>
            </div>
            <div 
              ref={originalScrollContainerRef}
              className="flex-1 overflow-auto px-4 py-6 md:p-10 leading-relaxed font-serif select-text" 
              style={{ fontSize: `${fontSize}px` }}
              onScroll={handleScrollOriginal}
              onClick={handleContentClick}
            >
              {loadingContent ? (
                <div className="flex flex-col items-center justify-center h-full gap-2 opacity-30">
                  <Loader2 className="w-6 h-6 animate-spin" />
                  <span className="text-xs uppercase tracking-widest font-bold">Summoning text...</span>
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
                        Next Chapter <ChevronRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                      </Button>
                    ) : chapterContent?.source_url && handleFetchNextChapter ? (
                      <Button 
                        variant="default" 
                        className="rounded-full px-8 py-6 text-sm font-bold shadow-lg shadow-[var(--primary)]/20 hover:scale-105 active:scale-95 transition-all duration-300 group"
                        onClick={handleFetchNextChapter}
                      >
                        <Sparkles className="w-4 h-4 mr-2" />
                        Fetch Next Web Chapter
                      </Button>
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
          <div className="flex flex-col h-full overflow-hidden">
            <div 
              className={`px-6 flex items-center justify-between border-[var(--border)] bg-[var(--background)]/50 transition-all duration-300 ease-in-out ${
                controlsVisible 
                  ? 'h-10 py-3 border-b opacity-100' 
                  : 'h-0 py-0 border-b-0 opacity-0 overflow-hidden pointer-events-none'
              }`}
            >
              <span className="text-[10px] font-black uppercase tracking-widest text-[var(--accent)]">AI Translation</span>
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-1.5 text-[10px] font-bold text-[var(--muted-foreground)] cursor-pointer select-none hover:text-[var(--foreground)] transition-colors">
                  <input 
                    type="checkbox" 
                    checked={alwaysHideThoughts} 
                    onChange={async (e) => {
                      const checked = e.target.checked;
                      setAlwaysHideThoughts(checked);
                      try {
                        await fetch(getApiUrl('/api/settings'), {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ always_hide_thoughts: checked ? 1 : 0 })
                        });
                      } catch (err) {
                        console.error('Failed to save always_hide_thoughts setting:', err);
                      }
                    }}
                    className="rounded border-[var(--border)] bg-transparent text-[var(--accent)] focus:ring-0 cursor-pointer h-3.5 w-3.5"
                  />
                  Always Hide Thoughts
                </label>
                {(() => {
                  const hasTranslation = !!chapterContent?.content_translated || !!translatedText;
                  return (
                     <Button 
                      variant={hasTranslation ? "outline" : "default"} 
                      size="sm" 
                      className={`h-7 px-3 text-[10px] rounded-lg gap-1.5 ${hasTranslation ? 'border border-[color-mix(in_srgb,var(--foreground)_30%,transparent)] text-[var(--foreground)] hover:bg-[color-mix(in_srgb,var(--foreground)_10%,transparent)] bg-transparent' : 'shadow-lg shadow-[var(--accent)]/20'}`}
                      onClick={handleTranslateClick}
                      disabled={isTranslating}
                    >
                      {isTranslating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                      {isTranslating 
                        ? (hasTranslation ? 'RE-TRANSLATING' : 'TRANSLATING') 
                        : (hasTranslation ? 'RE-TRANSLATE' : 'TRANSLATE')
                      }
                    </Button>
                  );
                })()}
              </div>
            </div>
            <div 
              ref={translatedScrollContainerRef}
              className="flex-1 overflow-auto px-4 py-6 md:p-10 leading-relaxed font-serif bg-[var(--background)] select-text" 
              style={{ fontSize: `${fontSize}px` }}
              onScroll={handleScrollTranslated}
              onClick={handleContentClick}
            >
              {loadingContent ? (
                <div className="flex flex-col items-center justify-center h-full gap-2 opacity-30">
                  <Loader2 className="w-6 h-6 animate-spin" />
                  <span className="text-xs uppercase tracking-widest font-bold">Fetching translation...</span>
                </div>
              ) : translatedText ? (
                <>
                  {chapterContent?.fidelity_warning && (
                    <div className="mb-6 p-4 rounded-xl border border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-400 text-xs font-sans flex items-start gap-2.5">
                      <span className="text-base leading-none">⚠️</span>
                      <div className="flex-1 space-y-1">
                        <span className="font-bold block uppercase tracking-wider text-[10px]">Fidelity Warning</span>
                        <p className="leading-normal">{chapterContent.fidelity_warning}</p>
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
                        Next Chapter <ChevronRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
                      </Button>
                    ) : chapterContent?.source_url && handleFetchNextChapter ? (
                      <Button 
                        variant="default" 
                        className="rounded-full px-8 py-6 text-sm font-bold shadow-lg shadow-[var(--primary)]/20 hover:scale-105 active:scale-95 transition-all duration-300 group"
                        onClick={handleFetchNextChapter}
                      >
                        <Sparkles className="w-4 h-4 mr-2" />
                        Fetch Next Web Chapter
                      </Button>
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
                    <p className="text-sm font-bold uppercase tracking-tight">No Translation Yet</p>
                    <p className="text-[10px] max-w-[200px]">Click the generate button above to start AI translation for this chapter.</p>
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
          mobileToolbarVisible ? 'bottom-28 md:bottom-6' : 'bottom-6'
        } translate-y-28 opacity-0 scale-75 pointer-events-none hover:scale-105 active:scale-95`}
        style={{
          backgroundColor: 'var(--card)',
          boxShadow: '0 8px 30px rgba(0, 0, 0, 0.25)',
          borderRadius: '16px',
        }}
        title="Scroll to Top (0%)"
      >
        <svg className="absolute inset-0 w-full h-full -rotate-90 pointer-events-none" viewBox="0 0 56 56">
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
    </div>
  );
}
