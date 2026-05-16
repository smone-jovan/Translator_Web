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

  return (
    <div className="w-full max-w-6xl mx-auto space-y-10 py-4">
      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div className="space-y-1">
          <h1 className="text-4xl font-bold text-[var(--foreground)] tracking-tight">Your Library</h1>
          <p className="text-[var(--muted-foreground)] text-lg">Manage your translated works and reading progress.</p>
        </div>
        
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]" size={18} />
            <input 
              type="text" 
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search your library..."
              className="pl-10 pr-4 py-2.5 rounded-xl bg-[var(--card)] border border-[var(--border)] text-sm focus:outline-none focus:border-[var(--primary)] transition-all min-w-[280px]"
            />
          </div>
          <Button variant="outline" size="icon" className="rounded-xl"><Filter size={18} /></Button>
        </div>
      </header>

      {/* Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-8">
        {loading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="aspect-[3/4] rounded-2xl bg-[var(--secondary)] animate-pulse" />
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
          <div className="col-span-full py-32 text-center bg-[var(--card)] border-2 border-dashed border-[var(--border)] rounded-3xl">
            <BookOpen className="mx-auto w-16 h-16 text-[var(--muted-foreground)] mb-4 opacity-20" />
            <h2 className="text-2xl font-bold text-[var(--foreground)] mb-2">Library is Empty</h2>
            <p className="text-[var(--muted-foreground)] max-w-sm mx-auto">
              Start by translating a URL or uploading an EPUB to build your collection.
            </p>
            <Button className="mt-8 rounded-xl px-8" onClick={() => window.location.hash = '#translate'}>
              Go to Translate
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
