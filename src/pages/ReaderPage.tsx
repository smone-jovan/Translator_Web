import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Loader2, Save, Settings, 
  ArrowLeft, Download, Layout, Sparkles, Eraser, Wand2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getApiUrl } from '@/lib/api';
import ExportModal from '@/components/ExportModal';
import BulkTranslateModal from '@/components/BulkTranslateModal';
import { toast } from 'sonner';
import { useConfirm } from '@/hooks/use-confirm';

// Subcomponents and types
import SettingsOverlay from '@/components/reader/SettingsOverlay';
import NovelHeader from '@/components/reader/NovelHeader';
import ChapterListControls from '@/components/reader/ChapterListControls';
import ChapterGrid from '@/components/reader/ChapterGrid';
import ChapterReader from '@/components/reader/ChapterReader';
import type { ThreadDetail, ChapterContent } from '@/components/reader/types';

interface ReaderPageProps {
  threadId: number;
  onBack: () => void;
  onReadingChapterChange?: (isReading: boolean) => void;
}

const READER_SESSION_MAX_IDLE_MS = 6 * 60 * 60 * 1000;

interface ReaderSessionState {
  threadId: number;
  selectedChapterId: number | null;
  showChapterList: boolean;
  lastActiveAt: number;
}

function getReaderSessionKey(threadId: number) {
  return `readomni_reader_session_${threadId}`;
}

function readReaderSession(threadId: number): ReaderSessionState | null {
  try {
    const raw = localStorage.getItem(getReaderSessionKey(threadId));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ReaderSessionState>;
    if (
      parsed.threadId !== threadId ||
      typeof parsed.showChapterList !== 'boolean' ||
      typeof parsed.lastActiveAt !== 'number'
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
      selectedChapterId: typeof parsed.selectedChapterId === 'number' ? parsed.selectedChapterId : null,
      showChapterList: parsed.showChapterList,
      lastActiveAt: parsed.lastActiveAt,
    };
  } catch {
    localStorage.removeItem(getReaderSessionKey(threadId));
    return null;
  }
}

export default function ReaderPage({ threadId, onBack, onReadingChapterChange }: ReaderPageProps) {
  const { confirm } = useConfirm();
  const initialReaderSession = readReaderSession(threadId);
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedChapterIdx, setSelectedChapterIdx] = useState<number | null>(null);
  const [chapterContent, setChapterContent] = useState<ChapterContent | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);
  const [translatedText, setTranslatedText] = useState('');
  const [isTranslating, setIsTranslating] = useState(false);
  const [showChapterList, setShowChapterList] = useState(initialReaderSession?.showChapterList ?? true);
  const [fontSize, setFontSize] = useState(18);
  const [showSettings, setShowSettings] = useState(false);
  const [displayMode, setDisplayMode] = useState(localStorage.getItem('display_mode') || 'both');
  const [isTranslatingTitles, setIsTranslatingTitles] = useState(false);
  const [lastReadId, setLastReadId] = useState<number | null>(null);
  const [prefetchEnabled, setPrefetchEnabled] = useState(false);
  const [prefetchCount, setPrefetchCount] = useState(2);
  const [prefetchMode, setPrefetchMode] = useState('soft');
  const [globalSettings, setGlobalSettings] = useState<{ lm_url?: string; lm_model?: string; target_language?: string }>({});
  const [polishMode, setPolishMode] = useState<'soft' | 'hard'>('soft');
  const [polishSoftLimit, setPolishSoftLimit] = useState<number>(100);
  const [alwaysHideThoughts, setAlwaysHideThoughts] = useState<boolean>(true);

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
    onReadingChapterChange?.(!showChapterList && selectedChapterIdx !== null);
    return () => onReadingChapterChange?.(false);
  }, [onReadingChapterChange, selectedChapterIdx, showChapterList]);

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

  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [isBulkModalOpen, setIsBulkModalOpen] = useState(false);
  const [chapterSearch, setChapterSearch] = useState('');
  const [controlsVisible, setControlsVisible] = useState(true);
  const [chapterFilter, setChapterFilter] = useState<'all' | 'translated'>('all');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [mobileToolbarVisible, setMobileToolbarVisible] = useState(true);

  const scrollRef = useRef<HTMLDivElement>(null);
  const lastFetchedIdRef = useRef<number | null>(null);
  const initialReaderSessionRef = useRef<ReaderSessionState | null>(initialReaderSession);

  const fetchThread = useCallback(async (opts?: { silent?: boolean }) => {
    const CACHE_KEY = `readomni_thread_cache_${threadId}`;

    // On silent refresh (polling), skip if tab is hidden
    if (opts?.silent && document.hidden) return;

    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}`));
      if (!res.ok) throw new Error('Network response not ok');
      const data: ThreadDetail = await res.json();
      setThread(data);
      if (data.last_read_id) setLastReadId(data.last_read_id);

      // Cache to sessionStorage for fast restore after mobile screen-off reload
      try {
        sessionStorage.setItem(CACHE_KEY, JSON.stringify({ data, ts: Date.now() }));
      } catch { /* quota exceeded — ignore */ }

      const storedSession = initialReaderSessionRef.current;
      if (storedSession?.selectedChapterId) {
        const restoredIdx = data.chapters.findIndex((chapter) => chapter.id === storedSession.selectedChapterId);
        if (restoredIdx !== -1) {
          setSelectedChapterIdx(restoredIdx);
          setShowChapterList(storedSession.showChapterList);
        }
        initialReaderSessionRef.current = null;
      }
    } catch (err) {
      console.error('Failed to fetch thread:', err);
    }
  }, [threadId]);

  useEffect(() => {
    const persistReaderSession = () => {
      const selectedChapterId =
        selectedChapterIdx !== null && thread?.chapters?.[selectedChapterIdx]
          ? thread.chapters[selectedChapterIdx].id
          : null;
      const payload: ReaderSessionState = {
        threadId,
        selectedChapterId,
        showChapterList,
        lastActiveAt: Date.now(),
      };
      localStorage.setItem(getReaderSessionKey(threadId), JSON.stringify(payload));
    };

    persistReaderSession();
    window.addEventListener('pagehide', persistReaderSession);
    document.addEventListener('visibilitychange', persistReaderSession);

    return () => {
      window.removeEventListener('pagehide', persistReaderSession);
      document.removeEventListener('visibilitychange', persistReaderSession);
    };
  }, [thread, threadId, selectedChapterIdx, showChapterList]);

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
              currentTitle: `Processing Chapter ${chapterIds[completed - 1]}` 
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

  // Initial Load — parallel fetch with sessionStorage fast-restore
  useEffect(() => {
    const CACHE_KEY = `readomni_thread_cache_${threadId}`;
    const CACHE_TTL = 5 * 60 * 1000;

    const init = async () => {
      // Instant restore from cache while real fetch runs in background
      try {
        const raw = sessionStorage.getItem(CACHE_KEY);
        if (raw) {
          const { data, ts } = JSON.parse(raw) as { data: ThreadDetail; ts: number };
          if (Date.now() - ts < CACHE_TTL) {
            setThread(data);
            if (data.last_read_id) setLastReadId(data.last_read_id);
            const storedSession = initialReaderSessionRef.current;
            if (storedSession?.selectedChapterId) {
              const restoredIdx = data.chapters.findIndex(c => c.id === storedSession.selectedChapterId);
              if (restoredIdx !== -1) {
                setSelectedChapterIdx(restoredIdx);
                setShowChapterList(storedSession.showChapterList);
              }
              initialReaderSessionRef.current = null;
            }
            setLoading(false);
          }
        }
      } catch { /* ignore */ }

      // Parallel: fetch thread + global settings simultaneously
      const [, gsData] = await Promise.allSettled([
        fetchThread(),
        fetch(getApiUrl('/api/global-context')).then(r => r.ok ? r.json() : null)
      ]);

      if (gsData.status === 'fulfilled' && gsData.value) {
        const gs = gsData.value;
        setPrefetchEnabled(gs.prefetch_enabled === 1);
        setPrefetchCount(gs.prefetch_count || 2);
        setPrefetchMode(gs.prefetch_mode || 'soft');
        setPolishMode(gs.polish_mode || 'soft');
        setPolishSoftLimit(gs.polish_soft_limit || 100);
        setAlwaysHideThoughts(gs.always_hide_thoughts !== 0);
        setGlobalSettings({ lm_url: gs.lm_url, lm_model: gs.lm_model, target_language: gs.target_language });
      }

      setLoading(false);
    };
    init();
  }, [fetchThread, threadId]);

  // Polling for background updates (ADR-013) — paused when tab is hidden
  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    const hasProcessing = thread?.chapters?.some(c => c.translation_status === 'processing') || false;

    if (prefetchEnabled || hasProcessing) {
      interval = setInterval(() => {
        fetchThread({ silent: true }); // skip if tab hidden
      }, 5000);
    }
    return () => { if (interval) clearInterval(interval); };
  }, [prefetchEnabled, fetchThread, thread?.chapters]);

  const handleTranslateChapter = useCallback(async (
    isResume = false, 
    initialText = '', 
    overrideContent?: string, 
    overrideId?: number, 
    forceOverwrite = false
  ) => {
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
            } catch {
              // Ignore invalid JSON chunks gracefully
            }
          }
        }
      }
      
      // Update thread state to show it has translation
      await fetchThread();
    } catch (err) {
      console.error('Translation error:', err);
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
        if (!res.ok) throw new Error('Failed to fetch chapter content');
        const data: ChapterContent = await res.json();
        
        lastFetchedIdRef.current = ch.id;
        setChapterContent(data);
        setTranslatedText(data.content_translated || '');
        setLastReadId(ch.id);
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== 'AbortError') {
          setChapterContent(null);
          lastFetchedIdRef.current = null;
        }
      } finally {
        setLoadingContent(false);
      }
    };
    
    fetchContent();
    return () => abortController.abort();
  }, [selectedChapterIdx, threadId, thread]);

  // Auto-detect starting chapter number based on the first chapter's original title
  const getAutoStartNum = useCallback(() => {
    if (!thread || !thread.chapters || thread.chapters.length === 0) return 1;
    const firstTitle = thread.chapters[0].title_original || '';
    const match = firstTitle.match(/(?:chapter|bab|vol|volume|ch|第)\s*(\d+)/i);
    if (match) return parseInt(match[1], 10);
    const digitMatch = firstTitle.match(/\d+/);
    if (digitMatch) return parseInt(digitMatch[0], 10);
    return 1;
  }, [thread]);

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

  // Infinite Polish - All
  const handleTranslateTitles = async (isRepolish = false) => {
    if (!thread || isTranslatingTitles) return;

    if (isRepolish) {
      const isConfirmed = await confirm({
        title: 'Repolish Titles',
        description: 'All existing polished titles will be overwritten by AI. Continue?',
        confirmText: 'Overwrite',
        variant: 'destructive'
      });
      if (!isConfirmed) return;
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
      toast.success('Titles polished successfully.');
    } catch (err) {
      console.error('Title translation failed:', err);
      toast.error('Title translation failed.');
    } finally {
      setIsTranslatingTitles(false);
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
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/chapters/${chapterContent.id}/translation`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ translated_text: translatedText })
      });
      if (!res.ok) throw new Error('Failed to save translation');
      await fetchThread();
    } catch (err) {
      console.error('Failed to save:', err);
    }
  };

  const runCleanerTool = async (tool: 'txt-cleaner' | 'epub-cleaner') => {
    const label = tool === 'txt-cleaner' ? 'TXT Cleaner' : 'EPUB Cleaner';
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/${tool}`), { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `${label} failed`);
      await fetchThread();

      const message = `${label} finished. Scanned: ${data.chapters_scanned}, Updated: ${data.chapters_updated}, Deleted: ${data.chapters_deleted}, Removed lines: ${data.lines_removed}`;
      if (data.chapters_updated > 0 || data.chapters_deleted > 0) {
        toast.success(message);
      } else {
        toast.info(message);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error';
      toast.error(`${label} failed: ${msg}`);
    }
  };

  const goToChapter = (idx: number) => {
    setSelectedChapterIdx(idx);
    setShowChapterList(false);
    setControlsVisible(true);
    setIsTranslating(false);
    setMobileToolbarVisible(true);
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
        <SettingsOverlay 
          fontSize={fontSize}
          setFontSize={setFontSize}
          displayMode={displayMode}
          setDisplayMode={setDisplayMode}
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
        />
      )}

      {/* Header Bar */}
      <div 
        className={`flex items-center gap-4 px-6 border-[var(--border)] bg-[var(--background)]/80 backdrop-blur-md z-30 transition-all duration-300 ease-in-out ${
          showChapterList || controlsVisible 
            ? 'h-16 py-4 border-b opacity-100' 
            : 'h-0 py-0 border-b-0 opacity-0 overflow-hidden pointer-events-none'
        }`}
      >
        <button onClick={onBack} className="p-2 hover:bg-[var(--secondary)] rounded-full transition-all active:scale-95 border-none bg-transparent cursor-pointer">
          <ArrowLeft className="w-5 h-5 text-[var(--foreground)]" />
        </button>
        <div className="flex-1 min-w-0 text-left">
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
          {showChapterList && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => runCleanerTool('txt-cleaner')}
                className="rounded-xl border-[var(--border)]"
                title="TXT Cleaner"
              >
                <Eraser className="w-4 h-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => runCleanerTool('epub-cleaner')}
                className="rounded-xl border-[var(--border)]"
                title="EPUB Cleaner"
              >
                <Wand2 className="w-4 h-4" />
              </Button>
            </>
          )}
          {!showChapterList && (
            <Button variant="outline" size="sm" onClick={handleSaveTranslation} className="rounded-xl border-[var(--border)] flex gap-1.5 px-2.5 sm:px-3" title="Save Translation">
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

      <div className={`flex-1 bg-[var(--background)] custom-scrollbar ${showChapterList ? 'overflow-auto' : 'overflow-hidden'}`} ref={scrollRef}>
        {showChapterList ? (
          <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 text-left pb-16">
            <NovelHeader 
              thread={thread}
              onReadNow={() => {
                const startIdx = thread.chapters.findIndex(ch => ch.id === lastReadId);
                goToChapter(startIdx !== -1 ? startIdx : 0);
              }}
              onOpenBulkModal={() => setIsBulkModalOpen(true)}
            />

            <ChapterListControls 
              thread={thread}
              chapterFilter={chapterFilter}
              setChapterFilter={setChapterFilter}
              sortOrder={sortOrder}
              setSortOrder={setSortOrder}
              chapterSearch={chapterSearch}
              setChapterSearch={setChapterSearch}
              targetLanguage={globalSettings.target_language || 'Indonesian'}
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
            />

            <ChapterGrid 
              thread={thread}
              chapterSearch={chapterSearch}
              chapterFilter={chapterFilter}
              sortOrder={sortOrder}
              lastReadId={lastReadId}
              isTranslatingTitles={isTranslatingTitles}
              goToChapter={goToChapter}
              handleSingleTitlePolish={handleSingleTitlePolish}
            />
          </div>
        ) : (
          selectedChapterIdx !== null && (
            <ChapterReader 
              thread={thread}
              selectedChapterIdx={selectedChapterIdx}
              setSelectedChapterIdx={setSelectedChapterIdx}
              chapterContent={chapterContent}
              loadingContent={loadingContent}
              translatedText={translatedText}
              isTranslating={isTranslating}
              displayMode={displayMode}
              setDisplayMode={setDisplayMode}
              fontSize={fontSize}
              handleTranslateChapter={handleTranslateChapter}
              setShowChapterList={setShowChapterList}
              alwaysHideThoughts={alwaysHideThoughts}
              setAlwaysHideThoughts={setAlwaysHideThoughts}
              controlsVisible={controlsVisible}
              setControlsVisible={setControlsVisible}
              mobileToolbarVisible={mobileToolbarVisible}
              setMobileToolbarVisible={setMobileToolbarVisible}
            />
          )
        )}
      </div>

      {/* Mobile Floating Bottom Toolbar (Only visible when reading a chapter) */}
      {!showChapterList && (
        <div 
          className={`fixed bottom-0 left-0 right-0 z-40 md:hidden px-4 pb-4 pt-2 transition-all duration-300 ease-in-out ${
            mobileToolbarVisible ? "translate-y-0 opacity-100" : "translate-y-28 opacity-0 pointer-events-none"
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
                if (selectedChapterIdx !== null && thread && selectedChapterIdx < thread.chapters.length - 1) {
                  goToChapter(selectedChapterIdx + 1);
                }
              }}
              disabled={selectedChapterIdx === null || !thread || selectedChapterIdx >= thread.chapters.length - 1}
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
        />
      )}
    </div>
  );
}
