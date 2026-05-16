import { useState, useEffect } from 'react';
import { ChevronLeft, ChevronRight, BookOpen, Languages, Check, Loader2 } from 'lucide-react';

interface Chapter {
  id: number;
  order: number;
  title: string | null;
  word_count: number;
  has_translation: boolean;
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
  title: string | null;
  content_original: string | null;
  content_translated: string | null;
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

  // Fetch thread detail
  useEffect(() => {
    const fetchThread = async () => {
      setLoading(true);
      try {
        const res = await fetch(`http://localhost:8000/api/threads/${threadId}`);
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

  // Fetch chapter content when selected
  useEffect(() => {
    if (thread && selectedChapterIdx !== null) {
      const ch = thread.chapters[selectedChapterIdx];
      if (!ch) return;
      const fetchContent = async () => {
        setLoadingContent(true);
        setTranslatedText('');
        try {
          const res = await fetch(`http://localhost:8000/api/threads/${threadId}/chapters/${ch.id}`);
          const data: ChapterContent = await res.json();
          setChapterContent(data);
          setTranslatedText(data.content_translated || '');
        } catch {
          setChapterContent(null);
        } finally {
          setLoadingContent(false);
        }
      };
      fetchContent();
    }
  }, [selectedChapterIdx, thread, threadId]);

  const handleTranslateChapter = async () => {
    if (!chapterContent?.content_original) return;
    setIsTranslating(true);
    setTranslatedText('');

    try {
      const lmUrl = localStorage.getItem('lm_url') || undefined;
      const lmModel = localStorage.getItem('lm_model') || undefined;

      const res = await fetch('http://localhost:8000/api/translate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: chapterContent.content_original,
          lm_url: lmUrl,
          model: lmModel,
          thread_id: threadId,
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
    } catch {
      setTranslatedText(prev => prev + '\n⚠️ Translation failed.');
    } finally {
      setIsTranslating(false);
    }
  };

  const goToChapter = (idx: number) => {
    setSelectedChapterIdx(idx);
    setShowChapterList(false);
  };

  const goPrev = () => {
    if (selectedChapterIdx !== null && selectedChapterIdx > 0) {
      setSelectedChapterIdx(selectedChapterIdx - 1);
    }
  };

  const goNext = () => {
    if (thread && selectedChapterIdx !== null && selectedChapterIdx < thread.chapters.length - 1) {
      setSelectedChapterIdx(selectedChapterIdx + 1);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--muted-foreground)]" />
      </div>
    );
  }

  if (!thread) {
    return (
      <div className="text-center py-20 text-[var(--muted-foreground)]">
        Thread not found. 
        <button onClick={onBack} className="ml-2 underline">Back to Library</button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="glass rounded-xl p-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              if (selectedChapterIdx !== null && !showChapterList) {
                setShowChapterList(true);
                setSelectedChapterIdx(null);
                setChapterContent(null);
                setTranslatedText('');
              } else {
                onBack();
              }
            }}
            className="p-2 rounded-lg hover:bg-[var(--secondary)] transition-colors"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-medium truncate flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-[var(--accent)] shrink-0" />
              {thread.title}
            </h2>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
              {thread.chapter_count} chapters · {thread.source_type.toUpperCase()}
            </p>
          </div>
        </div>
      </div>

      {/* Chapter List View */}
      {showChapterList && (
        <div className="glass rounded-xl p-4">
          <h3 className="font-medium text-sm mb-3 text-[var(--foreground)]">Chapters</h3>
          <div className="space-y-1.5">
            {thread.chapters.map((ch, idx) => (
              <button
                key={ch.id}
                onClick={() => goToChapter(idx)}
                className="w-full text-left bg-[var(--secondary)] hover:bg-[var(--accent)] border border-[var(--border)] rounded-lg px-4 py-3 flex items-center gap-3 transition-colors group"
              >
                <span className="text-xs font-mono text-[var(--muted-foreground)] w-8 shrink-0">
                  {ch.order + 1}
                </span>
                <span className="flex-1 text-sm truncate">
                  {ch.title || `Chapter ${ch.order + 1}`}
                </span>
                <span className="text-xs text-[var(--muted-foreground)]">
                  {ch.word_count} words
                </span>
                {ch.has_translation && (
                  <Check className="w-4 h-4 text-green-500 shrink-0" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Chapter Reader View */}
      {!showChapterList && selectedChapterIdx !== null && (
        <>
          {/* Chapter navigation bar */}
          <div className="glass rounded-xl p-3 flex items-center justify-between">
            <button
              onClick={goPrev}
              disabled={selectedChapterIdx === 0}
              className="flex items-center gap-1 text-sm px-3 py-1.5 rounded-md hover:bg-[var(--secondary)] disabled:opacity-30 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" /> Prev
            </button>

            <span className="text-sm font-medium">
              Ch. {thread.chapters[selectedChapterIdx].order + 1} / {thread.chapter_count}
              {thread.chapters[selectedChapterIdx].title && (
                <span className="text-[var(--muted-foreground)] ml-2 hidden sm:inline">
                  — {thread.chapters[selectedChapterIdx].title}
                </span>
              )}
            </span>

            <button
              onClick={goNext}
              disabled={selectedChapterIdx === thread.chapters.length - 1}
              className="flex items-center gap-1 text-sm px-3 py-1.5 rounded-md hover:bg-[var(--secondary)] disabled:opacity-30 transition-colors"
            >
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Two-pane original + translation */}
          <div className="grid md:grid-cols-2 gap-3" style={{ minHeight: '500px' }}>
            {/* Original */}
            <div className="glass rounded-xl p-4 flex flex-col">
              <h3 className="font-medium text-sm mb-3 text-[var(--foreground)]">Original</h3>
              <div className="flex-1 bg-[var(--secondary)] rounded-lg p-4 text-sm leading-relaxed overflow-auto whitespace-pre-wrap text-[var(--foreground)]">
                {loadingContent
                  ? 'Loading chapter...'
                  : (chapterContent?.content_original || 'No content.')}
              </div>
            </div>

            {/* Translation */}
            <div className="glass rounded-xl p-4 flex flex-col border border-[var(--border)]">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-sm text-[var(--foreground)]">Translation</h3>
                <button
                  onClick={handleTranslateChapter}
                  disabled={!chapterContent?.content_original || isTranslating || loadingContent}
                  className="flex items-center gap-1.5 text-xs bg-[var(--accent)] hover:bg-[var(--muted)] border border-[var(--border)] px-4 py-1.5 font-medium rounded-md transition-colors disabled:opacity-30"
                >
                  {isTranslating && <Loader2 className="w-3 h-3 animate-spin" />}
                  <Languages className="w-3.5 h-3.5" />
                  {isTranslating ? 'Translating...' : 'Translate'}
                </button>
              </div>
              <div className="flex-1 bg-[var(--secondary)] rounded-lg p-4 text-sm leading-relaxed overflow-auto whitespace-pre-wrap text-[var(--foreground)]">
                {translatedText || 'Click Translate to start.'}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
