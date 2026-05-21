import React from 'react';
import { Loader2, Sparkles, SlidersHorizontal } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ThreadDetail } from './types';

interface ChapterGridProps {
  thread: ThreadDetail;
  chapterSearch: string;
  chapterFilter: 'all' | 'translated';
  sortOrder: 'asc' | 'desc';
  lastReadId: number | null;
  isTranslatingTitles: boolean;
  goToChapter: (idx: number) => void;
  handleSingleTitlePolish: (chapterId: number, e: React.MouseEvent) => Promise<void>;
}

export default function ChapterGrid({
  thread,
  chapterSearch,
  chapterFilter,
  sortOrder,
  lastReadId,
  isTranslatingTitles,
  goToChapter,
  handleSingleTitlePolish,
}: ChapterGridProps) {
  const isPolished = (title: string | null | undefined) => {
    if (!title) return false;
    return !/[\u4e00-\u9fff]/.test(title);
  };

  const filteredChapters = thread.chapters
    .map((ch, originalIndex) => ({ ...ch, originalIndex }))
    .filter(ch => {
      const query = chapterSearch.toLowerCase();
      const titleOriginal = (ch.title_original || '').toLowerCase();
      const titleTranslated = (ch.title_translated || '').toLowerCase();
      const matchesSearch = titleOriginal.includes(query) || 
                            titleTranslated.includes(query) || 
                            `chapter ${ch.order + 1}`.includes(query) ||
                            `ch. ${ch.order + 1}`.includes(query) ||
                            String(ch.order + 1).includes(query);
      
      if (chapterFilter === 'translated') {
        return matchesSearch && ch.has_translation;
      }
      return matchesSearch;
    });

  const sortedChapters = [...filteredChapters].sort((a, b) => {
    return sortOrder === 'asc' ? a.order - b.order : b.order - a.order;
  });

  if (sortedChapters.length === 0) {
    return (
      <div className="max-w-5xl mx-auto px-6 mt-8">
        <div className="glass p-12 rounded-3xl border border-[var(--border)] text-center flex flex-col items-center justify-center bg-[var(--card)]/10 backdrop-blur-sm">
          <SlidersHorizontal className="w-10 h-10 text-[var(--muted-foreground)]/30 mb-3" />
          <p className="text-sm font-bold text-[var(--muted-foreground)]">No chapters matching your search or filters.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 mt-8">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
        {sortedChapters.map((ch) => (
          <div 
            key={ch.id}
            onClick={() => goToChapter(ch.originalIndex)}
            className={cn(
              "group relative p-5 rounded-2xl border transition-all duration-300 cursor-pointer text-left flex flex-col justify-between overflow-hidden",
              lastReadId === ch.id 
                ? "bg-[var(--primary)]/5 border-[var(--primary)] shadow-[0_0_20px_rgba(0,f2,fe,0.05)]" 
                : "bg-[var(--card)]/40 border-[var(--border)] hover:border-[var(--primary)]/30 hover:bg-[var(--card)]/60"
            )}
          >
            {/* Top indicators */}
            <div className="flex items-start justify-between gap-2 mb-3">
              <span className={cn(
                "text-sm font-extrabold transition-all line-clamp-2",
                isPolished(ch.title_translated) ? "text-[var(--foreground)] group-hover:text-[var(--primary)]" : "text-[var(--muted-foreground)] italic opacity-85 group-hover:text-[var(--foreground)]"
              )}>
                {ch.title_translated || ch.title_original || `Chapter ${ch.order + 1}`}
              </span>
              {/* Translation indicator */}
              {ch.has_translation ? (
                <span className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)] flex-shrink-0 mt-1" title="Translated" />
              ) : (
                <span className="w-2 h-2 rounded-full bg-[var(--border)] flex-shrink-0 mt-1" title="Not Translated" />
              )}
            </div>

            {/* Bottom info */}
            <div className="flex items-center justify-between gap-2 mt-4 pt-3 border-t border-[var(--border)]/20">
              <div className="flex items-center gap-1 text-[10px] text-[var(--muted-foreground)]">
                <span className="font-mono">{ch.word_count?.toLocaleString() || 0} words</span>
              </div>
              
              {/* Actions / Status badges */}
              <div className="flex items-center gap-1.5">
                {ch.translation_status === 'processing' && (
                  <div className="flex items-center gap-1 animate-pulse">
                    <Loader2 className="w-3 h-3 animate-spin text-[var(--accent)]" />
                    <span className="text-[9px] font-bold text-[var(--accent)] uppercase">Translating</span>
                  </div>
                )}
                
                {isPolished(ch.title_translated) ? (
                  <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[9px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <Sparkles className="w-2.5 h-2.5 text-emerald-400" />
                    Polished
                  </span>
                ) : (
                  <button
                    onClick={(e) => handleSingleTitlePolish(ch.id, e)}
                    disabled={isTranslatingTitles}
                    className="text-[9px] font-bold text-[var(--muted-foreground)] hover:text-[var(--primary)] px-2 py-0.5 rounded-md border border-[var(--border)] bg-transparent hover:bg-[var(--secondary)] transition-all flex items-center gap-1 cursor-pointer"
                  >
                    <Sparkles className="w-2.5 h-2.5 text-amber-500" />
                    Polish
                  </button>
                )}
              </div>
            </div>

            {/* Left bookmark vertical line */}
            {lastReadId === ch.id && (
              <div className="absolute left-0 top-0 bottom-0 w-1 bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)] animate-pulse" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
