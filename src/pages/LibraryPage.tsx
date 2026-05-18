/* eslint-disable @typescript-eslint/ban-ts-comment */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { BookOpen, FileText, Trash2, MoreVertical, Play, Clock, Search, Filter, Sparkles, Globe } from 'lucide-react';
import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { getApiUrl } from '@/lib/api';
import BulkTranslateModal from '@/components/BulkTranslateModal';
import AutoAwesome from '@mui/icons-material/AutoAwesome';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import IconButton from '@mui/material/IconButton';
import EditCoverModal, { getTitleGradient } from '@/components/EditCoverModal';
import ScrapeNUModal from '@/components/ScrapeNUModal';


interface ThreadItem {
  id: number;
  title: string;
  author?: string;
  source_type: 'url' | 'epub';
  chapter_count: number;
  created_at: string;
  last_read?: string;
  progress?: number;
  cover_image?: string | null;
  original_title?: string | null;
  genres?: string | null;
  tags?: string | null;
  status?: string | null;
  status_coo?: string | null;
  synopsis?: string | null;
}

interface LibraryPageProps {
  onOpenThread?: (threadId: number) => void;
}

const LibraryBookCard = ({ 
  thread, 
  onOpen, 
  onDelete, 
  onBatchTranslate,
  onEditCover,
  onScrapeNU
}: { 
  thread: ThreadItem, 
  onOpen: () => void, 
  onDelete: () => void,
  onBatchTranslate: () => void,
  onEditCover: () => void,
  onScrapeNU: () => void
}) => {
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };
  const handleClose = () => {
    setAnchorEl(null);
  };

  return (
    <Card className="overflow-hidden group hover:shadow-xl hover:border-[var(--primary)]/30 transition-all duration-300 bg-[var(--card)] border-[var(--border)]">
      <CardContent className="p-0 flex flex-col h-full">
        {/* Poster Area */}
        <div className="relative aspect-[3/4] bg-[var(--secondary)] overflow-hidden">
          {thread.cover_image ? (
            <img 
              src={thread.cover_image} 
              alt={thread.title} 
              className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105" 
            />
          ) : (
            <div 
              className="absolute inset-0 p-4 flex flex-col justify-between items-center text-center select-none transition-transform duration-500 group-hover:scale-105"
              style={{ background: getTitleGradient(thread.title) }}
            >
              {/* Visual Accent */}
              <div className="w-8 h-1 bg-white/20 rounded-full mt-2" />
              
              {/* Stylized initials in middle */}
              <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-md font-black text-white tracking-widest">
                {(() => {
                  const cleanText = thread.title.replace(/[^\w\s\u4e00-\u9fa5]/g, '').trim();
                  const parts = cleanText.split(/\s+/);
                  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
                  return thread.title.substring(0, 2).toUpperCase();
                })()}
              </div>
              
              {/* Mini Title below */}
              <div className="w-full mb-1">
                <p className="text-[9px] font-black text-white/90 uppercase tracking-widest line-clamp-2 px-1 leading-tight">
                  {thread.title}
                </p>
              </div>
            </div>
          )}
          
          {/* Badge */}
          <div className="absolute top-3 left-3 px-2 py-1 rounded-md bg-black/40 backdrop-blur-md text-[10px] font-bold text-white uppercase tracking-wider">
            {thread.source_type}
          </div>

          {/* Hover Actions */}
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <Button 
              size="icon" 
              className="w-12 h-12 rounded-full bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 shadow-lg transform scale-90 group-hover:scale-100 transition-all duration-300 flex items-center justify-center" 
              onClick={onOpen}
            >
              <Play size={24} className="fill-current ml-0.5" />
            </Button>
          </div>
        </div>

        {/* Info Area */}
        <div className="p-5 flex-1 flex flex-col">
          <div className="flex justify-between items-start mb-1">
            <div className="flex flex-col gap-0.5 max-w-[85%]">
              <h3 className="font-bold text-sm text-[var(--foreground)] line-clamp-1 leading-tight group-hover:text-[var(--primary)] transition-colors">
                {thread.title}
              </h3>
              {thread.original_title && (
                <p className="text-[10px] text-[var(--muted-foreground)]/80 italic font-medium line-clamp-1">
                  {thread.original_title}
                </p>
              )}
            </div>
            <IconButton 
              size="small" 
              onClick={handleClick}
              sx={{ color: 'var(--muted-foreground)', '&:hover': { color: 'var(--foreground)' } }}
            >
              <MoreVertical size={16} />
            </IconButton>
            <Menu
              anchorEl={anchorEl}
              open={open}
              onClose={handleClose}
              // @ts-ignore
              PaperProps={{
                sx: {
                  background: 'var(--card)',
                  border: '1px solid var(--border)',
                  color: 'var(--foreground)',
                  borderRadius: '12px',
                  mt: 0.5,
                  '& .MuiMenuItem-root': {
                    fontSize: '0.75rem',
                    gap: 1.5,
                    px: 2,
                    py: 1,
                    '&:hover': { background: 'rgba(255,255,255,0.05)' }
                  }
                }
              }}
            >
              <MenuItem onClick={() => { onBatchTranslate(); handleClose(); }}>
                <AutoAwesome sx={{ fontSize: 16, color: 'var(--primary)' }} />
                Translate All (Batch)
              </MenuItem>
              <MenuItem onClick={() => { onEditCover(); handleClose(); }}>
                <Sparkles size={16} className="text-[var(--primary)]" />
                Customize Cover
              </MenuItem>
              <MenuItem onClick={() => { onScrapeNU(); handleClose(); }}>
                <Globe size={16} className="text-[var(--primary)]" />
                Scrape from NU
              </MenuItem>
              <MenuItem onClick={() => { onDelete(); handleClose(); }} sx={{ color: '#ef4444' }}>
                <Trash2 size={16} />
                Delete Book
              </MenuItem>
            </Menu>
          </div>
          <div className="flex justify-between items-center mb-2">
            <p className="text-[10px] text-[var(--muted-foreground)] line-clamp-1">{thread.author || 'Unknown Author'}</p>
            {thread.status && (
              <span className="text-[8px] font-black px-1.5 py-0.5 rounded-full bg-green-500/10 text-green-400 border border-green-500/20 shadow-sm uppercase tracking-wide">
                {thread.status}
              </span>
            )}
          </div>
          {thread.genres && (
            <div className="flex flex-wrap gap-1 mb-3">
              {thread.genres.split(',').slice(0, 2).map((genre, i) => (
                <span key={i} className="text-[8px] font-extrabold px-1.5 py-0.5 rounded bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20 uppercase tracking-wide">
                  {genre.trim()}
                </span>
              ))}
            </div>
          )}
          
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
  const [selectedBatchThread, setSelectedBatchThread] = useState<any>(null);
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);
  const [selectedCoverThread, setSelectedCoverThread] = useState<ThreadItem | null>(null);
  const [isCoverModalOpen, setIsCoverModalOpen] = useState(false);
  const [selectedScrapeThread, setSelectedScrapeThread] = useState<ThreadItem | null>(null);
  const [isScrapeModalOpen, setIsScrapeModalOpen] = useState(false);

  const handleSaveCover = async (coverValue: string | null) => {
    if (!selectedCoverThread) return;
    try {
      const res = await fetch(getApiUrl(`/api/threads/${selectedCoverThread.id}/cover`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cover_image: coverValue })
      });
      if (!res.ok) throw new Error('Failed to update cover');
      
      fetchThreads();
    } catch (e) {
      console.error('Error saving cover:', e);
      throw e;
    }
  };

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

  const handleOpenBatchModal = async (thread: ThreadItem) => {
    try {
      const res = await fetch(getApiUrl(`/api/threads/${thread.id}`));
      const data = await res.json();
      setSelectedBatchThread(data);
      setIsBatchModalOpen(true);
    } catch {
      console.error('Failed to fetch thread details for batch');
    }
  };

  const handleStartBatch = async (chapterIds: number[], aiExtract: boolean, _loadMode: 'soft' | 'hard', targetLang: string, overwrite: boolean) => {
    if (!selectedBatchThread) return;
    
    try {
      const res = await fetch(getApiUrl(`/api/threads/${selectedBatchThread.id}/batch-translate`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            chapter_ids: chapterIds, 
            ai_extract: aiExtract,
            overwrite: overwrite,
            target_lang: targetLang
        })
      });
      
      if (!res.ok) throw new Error('Failed to start batch');
      
      fetchThreads();
    } catch (e) {
      console.error(e);
    }
  };

  const filteredThreads = threads.filter(t => 
    t.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Find all books with reading progress
  const activeReads = threads
    .filter(t => t.progress !== undefined && t.progress > 0 && t.progress < 100)
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  return (
    <div className="w-full max-w-6xl mx-auto space-y-12 py-8 px-4 sm:px-6 animate-in fade-in duration-700">
      {/* Continue Reading Carousel */}
      {activeReads.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between px-2">
            <h2 className="text-xs font-black uppercase tracking-[0.2em] text-[var(--muted-foreground)] flex items-center gap-2">
              <Clock size={14} /> Continue Reading
            </h2>
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--primary)]" />
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--primary)]/30" />
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--primary)]/10" />
            </div>
          </div>
          
          <div className="flex gap-6 overflow-x-auto pb-6 pt-2 px-2 no-scrollbar snap-x snap-mandatory">
            {activeReads.map(book => (
              <section 
                key={book.id}
                className="relative flex-shrink-0 w-[90%] md:w-[600px] snap-center overflow-hidden rounded-[2.5rem] bg-gradient-to-br from-[var(--primary)]/10 to-[var(--accent)]/5 border border-[var(--border)] shadow-xl hover:shadow-2xl hover:border-[var(--primary)]/30 transition-all duration-500 group"
              >
                <div className="absolute top-0 right-0 p-6 opacity-5 pointer-events-none group-hover:scale-110 transition-transform duration-700">
                  <BookOpen size={140} />
                </div>
                
                <div className="relative p-6 md:p-10 flex flex-row items-center gap-6 md:gap-10">
                  {/* Compact Cover */}
                  <div className="w-24 md:w-32 aspect-[3/4] bg-[var(--card)] rounded-2xl shadow-xl flex-shrink-0 overflow-hidden border border-[var(--primary)]/10 rotate-[-2deg] group-hover:rotate-0 transition-transform duration-500 relative">
                    {book.cover_image ? (
                      <img src={book.cover_image} alt={book.title} className="w-full h-full object-cover" />
                    ) : (
                      <div 
                        className="w-full h-full p-2 flex flex-col justify-between items-center text-center select-none"
                        style={{ background: getTitleGradient(book.title) }}
                      >
                        {/* Visual Accent */}
                        <div className="w-4 h-0.5 bg-white/20 rounded-full mt-1" />
                        
                        {/* Stylized initials in middle */}
                        <div className="w-8 h-8 rounded-full bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-[10px] font-black text-white tracking-wider">
                          {(() => {
                            const cleanText = book.title.replace(/[^\w\s\u4e00-\u9fa5]/g, '').trim();
                            const parts = cleanText.split(/\s+/);
                            if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
                            return book.title.substring(0, 2).toUpperCase();
                          })()}
                        </div>
                        
                        {/* Mini Title below */}
                        <div className="w-full mb-1">
                          <p className="text-[7px] font-black text-white/80 uppercase tracking-wider line-clamp-1 px-0.5 leading-tight">
                            {book.title}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex-1 space-y-4 min-w-0">
                    <div className="space-y-1">
                      <h2 className="text-xl md:text-2xl font-black tracking-tight leading-tight truncate">{book.title}</h2>
                      <p className="text-[10px] md:text-xs text-[var(--muted-foreground)] font-medium truncate">
                        Last: <span className="text-[var(--foreground)]">{book.last_read || 'Chapter 1'}</span>
                      </p>
                    </div>
                    
                    <div className="space-y-2 max-w-xs">
                      <div className="flex justify-between items-end">
                        <span className="text-[9px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">{book.progress}% Done</span>
                      </div>
                      <div className="h-1.5 w-full bg-[var(--secondary)] rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-[var(--primary)] to-[var(--accent)] transition-all duration-1000 ease-out" 
                          style={{ width: `${book.progress}%` }}
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-3 pt-1">
                      <Button size="sm" className="rounded-xl px-5 font-bold shadow-lg shadow-[var(--primary)]/20 text-[10px] h-9" onClick={() => onOpenThread?.(book.id)}>
                        <Play size={14} className="fill-current mr-2" /> RESUME
                      </Button>
                      <Button variant="ghost" size="sm" className="rounded-xl text-[var(--muted-foreground)] hover:text-[var(--foreground)] text-[10px] h-9" onClick={() => onOpenThread?.(book.id)}>
                        DETAILS
                      </Button>
                    </div>
                  </div>
                </div>
              </section>
            ))}
          </div>
        </div>
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
            onBatchTranslate={() => handleOpenBatchModal(thread)}
            onEditCover={() => {
              setSelectedCoverThread(thread);
              setIsCoverModalOpen(true);
            }}
            onScrapeNU={() => {
              setSelectedScrapeThread(thread);
              setIsScrapeModalOpen(true);
            }}
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
      {selectedBatchThread && (
        <BulkTranslateModal 
          isOpen={isBatchModalOpen}
          onClose={() => setIsBatchModalOpen(false)}
          threadId={selectedBatchThread.id}
          threadTitle={selectedBatchThread.title}
          chapters={selectedBatchThread.chapters || []}
          onStartBatch={handleStartBatch}
        />
      )}

      {selectedCoverThread && (
        <EditCoverModal
          isOpen={isCoverModalOpen}
          onClose={() => {
            setIsCoverModalOpen(false);
            setSelectedCoverThread(null);
          }}
          threadId={selectedCoverThread.id}
          threadTitle={selectedCoverThread.title}
          currentCover={selectedCoverThread.cover_image || null}
          onSave={handleSaveCover}
        />
      )}

      {selectedScrapeThread && (
        <ScrapeNUModal
          isOpen={isScrapeModalOpen}
          onClose={() => {
            setIsScrapeModalOpen(false);
            setSelectedScrapeThread(null);
          }}
          threadId={selectedScrapeThread.id}
          threadTitle={selectedScrapeThread.title}
          threadOriginalTitle={selectedScrapeThread.original_title || null}
          onScrapeSuccess={fetchThreads}
        />
      )}
    </div>
  );
}
