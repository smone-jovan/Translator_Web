import { useState, useEffect, useRef } from 'react';
import { ArrowUpDown, SlidersHorizontal, Sparkles, RefreshCw, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { ThreadDetail } from './types';

interface ChapterListControlsProps {
  thread: ThreadDetail;
  chapterFilter: 'all' | 'translated';
  setChapterFilter: (filter: 'all' | 'translated') => void;
  sortOrder: 'asc' | 'desc';
  setSortOrder: (order: 'asc' | 'desc') => void;
  chapterSearch: string;
  setChapterSearch: (search: string) => void;
  targetLanguage: string;
  handlePolishLanguageChange: (lang: string) => Promise<void>;
  polishMode: 'soft' | 'hard';
  handlePolishModeChange: (mode: 'soft' | 'hard') => Promise<void>;
  polishSoftLimit: number;
  handlePolishLimitChange: (limit: number) => Promise<void>;
  autoDetectStart: boolean;
  setAutoDetectStart: (val: boolean) => void;
  manualStartNum: number;
  setManualStartNum: (val: number) => void;
  volumeMode: boolean;
  setVolumeMode: (val: boolean) => void;
  autoDetectVolume: boolean;
  setAutoDetectVolume: (val: boolean) => void;
  manualStartVolume: number;
  setManualStartVolume: (val: number) => void;
  volumeBoundaries: string;
  setVolumeBoundaries: (val: string) => void;
  volumeBoundaryType: string;
  setVolumeBoundaryType: (val: string) => void;
  chaptersPerVolume: number;
  setChaptersPerVolume: (val: number) => void;
  isTranslatingTitles: boolean;
  handleTranslateTitles: (isRepolish: boolean) => Promise<void>;
  getAutoStartNum: () => number;
}

export default function ChapterListControls({
  thread,
  chapterFilter,
  setChapterFilter,
  sortOrder,
  setSortOrder,
  chapterSearch,
  setChapterSearch,
  targetLanguage,
  handlePolishLanguageChange,
  polishMode,
  handlePolishModeChange,
  polishSoftLimit,
  handlePolishLimitChange,
  autoDetectStart,
  setAutoDetectStart,
  manualStartNum,
  setManualStartNum,
  volumeMode,
  setVolumeMode,
  autoDetectVolume,
  setAutoDetectVolume,
  manualStartVolume,
  setManualStartVolume,
  volumeBoundaries,
  setVolumeBoundaries,
  volumeBoundaryType,
  setVolumeBoundaryType,
  chaptersPerVolume,
  setChaptersPerVolume,
  isTranslatingTitles,
  handleTranslateTitles,
  getAutoStartNum,
}: ChapterListControlsProps) {
  const [showPolishPopover, setShowPolishPopover] = useState(false);
  const polishPopoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (polishPopoverRef.current && !polishPopoverRef.current.contains(e.target as Node)) {
        setShowPolishPopover(false);
      }
    };
    if (showPolishPopover) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [showPolishPopover]);

  const isPolished = (title: string | null | undefined) => {
    if (!title) return false;
    const containsChinese = /[\u4e00-\u9fff]/.test(title);
    if (containsChinese && targetLanguage.toLowerCase() !== 'chinese') return false;
    return true;
  };

  const somePolished = thread.chapters.some(ch => isPolished(ch.title_translated));
  const allPolished = thread.chapters.every(ch => isPolished(ch.title_translated));

  return (
    <div className="max-w-5xl mx-auto px-6 mt-8">
      {/* Controls bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-xl font-extrabold text-[var(--foreground)] flex items-center gap-3">
            Chapters
            <span className="text-xs font-semibold text-[var(--muted-foreground)] bg-[var(--secondary)] px-2.5 py-1 rounded-full">
              {thread.chapters.length} Total
            </span>
          </h2>
        </div>

        {/* Filter and Polish controls */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex bg-[var(--secondary)] p-1 rounded-xl border border-[var(--border)]">
            <button
              onClick={() => setChapterFilter('all')}
              className={cn(
                "text-xs font-bold px-3 py-1.5 rounded-lg transition-all border-none bg-transparent cursor-pointer",
                chapterFilter === 'all' 
                  ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm" 
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              )}
            >
              All Chapters
            </button>
            <button
              onClick={() => setChapterFilter('translated')}
              className={cn(
                "text-xs font-bold px-3 py-1.5 rounded-lg transition-all border-none bg-transparent cursor-pointer",
                chapterFilter === 'translated' 
                  ? "bg-[var(--card)] text-[var(--foreground)] shadow-sm" 
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              )}
            >
              Translated
            </button>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            className="rounded-xl h-9 gap-1.5 border-[var(--border)] text-[var(--foreground)] bg-[var(--card)]/30"
            title={sortOrder === 'asc' ? 'Sort Descending' : 'Sort Ascending'}
          >
            <ArrowUpDown className="w-3.5 h-3.5" />
            <span className="text-xs font-bold">{sortOrder === 'asc' ? 'Ascending' : 'Descending'}</span>
          </Button>

          <div className="relative" ref={polishPopoverRef}>
            <div className="flex items-center bg-[var(--card)]/30 border border-[var(--border)] rounded-xl h-9 overflow-hidden hover:bg-[var(--card)]/50 transition-all">
              {allPolished ? (
                <button 
                  className="flex items-center gap-1.5 px-3 h-full text-xs font-bold text-emerald-400 hover:bg-emerald-500/10 transition-all cursor-pointer disabled:opacity-50 bg-transparent border-none"
                  onClick={() => handleTranslateTitles(true)}
                  disabled={isTranslatingTitles}
                >
                  <RefreshCw className={cn("w-3.5 h-3.5", isTranslatingTitles ? "animate-spin" : "")} />
                  <span>{isTranslatingTitles ? 'Polishing...' : 'Re-polish All'}</span>
                </button>
              ) : somePolished ? (
                <button 
                  className="flex items-center gap-1.5 px-3 h-full text-xs font-bold text-amber-400 hover:bg-amber-500/10 transition-all cursor-pointer disabled:opacity-50 bg-transparent border-none"
                  onClick={() => handleTranslateTitles(false)}
                  disabled={isTranslatingTitles}
                >
                  <Sparkles className={cn("w-3.5 h-3.5 text-amber-500", isTranslatingTitles ? "animate-spin" : "")} />
                  <span>{isTranslatingTitles ? 'Polishing...' : 'Polish Remaining'}</span>
                </button>
              ) : (
                <button 
                  className="flex items-center gap-1.5 px-3 h-full text-xs font-bold text-[var(--foreground)] hover:bg-[var(--secondary)] transition-all cursor-pointer disabled:opacity-50 bg-transparent border-none"
                  onClick={() => handleTranslateTitles(false)}
                  disabled={isTranslatingTitles}
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                  <span>{isTranslatingTitles ? 'Polishing...' : 'Polish Titles'}</span>
                </button>
              )}
              <div className="w-[1px] h-4 bg-[var(--border)]" />
              <button 
                onClick={() => setShowPolishPopover(!showPolishPopover)}
                className={cn(
                  "flex items-center justify-center px-2.5 h-full transition-all cursor-pointer hover:bg-[var(--secondary)] bg-transparent border-none",
                  showPolishPopover ? "text-[var(--primary)] bg-[var(--secondary)]" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                )}
                title="Polish Settings"
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
              </button>
            </div>

            {showPolishPopover && (
              <div className="absolute right-0 top-11 w-72 bg-[var(--card)] border border-[var(--border)] rounded-2xl p-4 shadow-xl z-50 animate-in fade-in slide-in-from-top-2 flex flex-col gap-4 text-left">
                <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)] flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-amber-500" />
                  Polish Settings
                </div>

                {/* Language select */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase">Language</label>
                  <select 
                    value={targetLanguage}
                    onChange={(e) => handlePolishLanguageChange(e.target.value)}
                    className="text-xs bg-[var(--secondary)] border border-[var(--border)] text-[var(--foreground)] px-2.5 py-1.5 rounded-xl outline-none"
                  >
                    <option value="Indonesian">Indonesian</option>
                    <option value="English">English</option>
                  </select>
                </div>

                {/* Mode Select */}
                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase">Mode</label>
                  <div className="flex bg-[var(--secondary)] rounded-xl p-1">
                    <button
                      onClick={() => handlePolishModeChange('soft')}
                      className={cn(
                        "flex-1 py-1 text-[10px] font-bold rounded-lg transition-all border-none bg-transparent cursor-pointer",
                        polishMode === 'soft' ? "bg-[var(--card)] text-[var(--primary)] shadow-sm" : "text-[var(--muted-foreground)]"
                      )}
                    >
                      SOFT
                    </button>
                    <button
                      onClick={() => handlePolishModeChange('hard')}
                      className={cn(
                        "flex-1 py-1 text-[10px] font-bold rounded-lg transition-all border-none bg-transparent cursor-pointer",
                        polishMode === 'hard' ? "bg-[var(--card)] text-orange-500 shadow-sm" : "text-[var(--muted-foreground)]"
                      )}
                    >
                      HARD
                    </button>
                  </div>
                </div>

                {/* Limit slider (visible only in soft mode) */}
                {polishMode === 'soft' && (
                  <div className="flex flex-col gap-1.5 animate-in fade-in slide-in-from-top-1">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase">Limit</label>
                      <span className="text-[10px] font-bold text-[var(--primary)] bg-[var(--primary)]/10 px-2 py-0.5 rounded-md">{polishSoftLimit} Ch</span>
                    </div>
                    <input 
                      type="range" 
                      min="50" 
                      max="150" 
                      step="10"
                      value={polishSoftLimit} 
                      onChange={(e) => handlePolishLimitChange(parseInt(e.target.value, 10))}
                      className="w-full h-1.5 bg-[var(--secondary)] rounded-lg appearance-none cursor-pointer accent-[var(--primary)]"
                    />
                  </div>
                )}

                {/* Numbering Polish Section */}
                <div className="flex flex-col gap-1.5 pt-3 border-t border-[var(--border)]">
                  <label className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase">Numbering Polish</label>
                  
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] font-semibold text-[var(--foreground)]">Auto-detect starting number</span>
                    <button
                      onClick={() => setAutoDetectStart(!autoDetectStart)}
                      className={cn(
                        "text-[9px] font-extrabold px-2 py-0.5 rounded-md transition-all border bg-transparent cursor-pointer",
                        autoDetectStart 
                          ? "bg-green-500/10 text-green-400 border-green-500/30" 
                          : "bg-[var(--secondary)] text-[var(--muted-foreground)] border-transparent"
                      )}
                    >
                      {autoDetectStart ? 'ON' : 'OFF'}
                    </button>
                  </div>

                  <div className="flex items-center gap-2">
                    <input 
                      type="number"
                      min="1"
                      disabled={autoDetectStart}
                      value={autoDetectStart ? getAutoStartNum() : manualStartNum}
                      onChange={(e) => {
                        const val = parseInt(e.target.value, 10);
                        if (!isNaN(val)) setManualStartNum(val);
                      }}
                      className={cn(
                        "w-full text-xs bg-[var(--secondary)] border border-[var(--border)] text-[var(--foreground)] px-2.5 py-1.5 rounded-xl outline-none transition-all",
                        autoDetectStart ? "opacity-60 cursor-not-allowed bg-[var(--secondary)]/40 text-[var(--muted-foreground)]" : "focus:border-[var(--primary)]"
                      )}
                      placeholder="e.g. 91"
                    />
                  </div>
                  <p className="text-[9px] text-[var(--muted-foreground)] mt-0.5 leading-relaxed">
                    {autoDetectStart 
                      ? `System auto-detects Chapter ${getAutoStartNum()} from first title.`
                      : "Manually specify starting chapter number for zero-padded polish."}
                  </p>
                </div>

                {/* Volume Polish Section */}
                <div className="flex flex-col gap-1.5 pt-3 border-t border-[var(--border)]">
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase">Volume Numbering</label>
                    <button
                      onClick={() => setVolumeMode(!volumeMode)}
                      className={cn(
                        "text-[9px] font-extrabold px-2 py-0.5 rounded-md transition-all border bg-transparent cursor-pointer",
                        volumeMode 
                          ? "bg-green-500/10 text-green-400 border-green-500/30" 
                          : "bg-[var(--secondary)] text-[var(--muted-foreground)] border-transparent"
                      )}
                    >
                      {volumeMode ? 'ON' : 'OFF'}
                    </button>
                  </div>
                  
                  {volumeMode && (
                    <div className="flex flex-col gap-2 mt-1 animate-in fade-in slide-in-from-top-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] font-semibold text-[var(--foreground)]">Auto-detect Vol Boundaries</span>
                        <button
                          onClick={() => setAutoDetectVolume(!autoDetectVolume)}
                          className={cn(
                            "text-[9px] font-extrabold px-2 py-0.5 rounded-md transition-all border bg-transparent cursor-pointer",
                            autoDetectVolume 
                              ? "bg-amber-500/10 text-amber-500 border-amber-500/30" 
                              : "bg-[var(--secondary)] text-[var(--muted-foreground)] border-transparent"
                          )}
                        >
                          {autoDetectVolume ? 'ON' : 'OFF'}
                        </button>
                      </div>
                      <div className="flex items-center gap-2">
                        <input 
                          type="number"
                          min="1"
                          value={manualStartVolume}
                          onChange={(e) => {
                            const val = parseInt(e.target.value, 10);
                            if (!isNaN(val)) setManualStartVolume(val);
                          }}
                          className="w-full text-xs bg-[var(--secondary)] border border-[var(--border)] text-[var(--foreground)] px-2.5 py-1.5 rounded-xl outline-none transition-all focus:border-[var(--primary)]"
                          placeholder="Start Volume (e.g. 1)"
                        />
                      </div>

                      {/* Manual Volume Boundaries Input */}
                      <div className="flex flex-col gap-1 mt-1">
                        <span className="text-[11px] font-semibold text-[var(--foreground)]">Manual Volume Transitions</span>
                        <input 
                          type="text"
                          value={volumeBoundaries}
                          onChange={(e) => setVolumeBoundaries(e.target.value)}
                          className="w-full text-xs bg-[var(--secondary)] border border-[var(--border)] text-[var(--foreground)] px-2.5 py-1.5 rounded-xl outline-none transition-all focus:border-[var(--primary)]"
                          placeholder="Chapters list: e.g. 100, 200"
                        />
                        <div className="flex items-center justify-between mt-1">
                          <span className="text-[10px] text-[var(--muted-foreground)]">Match Type</span>
                          <div className="flex bg-[var(--secondary)] p-0.5 rounded-lg border border-[var(--border)]">
                            <button
                              onClick={() => setVolumeBoundaryType("raw")}
                              className={cn(
                                "text-[9px] font-bold px-2 py-0.5 rounded-md transition-all cursor-pointer border-none",
                                volumeBoundaryType === "raw" 
                                  ? "bg-[var(--primary)] text-[var(--primary-foreground)] shadow-sm font-bold" 
                                  : "text-[var(--muted-foreground)] bg-transparent border-transparent"
                              )}
                            >
                              Raw Num
                            </button>
                            <button
                              onClick={() => setVolumeBoundaryType("sequence")}
                              className={cn(
                                "text-[9px] font-bold px-2 py-0.5 rounded-md transition-all cursor-pointer border-none",
                                volumeBoundaryType === "sequence" 
                                  ? "bg-[var(--primary)] text-[var(--primary-foreground)] shadow-sm font-bold" 
                                  : "text-[var(--muted-foreground)] bg-transparent border-transparent"
                              )}
                            >
                              List Index
                            </button>
                          </div>
                        </div>
                      </div>

                      {/* Fixed Chapters per Volume Input */}
                      <div className="flex flex-col gap-1 mt-1">
                        <span className="text-[11px] font-semibold text-[var(--foreground)]">Fixed Chapters per Vol</span>
                        <input 
                          type="number"
                          min="0"
                          value={chaptersPerVolume || ''}
                          onChange={(e) => {
                            const val = parseInt(e.target.value, 10);
                            setChaptersPerVolume(isNaN(val) ? 0 : val);
                          }}
                          className="w-full text-xs bg-[var(--secondary)] border border-[var(--border)] text-[var(--foreground)] px-2.5 py-1.5 rounded-xl outline-none transition-all focus:border-[var(--primary)]"
                          placeholder="e.g. 100 (0 to disable)"
                        />
                      </div>

                      <p className="text-[9px] text-[var(--muted-foreground)] leading-relaxed mt-1">
                        Formats title as <span className="text-[var(--primary)] font-bold">V1-01. Title</span>. {autoDetectVolume ? "Resets chapter numbers when raw drops." : ""}
                      </p>
                    </div>
                  )}
                </div>
                {somePolished && (
                  <div className="pt-3 border-t border-[var(--border)] mt-1">
                    <button
                      onClick={() => {
                        handleTranslateTitles(true);
                      }}
                      disabled={isTranslatingTitles}
                      className="w-full py-2 text-xs font-bold text-center border border-red-500/20 hover:border-red-500/40 text-red-400 hover:bg-red-500/10 rounded-xl transition-all cursor-pointer bg-transparent"
                    >
                      Reset & Re-polish All
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Dynamic search bar */}
      <div className="relative mb-6">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted-foreground)]" />
        <input
          type="text"
          placeholder="Search chapter number, original title, or translation..."
          value={chapterSearch}
          onChange={(e) => setChapterSearch(e.target.value)}
          className="w-full pl-11 pr-4 py-3 rounded-2xl bg-[var(--card)]/50 border border-[var(--border)] focus:border-[var(--primary)]/60 focus:ring-1 focus:ring-[var(--primary)]/30 outline-none text-sm font-medium transition-all text-[var(--foreground)] bg-transparent"
        />
        {chapterSearch && (
          <button 
            onClick={() => setChapterSearch('')}
            className="absolute right-4 top-1/2 -translate-y-1/2 text-xs font-bold text-[var(--muted-foreground)] hover:text-[var(--foreground)] border-none bg-transparent cursor-pointer"
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
}
