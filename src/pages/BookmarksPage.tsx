import { useEffect, useState } from 'react';
import { getApiUrl } from '@/lib/api';
import { Star, BookOpen, LibraryBig } from 'lucide-react';

interface BookmarkedChapter {
  id: number;
  thread_id: number;
  thread_title: string;
  order: number;
  title_original: string | null;
  title_translated: string | null;
}

interface BookmarksPageProps {
  onOpenChapter: (threadId: number, chapterId: number) => void;
  onOpenLibrary: () => void;
}

export default function BookmarksPage({ onOpenChapter, onOpenLibrary }: BookmarksPageProps) {
  const [bookmarks, setBookmarks] = useState<BookmarkedChapter[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchBookmarks = async () => {
    try {
      setLoading(true);
      const res = await fetch(getApiUrl('/api/bookmarks'));
      const data = await res.json();
      if (Array.isArray(data)) setBookmarks(data);
    } catch (err) {
      console.error('Failed to fetch bookmarks:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    const load = async () => {
      await Promise.resolve();
      if (!active) return;
      fetchBookmarks();
    };
    load();
    return () => {
      active = false;
    };
  }, []);

  const removeBookmark = async (threadId: number, chapterId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/chapters/${chapterId}/bookmark`), {
        method: 'PUT',
      });
      if (res.ok) {
        setBookmarks(prev => prev.filter(b => b.id !== chapterId));
      }
    } catch (err) {
      console.error('Failed to remove bookmark:', err);
    }
  };

  // Group by thread
  const groupedBookmarks = bookmarks.reduce((acc, curr) => {
    if (!acc[curr.thread_id]) {
      acc[curr.thread_id] = { title: curr.thread_title, chapters: [] };
    }
    acc[curr.thread_id].chapters.push(curr);
    return acc;
  }, {} as Record<number, { title: string, chapters: BookmarkedChapter[] }>);

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-8 space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-2xl bg-[var(--accent)] flex items-center justify-center text-[var(--primary)] shadow-inner">
          <Star size={24} className="fill-[var(--primary)]" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Favorite Chapters</h1>
          <p className="text-[var(--muted-foreground)]">Your bookmarked and starred chapters</p>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-[var(--muted-foreground)]">Loading bookmarks...</div>
      ) : bookmarks.length === 0 ? (
        <div className="text-center py-20 bg-[var(--card)] rounded-3xl border border-[var(--border)] shadow-sm">
          <Star size={48} className="mx-auto text-[var(--muted)] mb-4" />
          <h2 className="text-xl font-medium mb-2">No bookmarks yet</h2>
          <p className="text-[var(--muted-foreground)] mb-6">Star your favorite chapters while reading to save them here.</p>
          <button 
            onClick={onOpenLibrary}
            className="px-6 py-2.5 rounded-full bg-[var(--primary)] text-[var(--primary-foreground)] font-medium hover:opacity-90 transition-opacity inline-flex items-center gap-2"
          >
            <LibraryBig size={18} />
            Go to Library
          </button>
        </div>
      ) : (
        <div className="space-y-8">
          {Object.entries(groupedBookmarks).map(([threadId, group]) => (
            <div key={threadId} className="bg-[var(--card)] rounded-3xl border border-[var(--border)] shadow-sm overflow-hidden">
              <div className="bg-[var(--muted)]/30 px-6 py-4 border-b border-[var(--border)]">
                <h2 className="font-semibold text-lg line-clamp-1" title={group.title}>{group.title}</h2>
              </div>
              <div className="divide-y divide-[var(--border)]">
                {group.chapters.map(ch => (
                  <div 
                    key={ch.id} 
                    className="flex items-center justify-between p-4 px-6 hover:bg-[var(--accent)]/50 transition-colors cursor-pointer group"
                    onClick={() => onOpenChapter(ch.thread_id, ch.id)}
                  >
                    <div className="flex-1 min-w-0 pr-4">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-[var(--primary)]/10 text-[var(--primary)] shrink-0">
                          Ch {ch.order}
                        </span>
                        <h3 className="font-medium truncate group-hover:text-[var(--primary)] transition-colors">
                          {ch.title_translated || ch.title_original || `Chapter ${ch.order}`}
                        </h3>
                      </div>
                      <p className="text-xs text-[var(--muted-foreground)] truncate">
                        {ch.title_original}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => removeBookmark(ch.thread_id, ch.id, e)}
                        className="p-2 rounded-xl text-yellow-500 hover:bg-yellow-500/10 transition-colors"
                        title="Remove bookmark"
                      >
                        <Star size={20} className="fill-current" />
                      </button>
                      <button
                        className="p-2 rounded-xl text-[var(--muted-foreground)] hover:bg-[var(--primary)]/10 hover:text-[var(--primary)] transition-colors opacity-0 group-hover:opacity-100"
                        title="Read Chapter"
                      >
                        <BookOpen size={20} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
