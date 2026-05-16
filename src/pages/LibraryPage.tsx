import { BookOpen, Globe, FileText, Trash2, MoreVertical, Play, Clock, Search, Filter } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getApiUrl } from '@/lib/api';

interface ThreadItem {
  id: number;
  title: string;
  author?: string;
  source_type: 'url' | 'epub';
  chapter_count: number;
  created_at: string;
  last_read?: string;
  progress?: number;
}

interface LibraryPageProps {
  onOpenThread?: (threadId: number) => void;
}

const LibraryBookCard = ({ thread, onOpen, onDelete }: { thread: ThreadItem, onOpen: () => void, onDelete: () => void }) => {
  return (
    <Card className="overflow-hidden group hover:shadow-xl hover:border-[var(--primary)]/30 transition-all duration-300 bg-[var(--card)] border-[var(--border)]">
      <CardContent className="p-0 flex flex-col h-full">
        {/* Poster Area */}
        <div className="relative aspect-[3/4] bg-[var(--secondary)] overflow-hidden">
          <div className="absolute inset-0 flex items-center justify-center">
            {thread.source_type === 'epub' ? (
              <BookOpen size={48} className="text-[var(--muted-foreground)] opacity-20" />
            ) : (
              <Globe size={48} className="text-[var(--muted-foreground)] opacity-20" />
            )}
          </div>
          
          {/* Badge */}
          <div className="absolute top-3 left-3 px-2 py-1 rounded-md bg-black/40 backdrop-blur-md text-[10px] font-bold text-white uppercase tracking-wider">
            {thread.source_type}
          </div>

          {/* Hover Actions */}
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
            <Button size="icon" className="rounded-full bg-white text-black hover:bg-white/90" onClick={onOpen}>
              <Play size={20} className="fill-current" />
            </Button>
            <Button variant="destructive" size="icon" className="rounded-full" onClick={onDelete}>
              <Trash2 size={20} />
            </Button>
          </div>
        </div>

        {/* Info Area */}
        <div className="p-5 flex-1 flex flex-col">
          <div className="flex justify-between items-start mb-1">
            <h3 className="font-bold text-sm text-[var(--foreground)] line-clamp-1 leading-tight group-hover:text-[var(--primary)] transition-colors">
              {thread.title}
            </h3>
            <button className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
              <MoreVertical size={16} />
            </button>
          </div>
          <p className="text-[10px] text-[var(--muted-foreground)] mb-4">{thread.author || 'Unknown Author'}</p>
          
          <div className="mt-auto space-y-3">
            {/* Progress */}
            <div className="space-y-1">
              <div className="flex justify-between text-[9px] font-bold text-[var(--muted-foreground)] uppercase tracking-tighter">
                <span>Progress</span>
                <span>{thread.progress || 0}%</span>
              </div>
              <div className="h-1 w-full bg-[var(--secondary)] rounded-full overflow-hidden">
                <div 
                  className="h-full bg-[var(--primary)] transition-all duration-500" 
                  style={{ width: `${thread.progress || 0}%` }}
                />
              </div>
            </div>

            {/* Stats */}
            <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]">
              <div className="flex items-center gap-1.5 text-[10px] text-[var(--muted-foreground)]">
                <FileText size={12} />
                <span>{thread.chapter_count} Chapters</span>
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-[var(--muted-foreground)]">
                <Clock size={12} />
                <span>{new Date(thread.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default function LibraryPage({ onOpenThread }: LibraryPageProps) {
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  const fetchThreads = useCallback(async () => {
    try {
      const res = await fetch(getApiUrl('/api/threads'));
      const data = await res.json();
      setThreads(data);
    } catch {
      console.error('Failed to fetch threads');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchThreads();
  }, [fetchThreads]);

  const handleDelete = async (id: number) => {
    if (!confirm('Are you sure you want to delete this book? All translations will be lost.')) return;
    try {
      await fetch(getApiUrl(`/api/threads/${id}`), { method: 'DELETE' });
      fetchThreads();
    } catch {
      console.error('Failed to delete thread');
    }
  };

  const filteredThreads = threads.filter(t => 
    t.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Find most recently read book for the banner
  const lastReadThread = threads
    .filter(t => t.progress > 0)
    .sort((a, b) => (a.progress === 100 ? 1 : -1)) // Optional: prioritize non-finished
    .slice(0, 1)[0];

  return (
    <div className="w-full max-w-6xl mx-auto space-y-12 py-8 px-4 sm:px-6 animate-in fade-in duration-700">
      {/* Continue Reading Banner */}
      {lastReadThread && (
        <section className="relative overflow-hidden rounded-[2.5rem] bg-gradient-to-br from-[var(--primary)]/20 to-[var(--accent)]/5 border border-[var(--primary)]/10 shadow-2xl">
          <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none">
            <BookOpen size={180} />
          </div>
          <div className="relative p-8 md:p-12 flex flex-col md:flex-row items-center gap-10">
            <div className="w-40 aspect-[3/4] bg-[var(--card)] rounded-2xl shadow-2xl flex-shrink-0 overflow-hidden border border-[var(--primary)]/20 rotate-[-2deg] group-hover:rotate-0 transition-transform duration-500">
               <div className="w-full h-full flex items-center justify-center opacity-40">
                  {lastReadThread.source_type === 'epub' ? <BookOpen size={48} /> : <Globe size={48} />}
               </div>
            </div>
            <div className="flex-1 space-y-6 text-center md:text-left">
              <div className="space-y-2">
                <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] text-[10px] font-bold uppercase tracking-widest">
                  <Clock size={12} /> Continue Reading
                </span>
                <h2 className="text-3xl md:text-4xl font-black tracking-tight leading-tight">{lastReadThread.title}</h2>
                <p className="text-[var(--muted-foreground)] font-medium">Last read: <span className="text-[var(--foreground)]">{lastReadThread.last_read || 'Chapter 1'}</span></p>
              </div>
              
              <div className="space-y-3 max-w-md mx-auto md:mx-0">
                <div className="flex justify-between items-end">
                   <span className="text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Your Progress</span>
                   <span className="text-sm font-black text-[var(--primary)]">{lastReadThread.progress}%</span>
                </div>
                <div className="h-2 w-full bg-[var(--secondary)] rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-gradient-to-r from-[var(--primary)] to-[var(--accent)] shadow-[0_0_15px_rgba(var(--primary-rgb),0.5)] transition-all duration-1000 ease-out" 
                    style={{ width: `${lastReadThread.progress}%` }}
                  />
                </div>
              </div>

              <div className="flex items-center gap-4 justify-center md:justify-start pt-2">
                <Button size="lg" className="rounded-2xl px-8 font-bold shadow-xl shadow-[var(--primary)]/25 gap-3" onClick={() => onOpenThread?.(lastReadThread.id)}>
                  <Play size={18} className="fill-current" /> Resume Reading
                </Button>
                <Button variant="ghost" className="rounded-2xl text-[var(--muted-foreground)] hover:text-[var(--foreground)]" onClick={() => onOpenThread?.(lastReadThread.id)}>
                  Details
                </Button>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-8 pt-4">
        <div className="space-y-2">
          <h1 className="text-4xl md:text-5xl font-black text-[var(--foreground)] tracking-tighter">Your Library</h1>
          <p className="text-[var(--muted-foreground)] font-medium text-lg">Manage your translated works and reading progress.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="relative group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] group-focus-within:text-[var(--primary)] transition-colors" size={18} />
            <input 
              type="text" 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search library..."
              className="pl-12 pr-6 py-3.5 rounded-2xl bg-[var(--card)] border border-[var(--border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/20 focus:border-[var(--primary)] transition-all min-w-[320px] shadow-sm"
            />
          </div>
          <Button variant="outline" size="icon" className="rounded-2xl h-[50px] w-[50px] border-[var(--border)] shadow-sm"><Filter size={20} /></Button>
        </div>
      </header>

      {/* Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-x-8 gap-y-12">
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="aspect-[3/4] rounded-3xl bg-[var(--secondary)]/50 animate-pulse" />
          ))
        ) : filteredThreads.map(thread => (
          <LibraryBookCard 
            key={thread.id} 
            thread={thread} 
            onOpen={() => onOpenThread?.(thread.id)}
            onDelete={() => handleDelete(thread.id)}
          />
        ))}

        {!loading && filteredThreads.length === 0 && (
          <div className="col-span-full py-40 text-center bg-[var(--card)]/50 border-2 border-dashed border-[var(--border)] rounded-[3rem] animate-in zoom-in-95 duration-500">
            <div className="inline-flex p-6 rounded-full bg-[var(--secondary)]/50 mb-6">
              <BookOpen className="w-12 h-12 text-[var(--muted-foreground)] opacity-30" />
            </div>
            <h2 className="text-3xl font-black text-[var(--foreground)] mb-3">Library is Empty</h2>
            <p className="text-[var(--muted-foreground)] font-medium max-w-sm mx-auto mb-10 leading-relaxed">
              Start by translating a URL or uploading an EPUB to build your personal collection.
            </p>
            <Button size="lg" className="rounded-2xl px-12 font-bold shadow-lg" onClick={() => window.location.hash = '#translate'}>
              Go to Translate
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
