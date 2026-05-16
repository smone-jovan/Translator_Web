import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  ChevronLeft, ChevronRight, BookOpen, Languages, 
  Check, Loader2, Save, Settings, 
  RefreshCw, ArrowLeft, Download, Layout, Sparkles,
  Info
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getApiUrl } from '@/lib/api';

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
  const [globalSettings, setGlobalSettings] = useState<{lm_url?: string, lm_model?: string, target_language?: string}>({});

  const scrollRef = useRef<HTMLDivElement>(null);
  const lastFetchedIdRef = useRef<number | null>(null);

  const fetchThread = useCallback(async () => {
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}`));
      const data = await res.json();
      setThread(data);
    } catch {
      console.error('Failed to fetch thread');
    }
  }, [threadId]);

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

  const handleTranslateChapter = useCallback(async (isResume = false, initialText = '', overrideContent?: string, overrideId?: number) => {
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
  }, [isTranslating, threadId, fetchThread, chapterContent?.content_original, chapterContent?.id]);

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
      const targetLang = localStorage.getItem('target_language') || 'Indonesian';
      const url = getApiUrl(`/api/threads/${threadId}/translate-titles?repolish=true&chapter_id=${chapterId}&target_lang=${targetLang}`);
      
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
    
    if (isRepolish && !window.confirm('All existing polished titles will be overwritten by AI. Continue?')) {
      return;
    }

    setIsTranslatingTitles(true);
    try {
      const targetLang = globalSettings.target_language || 'Indonesian';
      const url = getApiUrl(`/api/threads/${threadId}/translate-titles?target_lang=${targetLang}${isRepolish ? '&repolish=true' : ''}`);
      
      const res = await fetch(url, { method: 'POST' });
      if (!res.ok) throw new Error('Failed');
      await fetchThread();
    } catch {
      alert('Title translation failed.');
    } finally {
      setIsTranslatingTitles(false);
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
                <div className="flex items-center gap-4 mt-3">
                  <Button variant="outline" size="sm" onClick={() => setFontSize(f => Math.max(12, f - 1))} className="flex-1 border-[var(--border)]">-</Button>
                  <span className="text-sm font-mono w-8 text-center">{fontSize}</span>
                  <Button variant="outline" size="sm" onClick={() => setFontSize(f => Math.min(32, f + 1))} className="flex-1 border-[var(--border)]">+</Button>
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
          <h1 className="text-lg font-bold truncate tracking-tight">{thread.title}</h1>
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
          <Button variant="outline" size="sm" onClick={() => setShowSettings(!showSettings)} className="rounded-xl border-[var(--border)]">
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto bg-[var(--background)] custom-scrollbar" ref={scrollRef}>
        {showChapterList ? (
          <div className="max-w-5xl mx-auto p-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-8 gap-4">
              <div>
                <h2 className="text-2xl font-black flex items-center gap-3">
                  Chapter List
                  <span className="text-xs font-normal text-[var(--muted-foreground)] bg-[var(--secondary)] px-2 py-0.5 rounded-full">
                    {thread.chapters.length} Total
                  </span>
                </h2>
                <p className="text-[var(--muted-foreground)] text-sm mt-1">Select a chapter to begin translation or reading.</p>
              </div>
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="rounded-xl gap-2 border-[var(--border)] hover:bg-[var(--secondary)]"
                  onClick={() => handleTranslateTitles(false)}
                  disabled={isTranslatingTitles}
                >
                  <Languages className="w-4 h-4" />
                  Polish All
                </Button>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="rounded-xl text-[var(--muted-foreground)] hover:text-[var(--accent)]"
                  onClick={() => handleTranslateTitles(true)}
                  disabled={isTranslatingTitles}
                  title="Repolish all titles"
                >
                  <RefreshCw className={`w-4 h-4 ${isTranslatingTitles ? 'animate-spin' : ''}`} />
                </Button>
              </div>
            </div>

            <div className="glass rounded-3xl overflow-hidden border border-[var(--border)] shadow-xl">
              <table className="w-full text-left border-collapse">
                <thead className="bg-[var(--secondary)]/50 border-b border-[var(--border)]">
                  <tr>
                    <th className="px-6 py-4 text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest w-16">#</th>
                    <th className="px-6 py-4 text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Original Title</th>
                    <th className="px-6 py-4 text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Polished Title</th>
                    <th className="px-6 py-4 text-right text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest w-24">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {thread.chapters.map((ch, idx) => (
                    <tr 
                      key={ch.id}
                      onClick={() => goToChapter(idx)}
                      className={`group hover:bg-[var(--accent)]/5 transition-all cursor-pointer relative ${lastReadId === ch.id ? 'bg-[var(--accent)]/5' : ''}`}
                    >
                      {/* Read Progress Indicator */}
                      {lastReadId === ch.id && (
                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]" />
                      )}
                      
                      <td className="px-6 py-4 font-mono text-[10px] text-[var(--muted-foreground)]">
                        {String(ch.order + 1).padStart(3, '0')}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex flex-col">
                          <span className="text-xs font-medium text-[var(--muted-foreground)] truncate max-w-[200px]">
                            {ch.title_original || `Chapter ${ch.order + 1}`}
                          </span>
                          <span className="text-[10px] text-[var(--muted-foreground)]/50 mt-0.5">{ch.word_count} words</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          {ch.title_translated ? (
                            <span className="text-sm font-semibold text-[var(--foreground)]">
                              {ch.title_translated}
                            </span>
                          ) : (
                            <span className="text-xs text-[var(--muted-foreground)] italic opacity-50">Not polished yet</span>
                          )}
                          {ch.has_translation && (
                            <div className="w-1.5 h-1.5 rounded-full bg-green-500" title="Translated" />
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex justify-end gap-2">
                          <Button 
                            variant="ghost"
                            size="icon"
                            onClick={(e) => handleSingleTitlePolish(ch.id, e)}
                            disabled={isTranslatingTitles}
                            className="rounded-xl h-9 w-9 text-[var(--muted-foreground)] hover:text-[var(--accent)] hover:bg-[var(--accent)]/10 transition-all opacity-40 group-hover:opacity-100 disabled:opacity-20"
                            title="Repolish this title"
                          >
                            <RefreshCw className={`w-4 h-4 ${isTranslatingTitles ? 'animate-spin' : ''}`} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
                <span className="text-xs font-bold tracking-tight">
                  CHAPTER {selectedChapterIdx! + 1}
                </span>
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
                      <Button 
                        variant="default" 
                        size="sm" 
                        className="h-7 px-3 text-[10px] rounded-lg gap-1.5 shadow-lg shadow-[var(--accent)]/20"
                        onClick={() => handleTranslateChapter()}
                        disabled={isTranslating}
                      >
                        {isTranslating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                        {isTranslating ? 'TRANSLATING' : 'GENERATE'}
                      </Button>
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
    </div>
  );
}
