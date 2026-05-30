/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useRef, useEffect, useCallback } from 'react';
import { Settings2, ArrowUp, UploadCloud, History, ChevronDown, Loader2, Eraser, Cpu, Bot, BookOpen, Plus, Check } from 'lucide-react';
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
  cover_image?: string;
}

interface TranslatePageProps {
  onOpenThread?: (id: number) => void;
  onNavigateToSettings?: () => void;
  onNavigateToLibrary?: () => void;
}

export default function TranslatePage({ onOpenThread, onNavigateToSettings, onNavigateToLibrary }: TranslatePageProps) {
  const [inputText, setInputText] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [recentThreads, setRecentThreads] = useState<ThreadItem[]>([]);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem('lm_model') || '');
  const [selectedThreadId, setSelectedThreadId] = useState<string>('new');

  const fileInputRef = useRef<HTMLInputElement>(null);
  const txtCleanerInputRef = useRef<HTMLInputElement>(null);
  const modelDropdownRef = useRef<HTMLDivElement>(null);
  const threadDropdownRef = useRef<HTMLDivElement>(null);

  const [openModelDropdown, setOpenModelDropdown] = useState(false);
  const [openThreadDropdown, setOpenThreadDropdown] = useState(false);
  const [providerLabel, setProviderLabel] = useState('lm_studio');

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (modelDropdownRef.current && !modelDropdownRef.current.contains(e.target as Node)) {
        setOpenModelDropdown(false);
      }
      if (threadDropdownRef.current && !threadDropdownRef.current.contains(e.target as Node)) {
        setOpenThreadDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const fetchData = useCallback(async () => {
    try {
      const resThreads = await fetch(getApiUrl('/api/threads'));
      const threads = await resThreads.json();
      setRecentThreads(threads);

      // Fetch global settings to determine provider and model
      const resGs = await fetch(getApiUrl('/api/global-context'));
      const gs = await resGs.json();
      
      const provider = gs.llm_provider || 'lm_studio';
      const providerLabels: Record<string, string> = {
        lm_studio: 'LM Studio',
        openai: 'OpenAI',
        gemini: 'Gemini',
      };
      setProviderLabel(providerLabels[provider] || provider);
      
      if (provider === 'lm_studio') {
        // For LM Studio, fetch available models from the local server
        const lmUrl = localStorage.getItem('lm_url') || gs.lm_url || 'http://localhost:1234';
        try {
          const resModels = await fetch(`${lmUrl}/v1/models`);
          const modelData = await resModels.json();
          const models = modelData.data?.map((m: { id: string }) => m.id) || [];
          setAvailableModels(models);
          if (models.length > 0 && !selectedModel) {
            setSelectedModel(models[0]);
          }
        } catch {
          // LM Studio might not be running — show the configured model as fallback
          if (gs.lm_model) {
            setAvailableModels([gs.lm_model]);
            if (!selectedModel) setSelectedModel(gs.lm_model);
          }
        }
      } else if (provider === 'openai') {
        // For OpenAI, show the configured model
        const model = gs.openai_model || 'gpt-4o';
        setAvailableModels([model]);
        if (!selectedModel) setSelectedModel(model);
      } else if (provider === 'gemini') {
        // For Gemini, show the configured model
        const model = gs.gemini_model || 'gemini-2.5-flash';
        setAvailableModels([model]);
        if (!selectedModel) setSelectedModel(model);
      }
    } catch {
      console.error('Failed to fetch data');
    }
  }, [selectedModel]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Silently refresh recent threads when batch translation completes
  useEffect(() => {
    const handleBatchCompleted = () => {
      fetch(getApiUrl('/api/threads'))
        .then(res => res.json())
        .then(data => setRecentThreads(data))
        .catch(() => {});
    };
    window.addEventListener('batch-completed', handleBatchCompleted);
    return () => window.removeEventListener('batch-completed', handleBatchCompleted);
  }, []);

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

        <Card className="rounded-3xl bg-[var(--card)] border-[var(--border)] shadow-2xl mb-12 ring-1 ring-black/5 dark:ring-white/5">
          <CardContent className="p-0">
            <div className="p-8 pb-2 overflow-hidden">
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
                  onClick={() => onNavigateToSettings?.()}
                >
                  <Settings2 size={20} />
                </Button>
              </div>

              {/* Right Controls */}
              <div className="flex items-center gap-3 w-full sm:w-auto">
                <div className="flex items-center gap-2 bg-[var(--secondary)] rounded-full border border-[var(--border)] p-1 pr-3 flex-1 sm:flex-initial overflow-visible">
                  {/* Model Dropdown */}
                  <div ref={modelDropdownRef} className="relative flex-1 sm:flex-initial">
                    <button
                      onClick={() => { setOpenModelDropdown(!openModelDropdown); setOpenThreadDropdown(false); }}
                      className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-[var(--foreground)] hover:bg-[var(--primary)]/10 transition-colors cursor-pointer w-full sm:min-w-[140px] sm:max-w-[220px]"
                    >
                      <Cpu size={14} className="text-[var(--primary)] shrink-0" />
                      <span className="truncate">{selectedModel || 'Select Model'}</span>
                      <ChevronDown size={12} className={cn("ml-auto shrink-0 text-[var(--muted-foreground)] transition-transform", openModelDropdown && "rotate-180")} />
                    </button>
                    {openModelDropdown && (
                      <div className="absolute top-full left-0 mt-2 w-72 max-h-64 overflow-y-auto bg-[var(--card)] border border-[var(--border)] rounded-2xl shadow-2xl z-50 py-2 animate-in fade-in zoom-in-95 duration-150">
                        <div className="px-3 py-2 flex items-center gap-2 border-b border-[var(--border)] mb-1">
                          <span className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)]">{providerLabel}</span>
                        </div>
                        {availableModels.length > 0 ? availableModels.map(m => (
                          <button
                            key={m}
                            onClick={() => {
                              setSelectedModel(m);
                              localStorage.setItem('lm_model', m);
                              setOpenModelDropdown(false);
                            }}
                            className={cn(
                              "w-full text-left px-3 py-2.5 text-xs flex items-center gap-3 transition-colors",
                              selectedModel === m
                                ? "bg-[var(--primary)]/10 text-[var(--primary)] font-semibold"
                                : "text-[var(--foreground)] hover:bg-[var(--secondary)]"
                            )}
                          >
                            <Bot size={14} className={selectedModel === m ? "text-[var(--primary)]" : "text-[var(--muted-foreground)]"} />
                            <span className="truncate flex-1">{m}</span>
                            {selectedModel === m && <Check size={14} className="text-[var(--primary)] shrink-0" />}
                          </button>
                        )) : (
                          <div className="px-3 py-4 text-xs text-[var(--muted-foreground)] text-center">
                            No models available
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="w-px h-5 bg-[var(--border)] shrink-0" />

                  {/* Thread Dropdown */}
                  <div ref={threadDropdownRef} className="relative flex-1 sm:flex-initial">
                    <button
                      onClick={() => { setOpenThreadDropdown(!openThreadDropdown); setOpenModelDropdown(false); }}
                      className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-[var(--foreground)] hover:bg-[var(--primary)]/10 transition-colors cursor-pointer w-full sm:min-w-[120px] sm:max-w-[200px]"
                    >
                      <BookOpen size={14} className="text-[var(--primary)] shrink-0" />
                      <span className="truncate">
                        {selectedThreadId === 'new'
                          ? 'New Thread'
                          : recentThreads.find(t => String(t.id) === selectedThreadId)?.title || 'Select Thread'
                        }
                      </span>
                      <ChevronDown size={12} className={cn("ml-auto shrink-0 text-[var(--muted-foreground)] transition-transform", openThreadDropdown && "rotate-180")} />
                    </button>
                    {openThreadDropdown && (
                      <div className="absolute top-full right-0 sm:left-0 mt-2 w-72 max-h-64 overflow-y-auto bg-[var(--card)] border border-[var(--border)] rounded-2xl shadow-2xl z-50 py-2 animate-in fade-in zoom-in-95 duration-150">
                        <button
                          onClick={() => { setSelectedThreadId('new'); setOpenThreadDropdown(false); }}
                          className={cn(
                            "w-full text-left px-3 py-2.5 text-xs flex items-center gap-3 transition-colors",
                            selectedThreadId === 'new'
                              ? "bg-[var(--primary)]/10 text-[var(--primary)] font-semibold"
                              : "text-[var(--foreground)] hover:bg-[var(--secondary)]"
                          )}
                        >
                          <Plus size={14} className={selectedThreadId === 'new' ? "text-[var(--primary)]" : "text-[var(--muted-foreground)]"} />
                          <span className="flex-1">New Thread</span>
                          {selectedThreadId === 'new' && <Check size={14} className="text-[var(--primary)] shrink-0" />}
                        </button>
                        {recentThreads.length > 0 && <div className="h-px bg-[var(--border)] mx-2 my-1" />}
                        {recentThreads.map(t => (
                          <button
                            key={t.id}
                            onClick={() => { setSelectedThreadId(String(t.id)); setOpenThreadDropdown(false); }}
                            className={cn(
                              "w-full text-left px-3 py-2.5 text-xs flex items-center gap-3 transition-colors",
                              String(t.id) === selectedThreadId
                                ? "bg-[var(--primary)]/10 text-[var(--primary)] font-semibold"
                                : "text-[var(--foreground)] hover:bg-[var(--secondary)]"
                            )}
                          >
                            {t.cover_image ? (
                              <img src={t.cover_image} alt="" className="w-5 h-7 rounded object-cover shrink-0" />
                            ) : (
                              <BookOpen size={14} className={String(t.id) === selectedThreadId ? "text-[var(--primary)]" : "text-[var(--muted-foreground)]"} />
                            )}
                            <div className="flex-1 min-w-0">
                              <span className="truncate block">{t.title}</span>
                              {(t.translations_count || 0) > 0 && (
                                <span className="text-[10px] text-[var(--muted-foreground)]">{t.translations_count} translations</span>
                              )}
                            </div>
                            {String(t.id) === selectedThreadId && <Check size={14} className="text-[var(--primary)] shrink-0" />}
                          </button>
                        ))}
                      </div>
                    )}
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
            <Button variant="link" className="text-[var(--primary)] font-bold" onClick={() => onNavigateToLibrary?.()}>See full library</Button>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {recentThreads.slice(0, 3).map((thread) => (
              <div key={thread.id} onClick={() => onOpenThread?.(thread.id)}>
                <BookCard 
                  title={thread.title} 
                  author={thread.author || 'Ancient Author'} 
                  status={(thread.translations_count || 0) > 0 ? 'In Progress' : 'Unread'} 
                  translations_count={thread.translations_count}
                  imageUrl={thread.cover_image}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
