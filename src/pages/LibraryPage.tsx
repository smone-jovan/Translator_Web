import { BookOpen, Globe, FileText, Trash2 } from 'lucide-react';
import { useState, useEffect } from 'react';

interface ThreadItem {
  id: number;
  title: string;
  source_type: 'url' | 'epub';
  chapter_count: number;
  created_at: string;
}

interface LibraryPageProps {
  onOpenThread?: (threadId: number) => void;
}

export default function LibraryPage({ onOpenThread }: LibraryPageProps) {
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      await fetchThreads();
    })();
  }, []);

  const fetchThreads = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/threads');
      const data = await res.json();
      setThreads(data);
    } catch (e) {
      console.error('Failed to fetch threads', e);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this thread?')) return;
    try {
      await fetch(`http://localhost:8000/api/threads/${id}`, { method: 'DELETE' });
      fetchThreads();
    } catch (e) {
      console.error('Failed to delete thread', e);
    }
  };

  return (
    <div className="space-y-4">
      <div className="glass rounded-xl p-5">
        <div className="flex justify-between items-center mb-5">
          <div>
            <h2 className="text-lg font-medium">Library</h2>
            <p className="text-xs text-[var(--muted-foreground)] mt-1">
              All imported novels & translations. Click to read.
            </p>
          </div>
          <div className="text-xs text-[var(--muted-foreground)]">
            {threads.length} items
          </div>
        </div>

        <div className="space-y-2">
          {loading && <div className="text-sm text-[var(--muted-foreground)]">Loading...</div>}
          
          {!loading && threads.map(thread => (
            <div
              key={thread.id}
              onClick={() => onOpenThread?.(thread.id)}
              className="bg-[var(--secondary)] border border-[var(--border)] rounded-lg px-4 py-3 flex items-center gap-4 group hover:bg-[var(--accent)] transition-colors cursor-pointer"
            >
              {/* Icon */}
              <div className="w-10 h-10 rounded-lg bg-[var(--background)] flex items-center justify-center shrink-0">
                {thread.source_type === 'epub' ? (
                  <BookOpen size={18} className="text-[var(--muted-foreground)]" />
                ) : (
                  <Globe size={18} className="text-[var(--muted-foreground)]" />
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm text-[var(--foreground)] truncate">
                  {thread.title}
                </div>
                <div className="flex items-center gap-3 text-xs text-[var(--muted-foreground)] mt-0.5">
                  <span className="flex items-center gap-1">
                    <FileText size={12} />
                    {thread.chapter_count} ch
                  </span>
                  <span>{new Date(thread.created_at).toLocaleDateString()}</span>
                  <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-[var(--background)] border border-[var(--border)]">
                    {thread.source_type}
                  </span>
                </div>
              </div>

              {/* Delete */}
              <button 
                onClick={(e) => { e.stopPropagation(); handleDelete(thread.id); }}
                className="text-[var(--muted-foreground)] hover:text-[var(--destructive)] opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}

          {!loading && threads.length === 0 && (
            <div className="text-center text-sm text-[var(--muted-foreground)] py-12">
              No books yet. Go to Translate tab to import.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

