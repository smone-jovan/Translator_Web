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

  const [isBookmarked, setIsBookmarked] = useState(false);

  useEffect(() => {
    setIsBookmarked(chapterContent?.is_bookmarked || false);
  }, [chapterContent]);

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

  const [scrollProgress, setScrollProgress] = useState(0);
  const originalScrollContainerRef = useRef<HTMLDivElement>(null);
  const translatedScrollContainerRef = useRef<HTMLDivElement>(null);

  const lastScrollTopOriginal = useRef(0);
  const lastScrollTopTranslated = useRef(0);

  const scrollRafOriginalId = useRef<number | null>(null);

  const handleScrollOriginal = (e: React.UIEvent<HTMLDivElement>) => {
    if (scrollRafOriginalId.current !== null) return;
    const target = e.currentTarget;
    const scrollTop = target.scrollTop;
    const scrollHeight = target.scrollHeight - target.clientHeight;
    
    scrollRafOriginalId.current = requestAnimationFrame(() => {
      const pct = scrollHeight > 0 ? (scrollTop / scrollHeight) * 100 : 0;
      setScrollProgress(pct);

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
      setScrollProgress(pct);

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
        
        setScrollProgress(pct);
        
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
    return () => window.removeEventListener('scroll', handleWindowScroll);
  }, [setControlsVisible]);

  // Restore scroll progress when chapter content changes
  useEffect(() => {
    if (chapterContent && chapterContent.scroll_progress && chapterContent.scroll_progress > 0) {
      const timer = setTimeout(() => {
        const progress = chapterContent.scroll_progress || 0;
        
        // 1. Restore for columns if internally scrolling
        if (originalScrollContainerRef.current) {
          const el = originalScrollContainerRef.current;
          const scrollHeight = el.scrollHeight - el.clientHeight;
          if (scrollHeight > 0) {
            el.scrollTop = (progress / 100) * scrollHeight;
          }
        }
        if (translatedScrollContainerRef.current) {
          const el = translatedScrollContainerRef.current;
          const scrollHeight = el.scrollHeight - el.clientHeight;
          if (scrollHeight > 0) {
            el.scrollTop = (progress / 100) * scrollHeight;
          }
        }
        
        // 2. Restore for window/body scroll
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        if (docHeight > 0) {
          const targetY = (progress / 100) * docHeight;
          window.scrollTo({ top: targetY, behavior: 'auto' });
        }
      }, 350); // slight delay to let elements lay out
      
      return () => clearTimeout(timer);
    }
  }, [chapterContent]);

  // Auto-save scroll progress to backend with debounce
  useEffect(() => {
    if (!chapterContent || scrollProgress <= 0) return;

    const saveScrollProgress = async () => {
      try {
        await fetch(getApiUrl(`/api/threads/${thread.id}/chapters/${chapterContent.id}/scroll`), {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ scroll_progress: scrollProgress }),
        });
      } catch (err) {
        console.error('Failed to save scroll progress:', err);
      }
    };

    const timer = setTimeout(() => {
      saveScrollProgress();
    }, 2000); // Debounce: save 2 seconds after scroll finishes

    return () => clearTimeout(timer);
  }, [scrollProgress, chapterContent, thread.id]);

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
    setScrollProgress(0);
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
  }, [chapterContent?.content_original]);

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
            onClick={() => setDisplayMode('original')}
            className={`rounded-xl text-[10px] h-7 px-3 ${displayMode === 'original' ? 'shadow-sm bg-[var(--background)]' : ''}`}
          >
            ORI
          </Button>
          <Button 
            variant={displayMode === 'translated' ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => setDisplayMode('translated')}
            className={`rounded-xl text-[10px] h-7 px-3 ${displayMode === 'translated' ? 'shadow-sm bg-[var(--background)]' : ''}`}
          >
            TRS
          </Button>
          <Button 
            variant={displayMode === 'both' ? 'secondary' : 'ghost'}
            size="sm"
            onClick={() => setDisplayMode('both')}
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
        onClick={scrollToTop}
        className={`fixed right-4 md:right-6 flex items-center justify-center w-[56px] h-[56px] shadow-2xl z-50 transition-all duration-300 cursor-pointer focus:outline-none ${
          mobileToolbarVisible ? 'bottom-28 md:bottom-6' : 'bottom-6'
        } ${
          controlsVisible && scrollProgress > 5
            ? 'translate-y-0 opacity-100 scale-100 animate-in fade-in zoom-in duration-300'
            : 'translate-y-28 opacity-0 scale-75 pointer-events-none'
        } hover:scale-105 active:scale-95`}
        style={{
          backgroundColor: 'var(--card)',
          boxShadow: '0 8px 30px rgba(0, 0, 0, 0.25)',
          borderRadius: `${Math.min(50, 16 + (scrollProgress / 100) * 34)}%`,
        }}
        title={`Scroll to Top (${Math.round(scrollProgress)}%)`}
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
            style={{
              borderRadius: `${Math.min(50, 16 + (scrollProgress / 100) * 34)}%`,
              transition: 'all 0.3s ease-out'
            }}
          />
          <circle
            cx="28"
            cy="28"
            r="26"
            fill="transparent"
            stroke="var(--primary)"
            strokeWidth="2.5"
            strokeDasharray={163.4}
            strokeDashoffset={163.4 - (scrollProgress / 100) * 163.4}
            strokeLinecap="round"
            className="transition-all duration-300 ease-out"
          />
        </svg>
        <ArrowUp className="w-5 h-5 text-[var(--foreground)] relative z-10 transition-transform duration-200" />
        <span className="absolute -top-1.5 -right-1.5 bg-[var(--primary)] text-[var(--primary-foreground)] text-[8px] font-bold h-4 min-w-4 px-1 flex items-center justify-center rounded-full border-2 border-[var(--background)] shadow-sm z-10">
          {Math.round(scrollProgress)}%
        </span>
      </button>
    </div>
  );
}
