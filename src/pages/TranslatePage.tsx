/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useRef, useEffect, useCallback } from 'react';
import { Settings2, ArrowUp, UploadCloud, History, ChevronDown, Loader2, Eraser } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/api';
import { toast } from 'sonner';

interface BookCardProps {
  id?: number;
  imageUrl?: string;
  title: string;
  author: string;
  status: string;
  translations_count?: number;
}

const BookCard: React.FC<BookCardProps> = ({ imageUrl, title, author, status, translations_count }) => {
  return (
    <Card className="overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:shadow-md bg-[var(--card)] border-[var(--border)] group cursor-pointer">
      <CardContent className="p-4">
        <div className="flex gap-4">
          <div className="w-16 h-24 flex-shrink-0 overflow-hidden rounded-md bg-[var(--muted)] flex items-center justify-center">
            {imageUrl ? (
              <img
                src={imageUrl}
                alt={title}
                className="w-full h-full object-cover transition-transform group-hover:scale-105"
              />
            ) : (
              <History className="text-[var(--muted-foreground)] w-8 h-8" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-sm text-[var(--foreground)] truncate">{title}</h3>
            <p className="text-xs text-[var(--muted-foreground)] mt-1 truncate">{author}</p>
            <div className="flex items-center gap-2 mt-3">
              <span className={cn(
                "text-[10px] px-2 py-0.5 rounded-full font-medium uppercase tracking-wider",
                status === 'Translated' ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400" :
                status === 'In Progress' ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400" :
                "bg-[var(--secondary)] text-[var(--muted-foreground)]"
              )}>
                {status}
              </span>
              {translations_count !== undefined && (
                <span className="text-[10px] text-[var(--muted-foreground)]">
                  {translations_count} translations
                </span>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

interface ThreadItem {
  id: number;
  title: string;
  author: string;
  status: string;
  translations_count?: number;
  image_url?: string;
}

interface TranslatePageProps {
  onOpenThread?: (id: number) => void;
}

export default function TranslatePage({ onOpenThread }: TranslatePageProps) {
  const [inputText, setInputText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [recentThreads, setRecentThreads] = useState<ThreadItem[]>([]);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem('lm_model') || '');
  const [selectedThreadId, setSelectedThreadId] = useState<string>('new');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const txtCleanerInputRef = useRef<HTMLInputElement>(null);

  const fetchData = useCallback(async () => {
    try {
      const resThreads = await fetch(getApiUrl('/api/threads'));
      const threads = await resThreads.json();
      setRecentThreads(threads);

      // Fetch global settings to get default LM URL
      const resGs = await fetch(getApiUrl('/api/global-context'));
      const gs = await resGs.json();
      
      const lmUrl = localStorage.getItem('lm_url') || gs.lm_url || 'http://localhost:1234';
      const resModels = await fetch(`${lmUrl}/v1/models`);
      const modelData = await resModels.json();
      const models = modelData.data?.map((m: { id: string }) => m.id) || [];
      setAvailableModels(models);
      
      if (models.length > 0 && !selectedModel) {
        setSelectedModel(models[0]);
      }
    } catch {
      console.error('Failed to fetch data');
    }
  }, [selectedModel]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleProcess = async () => {
    if (!inputText.trim()) return;
    
    const isUrl = inputText.trim().startsWith('http');
    setIsProcessing(true);

    try {
      const endpoint = isUrl ? getApiUrl('/api/threads/import-url') : getApiUrl('/api/translate');
      const body: Record<string, string | number> = isUrl ? { url: inputText.trim() } : { text: inputText.trim() };
      
      if (selectedThreadId !== 'new') {
        body.thread_id = parseInt(selectedThreadId);
      }

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      
      const data = await res.json();
      if (data.thread_id) {
        setInputText('');
        onOpenThread?.(data.thread_id);
      }
    } catch {
      toast.error('Operation failed.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleEpubUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    setIsProcessing(true);

    try {
      const res = await fetch(getApiUrl('/api/upload-epub'), {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        const data = await res.json();
        onOpenThread?.(data.thread_id);
      } else {
        toast.error('Failed to upload EPUB.');
      }
    } catch {
      toast.error('Upload failed.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleTxtCleanerUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    setIsProcessing(true);

    try {
      const res = await fetch(getApiUrl('/api/tools/txt-cleaner-file'), {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error('Failed to clean TXT');

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const disposition = res.headers.get('Content-Disposition') || '';
      const rfc5987 = disposition.match(/filename\*=utf-8''([^;]+)/i);
      const plain = disposition.match(/filename="?([^";]+)"?/i);
      const filename = rfc5987
        ? decodeURIComponent(rfc5987[1])
        : plain
        ? plain[1]
        : `${file.name.replace(/\.txt$/i, "")}_cleaned.txt`;

      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error('TXT Cleaner failed.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-120px)] w-full py-12">
      <div className="w-full max-w-3xl px-4">
        <header className="text-center mb-10">
          <h1 className="text-4xl font-bold text-[var(--foreground)] mb-3 tracking-tight">
            What can I translate for you?
          </h1>
          <p className="text-[var(--muted-foreground)] text-lg">
            Paste a URL, upload an EPUB, or enter text to start.
          </p>
          <p className="text-[var(--muted-foreground)] text-sm mt-2">
            Need quick cleanup only? Upload `.txt` and download cleaned file.
          </p>
        </header>

        <Card className="rounded-3xl bg-[var(--card)] border-[var(--border)] shadow-2xl mb-12 overflow-hidden ring-1 ring-black/5 dark:ring-white/5">
          <CardContent className="p-0">
            <div className="p-8 pb-2">
              <Textarea
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Paste a URL or text to translate..."
                className="min-h-[200px] bg-transparent border-none text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] resize-none focus-visible:ring-0 text-xl leading-relaxed font-hyperlegible"
              />
            </div>

            {/* Bottom Toolbar */}
            <div className="flex flex-col sm:flex-row items-center justify-between px-6 py-4 bg-[var(--muted)]/30 border-t border-[var(--border)] gap-4">
              {/* Left Icons */}
              <div className="flex items-center gap-2">
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
                <input
                  ref={txtCleanerInputRef}
                  type="file"
                  accept=".txt"
                  className="hidden"
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) handleTxtCleanerUpload(file);
                  }}
                />
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="rounded-xl h-10 w-10 text-[var(--muted-foreground)] hover:text-[var(--primary)] hover:bg-[var(--primary)]/10"
                  onClick={() => fileInputRef.current?.click()}
                  title="Upload EPUB"
                >
                  <UploadCloud size={20} />
                </Button>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="rounded-xl h-10 w-10 text-[var(--muted-foreground)] hover:text-[var(--primary)] hover:bg-[var(--primary)]/10"
                  onClick={() => txtCleanerInputRef.current?.click()}
                  title="TXT Cleaner"
                >
                  <Eraser size={20} />
                </Button>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  className="rounded-xl h-10 w-10 text-[var(--muted-foreground)] hover:text-[var(--primary)] hover:bg-[var(--primary)]/10"
                  title="Quick Settings"
                >
                  <Settings2 size={20} />
                </Button>
              </div>

              {/* Right Controls */}
              <div className="flex items-center gap-3 w-full sm:w-auto">
                <div className="flex items-center gap-2 bg-[var(--secondary)] rounded-full border border-[var(--border)] p-1 pr-3 flex-1 sm:flex-initial overflow-hidden">
                  <div className="relative flex-1 sm:flex-initial">
                    <select
                      value={selectedModel}
                      onChange={(e) => {
                        setSelectedModel(e.target.value);
                        localStorage.setItem('lm_model', e.target.value);
                      }}
                      className="appearance-none bg-transparent text-[var(--foreground)] text-xs font-medium pl-3 pr-8 py-2 focus:outline-none cursor-pointer w-full sm:min-w-[120px] sm:max-w-[200px] truncate"
                    >
                      {availableModels.length > 0 ? (
                        availableModels.map(m => <option key={m} value={m}>{m}</option>)
                      ) : (
                        <option value="">No Models</option>
                      )}
                    </select>
                    <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-[var(--muted-foreground)] opacity-50" />
                  </div>

                  <div className="w-px h-5 bg-[var(--border)] shrink-0" />

                  {/* Thread Selector */}
                  <div className="relative flex-1 sm:flex-initial">
                    <select
                      value={selectedThreadId}
                      onChange={(e) => setSelectedThreadId(e.target.value)}
                      className="appearance-none bg-transparent text-[var(--foreground)] text-xs font-medium pl-3 pr-8 py-2 focus:outline-none cursor-pointer w-full sm:min-w-[100px] sm:max-w-[180px] truncate"
                    >
                      <option value="new">New Thread</option>
                      {recentThreads.map(t => (
                        <option key={t.id} value={t.id}>{t.title}</option>
                      ))}
                    </select>
                    <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-[var(--muted-foreground)] opacity-50" />
                  </div>
                </div>

                <Button
                  onClick={handleProcess}
                  disabled={!inputText.trim() || isProcessing}
                  size="icon"
                  className="rounded-full w-12 h-12 bg-[var(--primary)] hover:bg-[var(--primary)]/90 text-[var(--primary-foreground)] shadow-xl transition-all active:scale-90 shrink-0"
                >
                  {isProcessing ? <Loader2 className="animate-spin" size={24} /> : <ArrowUp size={24} />}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="w-full">
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-3">
              Recent Library
              <span className="text-[10px] px-2 py-0.5 rounded bg-[var(--accent)] text-[var(--primary)] uppercase tracking-widest font-black">History</span>
            </h2>
            <Button variant="link" className="text-[var(--primary)] font-bold">See full library</Button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {recentThreads.slice(0, 3).map((thread) => (
              <div key={thread.id} onClick={() => onOpenThread?.(thread.id)}>
                <BookCard 
                  title={thread.title} 
                  author={thread.author || 'Ancient Author'} 
                  status={(thread.translations_count || 0) > 0 ? 'In Progress' : 'Unread'} 
                  translations_count={thread.translations_count}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
