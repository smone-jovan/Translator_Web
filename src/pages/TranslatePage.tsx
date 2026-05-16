import { useState, useRef, useEffect } from 'react';
import { UploadCloud, FileText, ChevronLeft, ChevronRight } from 'lucide-react';

export default function TranslatePage() {
  const [url, setUrl] = useState('');
  const [isExtracting, setIsExtracting] = useState(false);
  const [originalText, setOriginalText] = useState('');
  const [translatedText, setTranslatedText] = useState('');
  const [threadId, setThreadId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // EPUB handling state
  const [epubData, setEpubData] = useState<any>(null);
  const [currentChapterIndex, setCurrentChapterIndex] = useState(0);
  const [isLoadingChapter, setIsLoadingChapter] = useState(false);

  // Fetch chapter text when index changes
  useEffect(() => {
    if (epubData && epubData.chapters && epubData.chapters.length > 0) {
      const fetchChapter = async () => {
        setIsLoadingChapter(true);
        try {
          const ch = epubData.chapters[currentChapterIndex];
          const res = await fetch(`http://localhost:8000/api/threads/${epubData.thread_id}/chapters/${ch.id}`);
          const data = await res.json();
          setOriginalText(data.content_original || '');
          setTranslatedText(data.content_translated || '');
        } catch {
          setOriginalText('⚠️ Failed to load chapter.');
        } finally {
          setIsLoadingChapter(false);
        }
      };
      fetchChapter();
    }
  }, [currentChapterIndex, epubData]);

  const handleExtract = async () => {
    if (!url.trim()) return;
    setIsExtracting(true);
    setOriginalText('');
    setTranslatedText('');
    setEpubData(null);
    setThreadId(null);

    try {
      const res = await fetch('http://localhost:8000/api/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json();
      setOriginalText(data.markdown || data.error || 'No content returned.');
      if (data.thread_id) setThreadId(data.thread_id);
    } catch {
      setOriginalText('⚠️ Backend unreachable. Is FastAPI running on :8000?');
    } finally {
      setIsExtracting(false);
    }
  };

  const handleTranslate = async () => {
    if (!originalText.trim()) return;
    setTranslatedText('');

    try {
      const lmUrl = localStorage.getItem('lm_url') || undefined;
      const lmModel = localStorage.getItem('lm_model') || undefined;

      const res = await fetch('http://localhost:8000/api/translate/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          text: originalText,
          lm_url: lmUrl,
          model: lmModel,
          thread_id: epubData ? epubData.thread_id : threadId,
        }),
      });

      if (!res.body) throw new Error('No readable stream');
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
            } catch (e) {
              // Ignore parse errors on incomplete chunks
            }
          }
        }
      }
    } catch {
      setTranslatedText(prev => prev + '\n⚠️ Streaming failed or endpoint unreachable.');
    }
  };

  const handleEpubUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    setIsExtracting(true);
    setEpubData(null);
    setOriginalText('');
    setTranslatedText('');

    try {
      const res = await fetch('http://localhost:8000/api/upload-epub', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Failed to upload EPUB');
      }
      setEpubData(data);
      setCurrentChapterIndex(0);
      setThreadId(data.thread_id);
    } catch (err: any) {
      setOriginalText(`⚠️ Failed to upload EPUB: ${err.message || 'Backend unreachable'}`);
    } finally {
      setIsExtracting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Input area */}
      <div className="glass rounded-xl p-5">
        <h2 className="text-lg font-medium mb-4 flex items-center gap-2">
          <FileText className="w-5 h-5 text-[var(--accent)]" /> 
          New Translation
        </h2>
        
        <div className="flex flex-col md:flex-row gap-3">
          <div className="flex-1 flex gap-2">
            <input
              type="text"
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleExtract()}
              placeholder="Paste URL here to scrape..."
              className="flex-1 bg-[var(--secondary)] border border-[var(--border)] rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--ring)] transition-colors placeholder:text-[var(--muted-foreground)]"
            />
            <button
              onClick={handleExtract}
              disabled={isExtracting}
              className="bg-[var(--accent)] hover:bg-[var(--muted)] border border-[var(--border)] text-[var(--foreground)] px-5 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              {isExtracting && !epubData ? '...' : 'Extract'}
            </button>
          </div>

          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)] px-2 md:py-0 py-1 justify-center">
            or
          </div>

          {/* EPUB upload button */}
          <div className="flex-shrink-0">
            <input
              ref={fileInputRef}
              type="file"
              accept=".epub"
              className="hidden"
              onChange={e => {
                const file = e.target.files?.[0];
                if (file) handleEpubUpload(file);
              }}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isExtracting}
              className="w-full md:w-auto flex items-center justify-center gap-2 bg-[var(--secondary)] hover:bg-[var(--border)] border border-[var(--border)] text-[var(--foreground)] px-5 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              <UploadCloud className="w-4 h-4" />
              Upload EPUB
            </button>
          </div>
        </div>
        {epubData && (
          <div className="mt-3 text-sm text-[var(--accent)] font-medium">
            Loaded EPUB: {epubData.title} ({epubData.total_chapters} chapters)
          </div>
        )}
      </div>

      {/* Two-pane view */}
      <div className="grid md:grid-cols-2 gap-3" style={{ minHeight: '500px' }}>
        {/* Original */}
        <div className="glass rounded-xl p-4 flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium text-sm flex items-center gap-2 text-[var(--foreground)]">
              Original
            </h3>
            
            {/* Slider / Chapter Selector for EPUB */}
            {epubData && epubData.chapters && epubData.chapters.length > 0 && (
              <div className="flex items-center gap-2 bg-[var(--secondary)] border border-[var(--border)] rounded-md px-2 py-1">
                <button 
                  onClick={() => setCurrentChapterIndex(Math.max(0, currentChapterIndex - 1))}
                  disabled={currentChapterIndex === 0}
                  className="p-1 hover:bg-[var(--accent)] rounded disabled:opacity-30 transition-colors"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="text-xs font-medium min-w-[80px] text-center truncate">
                  Ch. {epubData.chapters[currentChapterIndex].order + 1} / {epubData.total_chapters}
                </span>
                <button 
                  onClick={() => setCurrentChapterIndex(Math.min(epubData.chapters.length - 1, currentChapterIndex + 1))}
                  disabled={currentChapterIndex === epubData.chapters.length - 1}
                  className="p-1 hover:bg-[var(--accent)] rounded disabled:opacity-30 transition-colors"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
          <div className="flex-1 bg-[var(--secondary)] rounded-lg p-4 text-sm leading-relaxed overflow-auto whitespace-pre-wrap text-[var(--foreground)]">
            {isLoadingChapter ? 'Loading chapter...' : (originalText || 'Extracted source text will appear here...')}
          </div>
        </div>

        {/* Translation */}
        <div className="glass rounded-xl p-4 flex flex-col border border-[var(--border)]">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-medium text-sm text-[var(--foreground)]">Translation</h3>
            <button
              onClick={handleTranslate}
              disabled={!originalText || isLoadingChapter}
              className="text-xs bg-[var(--accent)] hover:bg-[var(--muted)] border border-[var(--border)] px-4 py-1.5 font-medium rounded-md transition-colors disabled:opacity-30"
            >
              Translate
            </button>
          </div>
          <div className="flex-1 bg-[var(--secondary)] rounded-lg p-4 text-sm leading-relaxed overflow-auto whitespace-pre-wrap text-[var(--foreground)]">
            {translatedText || 'AI translation will appear here...'}
          </div>
        </div>
      </div>
    </div>
  );
}
