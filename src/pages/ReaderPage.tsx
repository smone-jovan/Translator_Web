import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  ChevronLeft, ChevronRight, BookOpen, Languages, 
  Check, Loader2, Save, Settings, 
  MoreHorizontal, ArrowLeft, Download, Layout, RefreshCw
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

  const scrollRef = useRef<HTMLDivElement>(null);

  // Fetch thread detail
  useEffect(() => {
    const fetchThread = async () => {
      setLoading(true);
      try {
        const res = await fetch(getApiUrl(`/api/threads/${threadId}`));
        const data = await res.json();
        setThread(data);
      } catch {
        console.error('Failed to fetch thread');
      } finally {
        setLoading(false);
      }
    };
    fetchThread();
  }, [threadId]);

  const handleTranslateChapter = useCallback(async (isResume = false, initialText = '') => {
    if (isTranslating || !chapterContent?.content_original) return;
    setIsTranslating(true);
    if (!isResume) setTranslatedText('');
    else setTranslatedText(initialText);

    try {
      const lmUrl = localStorage.getItem('lm_url') || undefined;
      const lmModel = localStorage.getItem('lm_model') || undefined;
      const targetLang = localStorage.getItem('target_language') || 'Indonesian';

      const res = await fetch(getApiUrl('/api/translate/stream'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: chapterContent.content_original,
          lm_url: lmUrl,
          model: lmModel,
          target_lang: targetLang,
          thread_id: threadId,
          chapter_id: chapterContent.id,
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
      
      if (thread && chapterContent) {
        const updatedChapters = [...thread.chapters];
        const chIdx = updatedChapters.findIndex(c => c.id === chapterContent.id);
        if (chIdx !== -1) {
          updatedChapters[chIdx].has_translation = true;
          updatedChapters[chIdx].translation_status = 'done';
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setThread({ ...thread, chapters: updatedChapters });
        }
      }
    } catch {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setTranslatedText(prev => prev + '\n⚠️ Translation failed.');
    } finally {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsTranslating(false);
    }
  }, [chapterContent, isTranslating, threadId, thread]);

  useEffect(() => {
    if (thread && selectedChapterIdx !== null) {
      const ch = thread.chapters[selectedChapterIdx];
      if (!ch) return;
      const fetchContent = async () => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setLoadingContent(true);
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setTranslatedText('');
        try {
          const res = await fetch(getApiUrl(`/api/threads/${threadId}/chapters/${ch.id}`));
          const data: ChapterContent = await res.json();
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setChapterContent(data);
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setTranslatedText(data.content_translated || '');
          if (scrollRef.current) scrollRef.current.scrollTop = 0;
          
          // Auto-resume if status is processing
          if (data.translation_status === 'processing') {
            handleTranslateChapter(true, data.content_translated || '');
          }
        } catch {
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setChapterContent(null);
        } finally {
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setLoadingContent(false);
        }
      };
      fetchContent();
    }
  }, [selectedChapterIdx, threadId, thread, handleTranslateChapter]);

  const handleReTranslate = () => {
    if (window.confirm('Re-translate this chapter? Current translation will be overwritten.')) {
      handleTranslateChapter(false);
    }
  };

  const handleTranslateTitles = async () => {
    if (!thread || isTranslatingTitles) return;
    setIsTranslatingTitles(true);
    try {
      const targetLang = localStorage.getItem('target_language') || 'Indonesian';
      await fetch(getApiUrl(`/api/threads/${threadId}/translate-titles?target_lang=${targetLang}`), {
        method: 'POST'
      });
      // Refresh thread to get new titles
      const res = await fetch(getApiUrl(`/api/threads/${threadId}`));
      const data = await res.json();
      setThread(data);
    } catch {
      alert('Failed to save content');
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
      if (thread) {
        const updatedChapters = [...thread.chapters];
        const chIdx = updatedChapters.findIndex(c => c.id === chapterContent.id);
        if (chIdx !== -1) {
          updatedChapters[chIdx].has_translation = true;
          setThread({ ...thread, chapters: updatedChapters });
        }
      }
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
        <p className="text-[var(--muted-foreground)] font-medium animate-pulse">Opening grimoire...</p>
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
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-2 mb-4">
                <h3 className="font-bold text-sm uppercase tracking-widest text-[var(--muted-foreground)]">Reader Settings</h3>
                <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => setShowSettings(false)}>
                  <MoreHorizontal size={14} />
                </Button>
              </div>

              {/* Typography */}
              <div className="space-y-3">
                <label className="text-[10px] font-bold uppercase tracking-tighter text-[var(--muted-foreground)]">Typography</label>
                <div className="flex items-center justify-between bg-[var(--secondary)] rounded-xl p-2">
                  <Button variant="ghost" size="icon" className="h-10 w-10" onClick={() => setFontSize(f => Math.max(12, f - 2))}>
                    <span className="font-bold">A-</span>
                  </Button>
                  <span className="font-bold text-sm">{fontSize}px</span>
                  <Button variant="ghost" size="icon" className="h-10 w-10" onClick={() => setFontSize(f => Math.min(32, f + 2))}>
                    <span className="font-bold">A+</span>
                  </Button>
                </div>
              </div>

              {/* Display Mode */}
              <div className="space-y-3">
                <label className="text-[10px] font-bold uppercase tracking-tighter text-[var(--muted-foreground)]">Display Mode</label>
                <div className="grid grid-cols-3 gap-2">
                  {['original', 'translated', 'both'].map((m) => (
                    <Button 
                      key={m}
                      variant={displayMode === m ? 'accent' : 'outline'}
                      className="h-12 rounded-xl text-[10px] capitalize font-bold"
                      onClick={() => {
                        setDisplayMode(m);
                        localStorage.setItem('display_mode', m);
                      }}
                    >
                      {m}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div className="pt-4 space-y-2 border-t border-[var(--border)]">
                <Button 
                  variant="outline" 
                  className="w-full h-12 rounded-xl gap-2 text-orange-500 border-orange-500/20 hover:bg-orange-500/10"
                  onClick={() => {
                    handleReTranslate();
                    setShowSettings(false);
                  }}
                  disabled={!chapterContent?.content_original || isTranslating || showChapterList}
                >
                  <RefreshCw size={18} /> Re-translate
                </Button>
                <Button 
                  variant="accent" 
                  className="w-full h-12 rounded-xl gap-2"
                  onClick={handleSaveTranslation}
                  disabled={!translatedText || isTranslating}
                >
                  <Save size={18} /> Save Progress
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Reader Navbar */}
      <nav className="shrink-0 z-30 bg-[var(--background)] border-b border-[var(--border)] px-4 h-16 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-4 min-w-0">
          <Button 
            variant="ghost" 
            size="icon" 
            className="rounded-full"
            onClick={() => {
              if (!showChapterList) setShowChapterList(true);
              else onBack();
            }}
          >
            <ArrowLeft size={20} />
          </Button>
          <div className="min-w-0">
            <h1 className="font-bold text-sm truncate leading-tight">{thread.title}</h1>
            <p className="text-[10px] text-[var(--muted-foreground)] uppercase font-bold tracking-widest mt-0.5">
              {(!showChapterList && selectedChapterIdx !== null && thread.chapters[selectedChapterIdx]) 
                ? `Chapter ${thread.chapters[selectedChapterIdx].order + 1}` 
                : 'Table of Contents'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!showChapterList && (
            <div className="flex items-center gap-2">
              {isTranslating && (
                <div className="flex items-center gap-2 px-3 py-1 bg-blue-500/10 text-blue-500 rounded-full text-[10px] font-bold animate-pulse">
                  <Loader2 size={12} className="animate-spin" /> Translating...
                </div>
              )}
              <Button 
                variant={showSettings ? "accent" : "ghost"} 
                size="icon" 
                className="rounded-full h-10 w-10"
                onClick={() => setShowSettings(!showSettings)}
              >
                <Settings size={20} />
              </Button>
            </div>
          )}
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 overflow-hidden relative">
        {showChapterList ? (
          <div className="h-full overflow-y-auto p-6 md:p-12">
            <div className="max-w-2xl mx-auto space-y-8">
              <div className="flex items-end justify-between">
                <div>
                  <h2 className="text-3xl font-bold tracking-tight">Index</h2>
                  <p className="text-[var(--muted-foreground)] mt-1">{thread.chapter_count} items available</p>
                </div>
                <div className="flex gap-2">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="rounded-xl gap-2" 
                    onClick={handleTranslateTitles}
                    disabled={isTranslatingTitles}
                  >
                    {isTranslatingTitles ? <Loader2 size={14} className="animate-spin" /> : <Languages size={14} />}
                    {isTranslatingTitles ? 'Polishing...' : 'Polish All Titles'}
                  </Button>
                  <Button variant="outline" size="sm" className="rounded-xl gap-2">
                    <Download size={14} /> Bulk Download
                  </Button>
                </div>
              </div>
              
              <div className="grid grid-cols-1 gap-2">
                {thread.chapters.map((ch, idx) => (
                  <button
                    key={ch.id}
                    onClick={() => goToChapter(idx)}
                    className="group flex items-center gap-6 p-4 rounded-2xl bg-[var(--card)] border border-[var(--border)] hover:border-[var(--primary)] hover:shadow-md transition-all text-left"
                  >
                    <span className="text-sm font-bold text-[var(--muted-foreground)] w-8 opacity-40 group-hover:opacity-100 transition-opacity">
                      {(ch.order + 1).toString().padStart(2, '0')}
                    </span>
                    <div className="flex-1 min-w-0">
                      <h4 className="font-bold text-[var(--foreground)] truncate group-hover:text-[var(--primary)] transition-colors">
                        {ch.title_translated || ch.title_original || `Chapter ${ch.order + 1}`}
                      </h4>
                      <p className="text-[10px] text-[var(--muted-foreground)] uppercase font-bold tracking-tighter mt-0.5">
                        {ch.word_count} Words
                      </p>
                    </div>
                    {ch.has_translation ? (
                      <div className="w-8 h-8 rounded-full bg-green-500/10 flex items-center justify-center text-green-500">
                        <Check size={16} />
                      </div>
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-[var(--secondary)] flex items-center justify-center text-[var(--muted-foreground)] opacity-0 group-hover:opacity-100 transition-opacity">
                        <ChevronRight size={16} />
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full flex flex-col">
            {/* Scrollable text area */}
            <div className="flex-1 overflow-y-auto" ref={scrollRef}>
              <div className={cn(
                "max-w-6xl mx-auto p-6 md:p-12 grid gap-12",
                displayMode === 'both' ? 'md:grid-cols-2' : 'grid-cols-1'
              )}>
                {showOriginal && (
                  <div className="space-y-6">
                    <div className="flex items-center gap-3 text-[var(--muted-foreground)] border-b border-[var(--border)] pb-4">
                      <BookOpen size={18} />
                      <span className="text-xs font-bold uppercase tracking-[0.2em]">Source Text</span>
                    </div>
                    <div 
                      className="reader-text leading-relaxed text-[var(--foreground)] opacity-80 whitespace-pre-wrap"
                      style={{ fontSize: `${fontSize}px`, fontFamily: 'var(--font-hyperlegible)' }}
                    >
                      {loadingContent ? (
                        <div className="space-y-4">
                          {Array.from({ length: 12 }).map((_, i) => (
                            <div 
                              key={i} 
                              className="h-4 bg-[var(--secondary)] rounded animate-pulse" 
                              style={{ width: `${60 + (i * 7) % 35}%` }} 
                            />
                          ))}
                        </div>
                      ) : (
                        chapterContent?.content_original || 'No content found.'
                      )}
                    </div>
                  </div>
                )}

                {showTranslated && (
                  <div className="space-y-6">
                    <div className="flex items-center justify-between border-b border-[var(--border)] pb-4">
                      <div className="flex items-center gap-3 text-[var(--primary)]">
                        <Languages size={18} />
                        <span className="text-xs font-bold uppercase tracking-[0.2em]">Translated</span>
                      </div>
                      {!translatedText && !isTranslating && !loadingContent && (
                        <Button 
                          size="sm" 
                          variant="accent" 
                          className="h-8 rounded-lg gap-2 text-[10px]"
                          onClick={() => handleTranslateChapter()}
                        >
                          <Languages size={12} /> Translate Chapter
                        </Button>
                      )}
                    </div>
                    <div 
                      className={cn(
                        "reader-text leading-relaxed text-[var(--foreground)] whitespace-pre-wrap",
                        isTranslating && "opacity-50"
                      )}
                      style={{ fontSize: `${fontSize}px`, fontFamily: 'var(--font-hyperlegible)' }}
                    >
                      {isTranslating ? (
                        <div className="whitespace-pre-wrap">{translatedText}<span className="inline-block w-2 h-4 ml-1 bg-[var(--primary)] animate-pulse" /></div>
                      ) : (
                        translatedText || (
                          <div className="flex flex-col items-center justify-center py-20 text-[var(--muted-foreground)] text-center">
                            <Languages size={48} className="opacity-10 mb-4" />
                            <p className="text-sm font-medium">No translation yet.</p>
                            <Button variant="link" className="mt-2" onClick={() => handleTranslateChapter()}>Begin translation</Button>
                          </div>
                        )
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Bottom Nav */}
            <div className="shrink-0 p-4 bg-[var(--background)] border-t border-[var(--border)] flex items-center justify-between">
              <Button 
                variant="outline" 
                className="rounded-xl h-12 px-6 gap-2"
                disabled={selectedChapterIdx === null || selectedChapterIdx === 0}
                onClick={() => setSelectedChapterIdx(idx => idx !== null ? idx - 1 : 0)}
              >
                <ChevronLeft size={20} /> <span className="hidden sm:inline">Previous</span>
              </Button>
              
              <div className="flex items-center gap-1 sm:gap-2">
                <Button variant="ghost" size="icon" className="rounded-full hidden sm:flex" onClick={() => setShowChapterList(true)}>
                  <Layout size={18} />
                </Button>
                <div className="w-1 h-8 bg-[var(--border)] mx-1 hidden sm:block" />
                <Button variant="ghost" size="icon" className="rounded-full" onClick={() => setShowSettings(!showSettings)}>
                  <Settings size={18} />
                </Button>
                <div className="w-1 h-8 bg-[var(--border)] mx-1" />
                <Button variant="ghost" size="icon" className="rounded-full">
                  <MoreHorizontal size={18} />
                </Button>
              </div>

              <Button 
                variant="outline" 
                className="rounded-xl h-12 px-6 gap-2"
                disabled={selectedChapterIdx === null || selectedChapterIdx === thread.chapters.length - 1}
                onClick={() => setSelectedChapterIdx(idx => idx !== null ? idx + 1 : 0)}
              >
                <span className="hidden sm:inline">Next</span> <ChevronRight size={20} />
              </Button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
