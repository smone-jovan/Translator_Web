/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable no-empty */
import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  ChevronLeft, ChevronRight, Languages, 
  Loader2, Save, Settings, 
  RefreshCw, ArrowLeft, Download, Layout, Sparkles,
  Info, Search, ArrowUpDown, SlidersHorizontal, BookOpen, ChevronDown, ChevronUp
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getApiUrl } from '@/lib/api';
import { cn } from '@/lib/utils';
import ExportModal from '@/components/ExportModal';
import BulkTranslateModal from '@/components/BulkTranslateModal';

interface Chapter {
  id: number;
  order: number;
  title_original: string | null;
  title_translated: string | null;
  word_count: number;
  has_translation: boolean;
  translation_status?: string;
}

interface ThreadDetail {
  id: number;
  title: string;
  source_type: string;
  chapter_count: number;
  chapters: Chapter[];
  last_read_id?: number | null;
  cover_image?: string | null;
  original_title?: string | null;
  genres?: string | null;
  status?: string | null;
  status_coo?: string | null;
  synopsis?: string | null;
  author?: string | null;
}

interface ChapterContent {
  id: number;
  order: number;
  title_original: string | null;
  title_translated: string | null;
  content_original: string | null;
  content_translated: string | null;
  translation_status: string | null;
}

interface ReaderPageProps {
  threadId: number;
  onBack: () => void;
}

export default function ReaderPage({ threadId, onBack }: ReaderPageProps) {
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedChapterIdx, setSelectedChapterIdx] = useState<number | null>(null);
  const [chapterContent, setChapterContent] = useState<ChapterContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [translatedText, setTranslatedText] = useState('');
  const [isTranslating, setIsTranslating] = useState(false);
  const [showChapterList, setShowChapterList] = useState(true);
  const [fontSize, setFontSize] = useState(18);
  const [showSettings, setShowSettings] = useState(false);
  const [displayMode, setDisplayMode] = useState(localStorage.getItem('display_mode') || 'both');
  const [isTranslatingTitles, setIsTranslatingTitles] = useState(false);
  const [lastReadId, setLastReadId] = useState<number | null>(null);
  const [prefetchEnabled, setPrefetchEnabled] = useState(false);
  const [prefetchCount, setPrefetchCount] = useState(2);
  const [prefetchMode, setPrefetchMode] = useState('soft');
  const [globalSettings, setGlobalSettings] = useState<{lm_url?: string, lm_model?: string, target_language?: string}>({});
  const [polishMode, setPolishMode] = useState<'soft' | 'hard'>('soft');
  const [polishSoftLimit, setPolishSoftLimit] = useState<number>(100);
  const [autoDetectStart, setAutoDetectStart] = useState<boolean>(() => {
    const saved = localStorage.getItem(`auto_detect_start_${threadId}`);
    return saved !== null ? saved === 'true' : true;
  });
  const [manualStartNum, setManualStartNum] = useState<number>(() => {
    const saved = localStorage.getItem(`manual_start_num_${threadId}`);
    return saved !== null ? parseInt(saved, 10) : 1;
  });
  const [volumeMode, setVolumeMode] = useState<boolean>(() => {
    const saved = localStorage.getItem(`volume_mode_${threadId}`);
    return saved !== null ? saved === 'true' : true;
  });
  const [autoDetectVolume, setAutoDetectVolume] = useState<boolean>(() => {
    const saved = localStorage.getItem(`auto_detect_volume_${threadId}`);
    return saved !== null ? saved === 'true' : true;
  });
  const [manualStartVolume, setManualStartVolume] = useState<number>(() => {
    const saved = localStorage.getItem(`manual_start_volume_${threadId}`);
    return saved !== null ? parseInt(saved, 10) : 1;
  });
  const [volumeBoundaries, setVolumeBoundaries] = useState<string>(() => {
    return localStorage.getItem(`volume_boundaries_${threadId}`) || '';
  });
  const [volumeBoundaryType, setVolumeBoundaryType] = useState<string>(() => {
    return localStorage.getItem(`volume_boundary_type_${threadId}`) || 'raw';
  });
  const [chaptersPerVolume, setChaptersPerVolume] = useState<number>(() => {
    const saved = localStorage.getItem(`chapters_per_volume_${threadId}`);
    return saved !== null ? parseInt(saved, 10) : 0;
  });

  useEffect(() => {
    localStorage.setItem(`auto_detect_start_${threadId}`, String(autoDetectStart));
    localStorage.setItem(`manual_start_num_${threadId}`, String(manualStartNum));
    localStorage.setItem(`volume_mode_${threadId}`, String(volumeMode));
    localStorage.setItem(`auto_detect_volume_${threadId}`, String(autoDetectVolume));
    localStorage.setItem(`manual_start_volume_${threadId}`, String(manualStartVolume));
    localStorage.setItem(`volume_boundaries_${threadId}`, volumeBoundaries);
    localStorage.setItem(`volume_boundary_type_${threadId}`, volumeBoundaryType);
    localStorage.setItem(`chapters_per_volume_${threadId}`, String(chaptersPerVolume));
  }, [threadId, autoDetectStart, manualStartNum, volumeMode, autoDetectVolume, manualStartVolume, volumeBoundaries, volumeBoundaryType, chaptersPerVolume]);
  const [showPolishPopover, setShowPolishPopover] = useState<boolean>(false);
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
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [isBulkModalOpen, setIsBulkModalOpen] = useState(false);
  const [isSynopsisCollapsed, setIsSynopsisCollapsed] = useState(true);
  const [chapterSearch, setChapterSearch] = useState('');
  const [chapterFilter, setChapterFilter] = useState<'all' | 'translated'>('all');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  const scrollRef = useRef<HTMLDivElement>(null);
  const lastFetchedIdRef = useRef<number | null>(null);

  const fetchThread = useCallback(async () => {
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}`));
      const data = await res.json();
      setThread(data);
      if (data.last_read_id) {
        setLastReadId(data.last_read_id);
      }
    } catch {
      console.error('Failed to fetch thread');
    }
  }, [threadId]);

  const handleStartBatch = async (chapterIds: number[], aiExtract: boolean, _loadMode: 'soft' | 'hard', targetLang: string, overwrite: boolean) => {
    if (!thread) return;
    
    window.dispatchEvent(new CustomEvent('batch-start', { 
        detail: { total: chapterIds.length } 
    }));

    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/batch-translate`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            chapter_ids: chapterIds, 
            ai_extract: aiExtract,
            overwrite: overwrite,
            target_lang: targetLang
        })
      });
      
      if (!res.ok) throw new Error('Failed to start batch');
      
      let completed = 0;
      const total = chapterIds.length;
      
      const simulateProgress = () => {
          if (completed < total) {
              completed++;
              window.dispatchEvent(new CustomEvent('batch-update', { 
                  detail: { 
                      completed, 
                      currentTitle: `Processing Chapter ${chapterIds[completed-1]}` 
                  } 
              }));
              if (completed === total) {
                window.dispatchEvent(new CustomEvent('batch-end'));
                fetchThread(); 
              } else {
                setTimeout(simulateProgress, 3000); 
              }
          }
      };
      
      simulateProgress();
    } catch (e) {
      console.error(e);
      window.dispatchEvent(new CustomEvent('batch-end'));
    }
  };

  // Initial Load
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await fetchThread();
      
      // Fetch global settings (ADR-008 Sync)
      try {
        const gsRes = await fetch(getApiUrl('/api/global-context'));
        const gsData = await gsRes.json();
        setPrefetchEnabled(gsData.prefetch_enabled === 1);
        setPrefetchCount(gsData.prefetch_count || 2);
        setPrefetchMode(gsData.prefetch_mode || 'soft');
        setPolishMode(gsData.polish_mode || 'soft');
        setPolishSoftLimit(gsData.polish_soft_limit || 100);
        setGlobalSettings({
          lm_url: gsData.lm_url,
          lm_model: gsData.lm_model,
          target_language: gsData.target_language
        });
      } catch (err) {
        console.error("Failed to fetch global settings", err);
      }
      
      setLoading(false);
    };
    init();
  }, [fetchThread]);

  // Polling for background updates (ADR-013)
  useEffect(() => {
    let interval: any = null;
    // Only poll if prefetch is enabled OR if there are processing chapters
    const hasProcessing = thread?.chapters.some(c => c.translation_status === 'processing');
    
    if (prefetchEnabled || hasProcessing) {
      interval = setInterval(() => {
        fetchThread();
      }, 5000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [prefetchEnabled, fetchThread, thread?.chapters]);

  const handleTranslateChapter = useCallback(async (isResume = false, initialText = '', overrideContent?: string, overrideId?: number, forceOverwrite = false) => {
    const textToTranslate = overrideContent || chapterContent?.content_original;
    const chId = overrideId || chapterContent?.id;
    
    if (isTranslating || !textToTranslate || !chId) return;
    setIsTranslating(true);
    if (!isResume) setTranslatedText('');
    else setTranslatedText(initialText);

    try {
      const lmUrl = globalSettings.lm_url;
      const lmModel = globalSettings.lm_model;
      const targetLang = globalSettings.target_language || 'Indonesian';

      const res = await fetch(getApiUrl('/api/translate/stream'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

      if (!res.body) throw new Error('No stream');
      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6);
            if (dataStr === '[DONE]') break;
            try {
              const data = JSON.parse(dataStr);
              if (data.content) {
                setTranslatedText(prev => prev + data.content);
              } else if (data.error) {
                setTranslatedText(prev => prev + '\n⚠️ ' + data.error);
              }
            } catch { /* skip */ }
          }
        }
      }
      
      // Update thread state to show it has translation
      await fetchThread();
    } catch {
      setTranslatedText(prev => prev + '\n⚠️ Translation failed.');
    } finally {
      setIsTranslating(false);
    }
  }, [isTranslating, threadId, fetchThread, chapterContent?.content_original, chapterContent?.id, globalSettings]);

  // Handle Chapter Selection
  useEffect(() => {
    if (!thread || selectedChapterIdx === null) return;
    const ch = thread.chapters[selectedChapterIdx];
    if (!ch) return;

    // Prevent re-fetching if we already have this chapter's content
    if (lastFetchedIdRef.current === ch.id) return;
    
    const abortController = new AbortController();

    const fetchContent = async () => {
      setLoadingContent(true);
      try {
        const res = await fetch(getApiUrl(`/api/threads/${threadId}/chapters/${ch.id}`), {
          signal: abortController.signal
        });
        const data: ChapterContent = await res.json();
        
        lastFetchedIdRef.current = ch.id;
        setChapterContent(data);
        setTranslatedText(data.content_translated || '');
        setLastReadId(ch.id);
        
        if (data.translation_status === 'processing') {
          handleTranslateChapter(true, data.content_translated || '', data.content_original || '', data.id);
        }
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setChapterContent(null);
          lastFetchedIdRef.current = null;
        }
      } finally {
        setLoadingContent(false);
      }
    };
    
    fetchContent();
    return () => abortController.abort();
  }, [selectedChapterIdx, threadId, thread, handleTranslateChapter]);

  // Infinite Polish - Single Title
  const handleSingleTitlePolish = async (chapterId: number, e: React.MouseEvent) => {
    e.stopPropagation(); // VERY IMPORTANT: Don't open the chapter!
    if (isTranslatingTitles) return;
    
    setIsTranslatingTitles(true);
    try {
      const targetLang = globalSettings.target_language || localStorage.getItem('target_language') || 'Indonesian';
      const autoStart = getAutoStartNum();
      const startNum = autoDetectStart ? autoStart : (manualStartNum || 1);
      const url = getApiUrl(`/api/threads/${threadId}/translate-titles?repolish=true&chapter_id=${chapterId}&target_lang=${targetLang}&start_number=${startNum}&volume_mode=${volumeMode}&auto_detect_volume=${autoDetectVolume}&start_volume=${manualStartVolume}&volume_boundaries=${encodeURIComponent(volumeBoundaries)}&volume_boundary_type=${volumeBoundaryType}&chapters_per_volume=${chaptersPerVolume}`);
      
      const res = await fetch(url, { method: 'POST' });
      if (res.ok) {
        await fetchThread();
      }
    } catch (err) {
      console.error('Polish failed:', err);
    } finally {
      setIsTranslatingTitles(false);
    }
  };

  // Auto-detect starting chapter number based on the first chapter's original title
  const getAutoStartNum = () => {
    if (!thread || !thread.chapters || thread.chapters.length === 0) return 1;
    const firstTitle = thread.chapters[0].title_original || '';
    const match = firstTitle.match(/(?:chapter|bab|vol|volume|ch|第)\s*(\d+)/i);
    if (match) return parseInt(match[1], 10);
    const digitMatch = firstTitle.match(/\d+/);
    if (digitMatch) return parseInt(digitMatch[0], 10);
    return 1;
  };

  // Infinite Polish - All
  const handleTranslateTitles = async (isRepolish = false) => {
    if (!thread || isTranslatingTitles) return;
    
    if (isRepolish && !window.confirm('All existing polished titles will be overwritten by AI. Continue?')) {
      return;
    }

    setIsTranslatingTitles(true);
    try {
      const targetLang = globalSettings.target_language || 'Indonesian';
      const autoStart = getAutoStartNum();
      const startNum = autoDetectStart ? autoStart : (manualStartNum || 1);
      const url = getApiUrl(`/api/threads/${threadId}/translate-titles?target_lang=${targetLang}${isRepolish ? '&repolish=true' : ''}&start_number=${startNum}&volume_mode=${volumeMode}&auto_detect_volume=${autoDetectVolume}&start_volume=${manualStartVolume}&volume_boundaries=${encodeURIComponent(volumeBoundaries)}&volume_boundary_type=${volumeBoundaryType}&chapters_per_volume=${chaptersPerVolume}`);
      
      const res = await fetch(url, { method: 'POST' });
      if (!res.ok) throw new Error('Failed');
      await fetchThread();
    } catch {
      alert('Title translation failed.');
    } finally {
      setIsTranslatingTitles(false);
      setShowPolishPopover(false);
    }
  };

  const handlePolishLanguageChange = async (lang: string) => {
    setGlobalSettings(prev => ({ ...prev, target_language: lang }));
    try {
      await fetch(getApiUrl('/api/settings'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_language: lang })
      });
    } catch (err) {
      console.error("Failed to update target language", err);
    }
  };

  const handlePolishModeChange = async (mode: 'soft' | 'hard') => {
    setPolishMode(mode);
    try {
      await fetch(getApiUrl('/api/settings'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ polish_mode: mode })
      });
    } catch (err) {
      console.error("Failed to update polish mode", err);
    }
  };

  const handlePolishLimitChange = async (limit: number) => {
    setPolishSoftLimit(limit);
    try {
      await fetch(getApiUrl('/api/settings'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ polish_soft_limit: limit })
      });
    } catch (err) {
      console.error("Failed to update polish limit", err);
    }
  };

  const handleSaveTranslation = async () => {
    if (!translatedText || !chapterContent) return;
    try {
      await fetch(getApiUrl(`/api/threads/${threadId}/chapters/${chapterContent.id}/translation`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ translated_text: translatedText })
      });
      await fetchThread();
    } catch {
      console.error('Failed to save.');
    }
  };

  const showOriginal = displayMode === 'both' || displayMode === 'original';
  const showTranslated = displayMode === 'both' || displayMode === 'translated';

  const goToChapter = (idx: number) => {
    setSelectedChapterIdx(idx);
    setShowChapterList(false);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="w-10 h-10 animate-spin text-[var(--primary)]" />
        <p className="text-[var(--muted-foreground)] font-medium animate-pulse">Consulting the archives...</p>
      </div>
    );
  }

  if (!thread) return null;

  return (
    <div className="flex flex-col h-full overflow-hidden bg-[var(--background)] relative">
      {/* Settings Overlay */}
      {showSettings && (
        <div className="absolute top-20 right-4 z-50 w-72 animate-in fade-in slide-in-from-top-4 duration-300">
          <Card className="shadow-2xl border-[var(--border)] bg-[var(--card)] backdrop-blur-xl">
            <CardContent className="p-6 space-y-6">
              <div>
                <label className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">Font Size</label>
                <div className="flex flex-col gap-2 mt-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono text-[var(--muted-foreground)]">12px</span>
                    <span className="text-sm font-bold text-[var(--accent)]">{fontSize}px</span>
                    <span className="text-[10px] font-mono text-[var(--muted-foreground)]">32px</span>
                  </div>
                  <input 
                    type="range" 
                    min="12" 
                    max="32" 
                    value={fontSize} 
                    onChange={(e) => setFontSize(parseInt(e.target.value))}
                    className="w-full h-1.5 bg-[var(--secondary)] rounded-lg appearance-none cursor-pointer accent-[var(--accent)]"
                  />
                </div>
              </div>
              
              <div>
                <label className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">Layout Mode</label>
                <div className="grid grid-cols-3 gap-2 mt-3">
                  {['original', 'translated', 'both'].map((mode) => (
                    <Button 
                      key={mode}
                      variant={displayMode === mode ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => { setDisplayMode(mode); localStorage.setItem('display_mode', mode); }}
                      className="text-[10px] capitalize h-8"
                    >
                      {mode}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]">
                <div className="space-y-0.5">
                  <label className="text-xs font-semibold text-[var(--foreground)]">Auto-Prefetch</label>
                  <p className="text-[10px] text-[var(--muted-foreground)]">Translate next chapter in background</p>
                </div>
                <Button 
                  variant={prefetchEnabled ? "default" : "outline"} 
                  size="sm" 
                  className={`h-7 px-3 rounded-full text-[10px] ${prefetchEnabled ? 'bg-green-600 hover:bg-green-700' : ''}`}
                  onClick={async () => {
                    const newVal = !prefetchEnabled;
                    setPrefetchEnabled(newVal);
                    try {
                      await fetch(getApiUrl('/api/settings'), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ prefetch_enabled: newVal ? 1 : 0 })
                      });
                    } catch (err) {
                      console.error("Failed to save prefetch setting", err);
                    }
                  }}
                >
                  {prefetchEnabled ? 'ON' : 'OFF'}
                </Button>
              </div>

              {prefetchEnabled && (
                <div className="pt-2 border-t border-[var(--border)] animate-in fade-in slide-in-from-top-2">
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">Prefetch Range</label>
                    <span className="text-[10px] font-bold text-[var(--primary)] bg-[var(--primary)]/10 px-2 py-0.5 rounded-md">{prefetchCount} Ch</span>
                  </div>
                  <input 
                    type="range" 
                    min="1" 
                    max="5" 
                    value={prefetchCount} 
                    onChange={async (e) => {
                      const val = parseInt(e.target.value);
                      setPrefetchCount(val);
                      try {
                        await fetch(getApiUrl('/api/settings'), {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ prefetch_count: val })
                        });
                      } catch (err) {
                        console.error("Failed to save prefetch count", err);
                      }
                    }}
                    className="w-full h-1.5 bg-[var(--secondary)] rounded-lg appearance-none cursor-pointer accent-[var(--primary)]"
                  />
                  <div className="flex justify-between text-[9px] text-[var(--muted-foreground)] mt-1 px-1">
                    <span>1</span>
                    <span>2</span>
                    <span>3</span>
                    <span>4</span>
                    <span>5</span>
                  </div>

                  <div className="mt-4 pt-3 border-t border-[var(--border)]">
                    <label className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider block mb-2">Prefetch Mode</label>
                    <div className="flex bg-[var(--secondary)] rounded-xl p-1">
                      <button
                        onClick={async () => {
                          setPrefetchMode('soft');
                          try { await fetch(getApiUrl('/api/settings'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prefetch_mode: 'soft' }) }); } catch {}
                        }}
                        className={cn(
                          "flex-1 py-1.5 text-[9px] font-bold rounded-lg transition-all",
                          prefetchMode === 'soft' ? "bg-[var(--card)] text-[var(--primary)] shadow-sm" : "text-[var(--muted-foreground)]"
                        )}
                      >
                        SOFT
                      </button>
                      <button
                        onClick={async () => {
                          setPrefetchMode('hard');
                          try { await fetch(getApiUrl('/api/settings'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prefetch_mode: 'hard' }) }); } catch {}
                        }}
                        className={cn(
                          "flex-1 py-1.5 text-[9px] font-bold rounded-lg transition-all",
                          prefetchMode === 'hard' ? "bg-[var(--card)] text-orange-500 shadow-sm" : "text-[var(--muted-foreground)]"
                        )}
                      >
                        HARD
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <Button variant="ghost" size="sm" className="w-full text-xs h-8 mt-2" onClick={() => setShowSettings(false)}>Close</Button>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Header Bar */}
      <div className="flex items-center gap-4 px-6 py-4 border-b border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-md z-30">
        <button onClick={onBack} className="p-2 hover:bg-[var(--secondary)] rounded-full transition-all active:scale-95">
          <ArrowLeft className="w-5 h-5 text-[var(--foreground)]" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-sm md:text-lg font-bold truncate tracking-tight">{thread.title}</h1>
          <p className="text-[10px] text-[var(--muted-foreground)] font-medium uppercase tracking-widest flex items-center gap-2">
            {thread.chapter_count} chapters • {thread.source_type}
            {isTranslatingTitles && (
              <span className="flex items-center gap-1 text-[var(--accent)] animate-pulse">
                <Loader2 className="w-2.5 h-2.5 animate-spin" />
                Polishing...
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!showChapterList && (
            <Button variant="outline" size="sm" onClick={handleSaveTranslation} className="rounded-xl border-[var(--border)] hidden sm:flex">
              <Save className="w-4 h-4 mr-2" /> Save
            </Button>
          )}
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setIsBulkModalOpen(true)} 
            className="rounded-xl border-[var(--border)] text-[var(--accent)] hover:bg-[var(--accent)]/10"
            title="Batch Translate"
          >
            <Sparkles className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={() => setIsExportModalOpen(true)} className="rounded-xl border-[var(--border)]">
            <Download className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowSettings(!showSettings)} className="rounded-xl border-[var(--border)]">
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-[var(--background)] custom-scrollbar" ref={scrollRef}>
        {showChapterList ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 text-left pb-16">
            {/* 1. Immersive Novel Header */}
            <div className="relative w-full overflow-hidden border-b border-[var(--border)] bg-[var(--background)]">
              {/* Immersive blurred backdrop cover */}
              {thread.cover_image && (
                <div 
                  className="absolute inset-0 z-0 bg-cover bg-center pointer-events-none scale-110 filter blur-[40px] brightness-[0.3] opacity-30"
                  style={{ backgroundImage: `url(${thread.cover_image})` }}
                />
              )}
              {/* Subtle gradient overlay to blend backdrop smoothly */}
              <div className="absolute inset-0 z-0 bg-gradient-to-b from-transparent to-[var(--background)] pointer-events-none" />

              {/* Inner Header Container */}
              <div className="relative z-10 max-w-5xl mx-auto px-6 py-10 md:py-16 flex flex-col md:flex-row gap-8 items-start">
                {/* Left: Premium Cover Container */}
                <div className="relative group mx-auto md:mx-0 flex-shrink-0">
                  <div className="w-[180px] h-[250px] md:w-[220px] md:h-[308px] rounded-3xl overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.5)] border border-white/10 relative transition-transform duration-500 group-hover:scale-105">
                    {thread.cover_image ? (
                      <img 
                        src={thread.cover_image} 
                        alt={thread.title} 
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = 'https://images.unsplash.com/photo-1543002588-bfa74002ed7e?q=80&w=300';
                        }}
                      />
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-indigo-500 to-purple-600 flex flex-col items-center justify-center p-4 text-center">
                        <BookOpen className="w-10 h-10 text-white/50 mb-2" />
                        <span className="text-xs text-white/80 font-bold tracking-wider uppercase">No Cover</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: Immersive Text Details */}
                <div className="flex-1 text-left min-w-0 flex flex-col h-full justify-between">
                  <div>
                    {/* Original Title (Cleaned) badge if different */}
                    {thread.original_title && (
                      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20 mb-3 max-w-full truncate" title={thread.original_title}>
                        {thread.original_title}
                      </span>
                    )}
                    <h1 className="text-2xl md:text-4xl font-extrabold text-[var(--foreground)] tracking-tight leading-tight mb-2">
                      {thread.title}
                    </h1>
                    <p className="text-sm text-[var(--muted-foreground)] font-medium mb-6">
                      by <span className="text-[var(--foreground)] font-semibold">{thread.source_type || 'AI Platform'}</span>
                    </p>

                    {/* Action Buttons */}
                    <div className="flex flex-wrap items-center gap-3 mb-6">
                      <Button 
                        variant="default"
                        size="lg"
                        onClick={() => {
                          const startIdx = thread.chapters.findIndex(ch => ch.id === lastReadId);
                          goToChapter(startIdx !== -1 ? startIdx : 0);
                        }}
                        className="rounded-2xl gap-2 font-extrabold px-6 h-12 text-sm bg-gradient-to-r from-red-600 to-red-500 hover:from-red-500 hover:to-red-400 text-white shadow-xl shadow-red-600/20 active:scale-[0.98] transition-all"
                      >
                        Read Now
                      </Button>
                      
                      <Button 
                        variant="outline"
                        size="lg"
                        onClick={() => setIsBulkModalOpen(true)}
                        className="rounded-2xl gap-2 font-bold px-5 h-12 text-sm border-[var(--border)] bg-[var(--card)]/30 backdrop-blur-sm hover:bg-[var(--secondary)] text-[var(--foreground)] transition-all"
                      >
                        <Sparkles className="w-4 h-4 text-[var(--primary)]" />
                        Batch Translate
                      </Button>
                    </div>

                    {/* Genres Grid */}
                    {thread.genres && (
                      <div className="flex flex-wrap gap-2 mb-4">
                        {thread.genres.split(',').map((g: string, i: number) => (
                          <span 
                            key={i} 
                            className="text-[10px] md:text-xs font-semibold px-3 py-1 rounded-full bg-[color-mix(in_srgb,var(--secondary)_50%,transparent)] border border-[var(--border)] text-[var(--foreground)]"
                          >
                            {g.trim()}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Status & Stats Badges */}
                    <div className="flex flex-wrap items-center gap-3">
                      {/* Status Badge */}
                      {thread.status && (
                        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
                          thread.status.toLowerCase().includes('ongoing') || thread.status.toLowerCase().includes('no')
                            ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' 
                            : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        }`}>
                          {thread.status}
                        </span>
                      )}
                      
                      {/* Status COO Badge */}
                      {thread.status_coo && (
                        <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 max-w-[280px] truncate" title={thread.status_coo}>
                          {thread.status_coo}
                        </span>
                      )}

                      {/* Chapter Count Badge */}
                      <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                        {thread.chapters.length} chapters
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Synopsis Section */}
            {thread.synopsis && (
              <div className="max-w-5xl mx-auto px-6 mt-8">
                <div className="glass p-6 rounded-3xl border border-[var(--border)] shadow-lg">
                  <h3 className="text-lg font-bold text-[var(--foreground)] mb-3">Synopsis</h3>
                  <div className="relative">
                    <p className={cn(
                      "text-sm leading-relaxed text-[var(--muted-foreground)] whitespace-pre-line font-medium transition-all duration-300",
                      isSynopsisCollapsed ? "line-clamp-4 overflow-hidden" : ""
                    )}>
                      {thread.synopsis}
                    </p>
                    {thread.synopsis.length > 200 && (
                      <div className="mt-3 flex justify-start">
                        <button 
                          onClick={() => setIsSynopsisCollapsed(!isSynopsisCollapsed)}
                          className="text-xs font-extrabold text-[var(--primary)] hover:underline flex items-center gap-1 cursor-pointer"
                        >
                          {isSynopsisCollapsed ? (
                            <>Show More <ChevronDown className="w-3.5 h-3.5" /></>
                          ) : (
                            <>Show Less <ChevronUp className="w-3.5 h-3.5" /></>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* 3. Chapter List Area */}
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
                        "text-xs font-bold px-3 py-1.5 rounded-lg transition-all",
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
                        "text-xs font-bold px-3 py-1.5 rounded-lg transition-all",
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
                      {(() => {
                        const somePolished = thread?.chapters?.some(ch => ch.title_translated) || false;
                        const allPolished = thread?.chapters?.every(ch => ch.title_translated) || false;
                        
                        if (allPolished) {
                          return (
                            <button 
                              className="flex items-center gap-1.5 px-3 h-full text-xs font-bold text-emerald-400 hover:bg-emerald-500/10 transition-all cursor-pointer disabled:opacity-50 bg-transparent border-none"
                              onClick={() => handleTranslateTitles(true)}
                              disabled={isTranslatingTitles}
                            >
                              <RefreshCw className={`w-3.5 h-3.5 ${isTranslatingTitles ? 'animate-spin' : ''}`} />
                              <span>{isTranslatingTitles ? 'Polishing...' : 'Re-polish All'}</span>
                            </button>
                          );
                        } else if (somePolished) {
                          return (
                            <button 
                              className="flex items-center gap-1.5 px-3 h-full text-xs font-bold text-amber-400 hover:bg-amber-500/10 transition-all cursor-pointer disabled:opacity-50 bg-transparent border-none"
                              onClick={() => handleTranslateTitles(false)}
                              disabled={isTranslatingTitles}
                            >
                              <Sparkles className={`w-3.5 h-3.5 text-amber-500 ${isTranslatingTitles ? 'animate-spin' : ''}`} />
                              <span>{isTranslatingTitles ? 'Polishing...' : 'Polish Remaining'}</span>
                            </button>
                          );
                        } else {
                          return (
                            <button 
                              className="flex items-center gap-1.5 px-3 h-full text-xs font-bold text-[var(--foreground)] hover:bg-[var(--secondary)] transition-all cursor-pointer disabled:opacity-50 bg-transparent border-none"
                              onClick={() => handleTranslateTitles(false)}
                              disabled={isTranslatingTitles}
                            >
                              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                              <span>{isTranslatingTitles ? 'Polishing...' : 'Polish Titles'}</span>
                            </button>
                          );
                        }
                      })()}
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
                            value={globalSettings.target_language || 'Indonesian'}
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
                                "flex-1 py-1 text-[10px] font-bold rounded-lg transition-all border-none bg-transparent",
                                polishMode === 'soft' ? "bg-[var(--card)] text-[var(--primary)] shadow-sm" : "text-[var(--muted-foreground)]"
                              )}
                            >
                              SOFT
                            </button>
                            <button
                              onClick={() => handlePolishModeChange('hard')}
                              className={cn(
                                "flex-1 py-1 text-[10px] font-bold rounded-lg transition-all border-none bg-transparent",
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
                              onChange={(e) => handlePolishLimitChange(parseInt(e.target.value))}
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
                                const val = parseInt(e.target.value);
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
                                    const val = parseInt(e.target.value);
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
                                        "text-[9px] font-bold px-2 py-0.5 rounded-md transition-all cursor-pointer",
                                        volumeBoundaryType === "raw" 
                                          ? "bg-[var(--primary)] text-[var(--primary-foreground)] shadow-sm" 
                                          : "text-[var(--muted-foreground)] bg-transparent border-transparent"
                                      )}
                                    >
                                      Raw Num
                                    </button>
                                    <button
                                      onClick={() => setVolumeBoundaryType("sequence")}
                                      className={cn(
                                        "text-[9px] font-bold px-2 py-0.5 rounded-md transition-all cursor-pointer",
                                        volumeBoundaryType === "sequence" 
                                          ? "bg-[var(--primary)] text-[var(--primary-foreground)] shadow-sm" 
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
                                    const val = parseInt(e.target.value);
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
                        {thread?.chapters?.some(ch => ch.title_translated) && (
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
                  className="w-full pl-11 pr-4 py-3 rounded-2xl bg-[var(--card)]/50 border border-[var(--border)] focus:border-[var(--primary)]/60 focus:ring-1 focus:ring-[var(--primary)]/30 outline-none text-sm font-medium transition-all text-[var(--foreground)]"
                />
                {chapterSearch && (
                  <button 
                    onClick={() => setChapterSearch('')}
                    className="absolute right-4 top-1/2 -translate-y-1/2 text-xs font-bold text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  >
                    Clear
                  </button>
                )}
              </div>

              {/* Studio Chapter Grid */}
              {(() => {
                const filteredChapters = thread.chapters
                  .map((ch, originalIndex) => ({ ...ch, originalIndex }))
                  .filter(ch => {
                    const query = chapterSearch.toLowerCase();
                    const titleOriginal = (ch.title_original || '').toLowerCase();
                    const titleTranslated = (ch.title_translated || '').toLowerCase();
                    const matchesSearch = titleOriginal.includes(query) || 
                                          titleTranslated.includes(query) || 
                                          `chapter ${ch.order + 1}`.includes(query) ||
                                          `ch. ${ch.order + 1}`.includes(query) ||
                                          String(ch.order + 1).includes(query);
                    
                    if (chapterFilter === 'translated') {
                      return matchesSearch && ch.has_translation;
                    }
                    return matchesSearch;
                  });

                const sortedChapters = [...filteredChapters].sort((a, b) => {
                  return sortOrder === 'asc' ? a.order - b.order : b.order - a.order;
                });

                if (sortedChapters.length === 0) {
                  return (
                    <div className="glass p-12 rounded-3xl border border-[var(--border)] text-center flex flex-col items-center justify-center">
                      <SlidersHorizontal className="w-10 h-10 text-[var(--muted-foreground)]/30 mb-3" />
                      <p className="text-sm font-bold text-[var(--muted-foreground)]">No chapters matching your search or filters.</p>
                    </div>
                  );
                }

                return (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                    {sortedChapters.map((ch) => (
                      <div 
                        key={ch.id}
                        onClick={() => goToChapter(ch.originalIndex)}
                        className={cn(
                          "group relative p-5 rounded-2xl border transition-all duration-300 cursor-pointer text-left flex flex-col justify-between overflow-hidden",
                          lastReadId === ch.id 
                            ? "bg-[var(--primary)]/5 border-[var(--primary)] shadow-[0_0_20px_rgba(0,f2,fe,0.05)]" 
                            : "bg-[var(--card)]/40 border-[var(--border)] hover:border-[var(--primary)]/30 hover:bg-[var(--card)]/60"
                        )}
                      >
                        {/* Top indicators */}
                        <div className="flex items-start justify-between gap-2 mb-3">
                          <span className={cn(
                            "text-sm font-extrabold transition-all line-clamp-2",
                            ch.title_translated ? "text-[var(--foreground)] group-hover:text-[var(--primary)]" : "text-[var(--muted-foreground)] italic opacity-85 group-hover:text-[var(--foreground)]"
                          )}>
                            {ch.title_translated || ch.title_original || `Chapter ${ch.order + 1}`}
                          </span>
                          {/* Translation indicator */}
                          {ch.has_translation ? (
                            <span className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)] flex-shrink-0 mt-1" title="Translated" />
                          ) : (
                            <span className="w-2 h-2 rounded-full bg-[var(--border)] flex-shrink-0 mt-1" title="Not Translated" />
                          )}
                        </div>

                        {/* Bottom info */}
                        <div className="flex items-center justify-between gap-2 mt-4 pt-3 border-t border-[var(--border)]/20">
                          <div className="flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]">
                            <span className="font-mono">{ch.word_count?.toLocaleString() || 0} words</span>
                          </div>
                          
                          {/* Actions / Status badges */}
                          <div className="flex items-center gap-1.5">
                            {ch.translation_status === 'processing' && (
                              <div className="flex items-center gap-1 animate-pulse">
                                <Loader2 className="w-3 h-3 animate-spin text-[var(--accent)]" />
                                <span className="text-[9px] font-bold text-[var(--accent)] uppercase">Translating</span>
                              </div>
                            )}
                            
                            {ch.title_translated ? (
                              <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                <Sparkles className="w-2.5 h-2.5 text-emerald-400" />
                                Polished
                              </span>
                            ) : (
                              <button
                                onClick={(e) => handleSingleTitlePolish(ch.id, e)}
                                disabled={isTranslatingTitles}
                                className="text-[9px] font-bold text-[var(--muted-foreground)] hover:text-[var(--primary)] px-2 py-0.5 rounded-md border border-[var(--border)] bg-transparent hover:bg-[var(--secondary)] transition-all flex items-center gap-1"
                              >
                                <Sparkles className="w-2.5 h-2.5" />
                                Polish
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Left bookmark vertical line */}
                        {lastReadId === ch.id && (
                          <div className="absolute left-0 top-0 bottom-0 w-1 bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)] animate-pulse" />
                        )}
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>
          </div>
        ) : (
          <div className="max-w-screen-2xl mx-auto h-full flex flex-col">
            {/* Top Navigation */}
            <div className="px-6 py-3 flex items-center justify-between border-b border-[var(--border)] bg-[var(--background)]/50">
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
                  CHAPTER {selectedChapterIdx! + 1}
                </span>
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
                  onClick={() => setSelectedChapterIdx(prev => prev! > 0 ? prev! - 1 : prev)}
                  disabled={selectedChapterIdx === 0}
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <Button 
                  variant="outline" 
                  size="icon" 
                  className="rounded-xl border-[var(--border)] h-8 w-8"
                  onClick={() => setSelectedChapterIdx(prev => prev! < thread.chapters.length - 1 ? prev! + 1 : prev)}
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
                  <div className="px-6 py-3 border-b border-[var(--border)] bg-[var(--background)]/50 flex items-center justify-between">
                    <span className="text-[10px] font-black uppercase tracking-widest text-[var(--muted-foreground)]">Source Content</span>
                    <Button variant="ghost" size="icon" className="h-6 w-6 rounded-lg text-[var(--muted-foreground)]">
                      <Info className="w-3 h-3" />
                    </Button>
                  </div>
                  <div className="flex-1 overflow-auto p-10 leading-relaxed font-serif" style={{ fontSize: `${fontSize}px` }}>
                    {loadingContent ? (
                      <div className="flex flex-col items-center justify-center h-full gap-2 opacity-30">
                        <Loader2 className="w-6 h-6 animate-spin" />
                        <span className="text-xs uppercase tracking-widest font-bold">Summoning text...</span>
                      </div>
                    ) : (
                      chapterContent?.content_original || 'No original content found.'
                    )}
                  </div>
                </div>
              )}

              {/* Translated Content */}
              {showTranslated && (
                <div className="flex flex-col h-full overflow-hidden">
                  <div className="px-6 py-3 border-b border-[var(--border)] bg-[var(--background)]/50 flex items-center justify-between">
                    <span className="text-[10px] font-black uppercase tracking-widest text-[var(--accent)]">AI Translation</span>
                    <div className="flex items-center gap-2">
                      {(() => {
                        const hasTranslation = !!chapterContent?.content_translated || !!translatedText;
                        return (
                           <Button 
                            variant={hasTranslation ? "outline" : "default"} 
                            size="sm" 
                            className={`h-7 px-3 text-[10px] rounded-lg gap-1.5 ${hasTranslation ? 'border border-[color-mix(in_srgb,var(--foreground)_30%,transparent)] text-[var(--foreground)] hover:bg-[color-mix(in_srgb,var(--foreground)_10%,transparent)] bg-transparent' : 'shadow-lg shadow-[var(--accent)]/20'}`}
                            onClick={() => handleTranslateChapter(false, '', undefined, undefined, hasTranslation)}
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
                  <div className="flex-1 overflow-auto p-10 leading-relaxed font-serif bg-[var(--background)]" style={{ fontSize: `${fontSize}px` }}>
                    {loadingContent ? (
                      <div className="flex flex-col items-center justify-center h-full gap-2 opacity-30">
                        <Loader2 className="w-6 h-6 animate-spin" />
                        <span className="text-xs uppercase tracking-widest font-bold">Fetching translation...</span>
                      </div>
                    ) : translatedText ? (
                      <div className="whitespace-pre-wrap">{translatedText}</div>
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
          </div>
        )}
      </div>

      {/* Floating Toolbar (Mobile optimized) */}
      {!showChapterList && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-1 p-1.5 glass rounded-2xl border border-[var(--border)] shadow-2xl z-50 animate-in slide-in-from-bottom-8 duration-500">
           <Button variant="ghost" size="icon" className="rounded-xl h-10 w-10 text-[var(--muted-foreground)]" onClick={() => setShowChapterList(true)}>
             <Layout className="w-5 h-5" />
           </Button>
           <div className="w-px h-6 bg-[var(--border)] mx-1" />
           <Button variant="ghost" size="icon" className="rounded-xl h-10 w-10 text-[var(--muted-foreground)]" onClick={() => setShowSettings(!showSettings)}>
             <Settings className="w-5 h-5" />
           </Button>
           <Button variant="ghost" size="icon" className="rounded-xl h-10 w-10 text-[var(--muted-foreground)]" onClick={() => setIsExportModalOpen(true)}>
             <Download className="w-5 h-5" />
           </Button>
           <Button 
             variant="default" 
             size="sm" 
             className="rounded-xl h-10 px-4 ml-2 gap-2 shadow-xl shadow-[var(--accent)]/30"
             onClick={handleSaveTranslation}
           >
             <Save className="w-4 h-4" />
             <span className="text-xs font-bold uppercase">Save</span>
           </Button>
        </div>
      )}

      {/* Export Modal */}
      <ExportModal 
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        threadId={threadId}
        threadTitle={thread.title}
        threadAuthor={thread.author || undefined}
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
        />
      )}
    </div>
  );
}
