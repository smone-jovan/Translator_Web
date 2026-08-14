import { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { ThreadDetail } from './types';

interface NovelHeaderProps {
  thread: ThreadDetail;
  onReadNow: () => void;
  onOpenBulkModal: () => void;
  onOpenFetchModal: () => void;
}

export default function NovelHeader({
  thread,
  onReadNow,
  onOpenBulkModal,
  onOpenFetchModal,
}: NovelHeaderProps) {
  const [isSynopsisCollapsed, setIsSynopsisCollapsed] = useState(true);

  return (
    <>
      {/* 1. Immersive Novel Header */}
      <div className="relative w-full overflow-hidden border-b border-[var(--border)] bg-[var(--background)]">
        {/* Immersive blurred backdrop cover */}
        {thread.cover_image && (
          <div 
            className="absolute inset-0 z-0 bg-cover bg-center pointer-events-none scale-110 filter blur-[40px] brightness-[0.3] opacity-30"
            style={{ backgroundImage: `url(${thread.cover_image})` }}
          />
        )}
        {/* Subtle gradient overlay to blend backdrop smoothly */}
        <div className="absolute inset-0 z-0 bg-gradient-to-b from-transparent to-[var(--background)] pointer-events-none" />

        {/* Inner Header Container */}
        <div className="relative z-10 max-w-5xl mx-auto px-6 py-10 md:py-16 flex flex-col md:flex-row gap-8 items-start">
          {/* Left: Premium Cover Container */}
          <div className="relative group mx-auto md:mx-0 flex-shrink-0">
            <div className="w-[180px] h-[250px] md:w-[220px] md:h-[308px] rounded-3xl overflow-hidden shadow-[0_20px_50px_rgba(0,0,0,0.5)] border border-white/10 relative transition-transform duration-500 group-hover:scale-105">
              {thread.cover_image ? (
                <img 
                  src={thread.cover_image} 
                  alt={thread.title} 
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = 'https://images.unsplash.com/photo-1543002588-bfa74002ed7e?q=80&w=300';
                  }}
                />
              ) : (
                <div className="w-full h-full bg-gradient-to-br from-indigo-500 to-purple-600 flex flex-col items-center justify-center p-4 text-center">
                  <BookOpen className="w-10 h-10 text-white/50 mb-2" />
                  <span className="text-xs text-white/80 font-bold tracking-wider uppercase">No Cover</span>
                </div>
              )}
            </div>
          </div>

          {/* Right: Immersive Text Details */}
          <div className="flex-1 text-left min-w-0 flex flex-col h-full justify-between">
            <div>
              {/* Original Title (Cleaned) badge if different */}
              {thread.original_title && (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold tracking-wider uppercase bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20 mb-3 max-w-full truncate" title={thread.original_title}>
                  {thread.original_title}
                </span>
              )}
              <h1 className="text-2xl md:text-4xl font-extrabold text-[var(--foreground)] tracking-tight leading-tight mb-2">
                {thread.title}
              </h1>
              <p className="text-sm text-[var(--muted-foreground)] font-medium mb-6">
                by <span className="text-[var(--foreground)] font-semibold">{thread.source_type || 'AI Platform'}</span>
              </p>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-3 mb-6">
                <Button 
                  variant="default"
                  size="lg"
                  onClick={onReadNow}
                  className="rounded-2xl gap-2 font-extrabold px-6 h-12 text-sm bg-gradient-to-r from-red-600 to-red-500 hover:from-red-500 hover:to-red-400 text-white shadow-xl shadow-red-600/20 active:scale-[0.98] transition-all"
                >
                  Read Now
                </Button>
                
                <Button 
                  variant="outline"
                  size="lg"
                  onClick={onOpenBulkModal}
                  className="rounded-2xl gap-2 font-bold px-5 h-12 text-sm border-[var(--border)] bg-[var(--card)]/30 backdrop-blur-sm hover:bg-[var(--secondary)] text-[var(--foreground)] transition-all"
                >
                  <Sparkles className="w-4 h-4 text-[var(--primary)]" />
                  Batch Translate
                </Button>

                {/* Show Fetch Button if thread or chapters have a web source */}
                {(thread.source_url || (thread.chapters && thread.chapters.some(c => !!c.source_url))) && (
                  <Button 
                    variant="outline"
                    size="lg"
                    onClick={onOpenFetchModal}
                    className="rounded-2xl gap-2 font-bold px-5 h-12 text-sm border-[var(--border)] bg-[var(--card)]/30 backdrop-blur-sm hover:bg-[var(--secondary)] text-[var(--foreground)] transition-all"
                  >
                    <BookOpen className="w-4 h-4 text-blue-400" />
                    Bulk Fetch
                  </Button>
                )}
              </div>

              {/* Genres Grid */}
              {thread.genres && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {thread.genres.split(',').map((g: string, i: number) => (
                    <span 
                      key={i} 
                      className="text-[10px] md:text-xs font-semibold px-3 py-1 rounded-full bg-[color-mix(in_srgb,var(--secondary)_50%,transparent)] border border-[var(--border)] text-[var(--foreground)]"
                    >
                      {g.trim()}
                    </span>
                  ))}
                </div>
              )}

              {/* Status & Stats Badges */}
              <div className="flex flex-wrap items-center gap-3">
                {/* Status Badge */}
                {thread.status && (
                  <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
                    thread.status.toLowerCase().includes('ongoing') || thread.status.toLowerCase().includes('no')
                      ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' 
                      : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  }`}>
                    {thread.status}
                  </span>
                )}
                
                {/* Status COO Badge */}
                {thread.status_coo && (
                  <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 max-w-[280px] truncate" title={thread.status_coo}>
                    {thread.status_coo}
                  </span>
                )}

                {/* Chapter Count Badge */}
                <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  {thread.chapters.length} chapters
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Synopsis Section */}
      {thread.synopsis && (
        <div className="max-w-5xl mx-auto px-6 mt-8">
          <div className="glass p-6 rounded-3xl border border-[var(--border)] shadow-lg">
            <h3 className="text-lg font-bold text-[var(--foreground)] mb-3">Synopsis</h3>
            <div className="relative">
              <p className={cn(
                "text-sm leading-relaxed text-[var(--muted-foreground)] whitespace-pre-line font-medium transition-all duration-300",
                isSynopsisCollapsed ? "line-clamp-4 overflow-hidden" : ""
              )}>
                {thread.synopsis}
              </p>
              {thread.synopsis.length > 200 && (
                <div className="mt-3 flex justify-start">
                  <button 
                    onClick={() => setIsSynopsisCollapsed(!isSynopsisCollapsed)}
                    className="text-xs font-extrabold text-[var(--primary)] hover:underline flex items-center gap-1 cursor-pointer border-none bg-transparent"
                  >
                    {isSynopsisCollapsed ? (
                      <>Show More <ChevronDown className="w-3.5 h-3.5" /></>
                    ) : (
                      <>Show Less <ChevronUp className="w-3.5 h-3.5" /></>
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
