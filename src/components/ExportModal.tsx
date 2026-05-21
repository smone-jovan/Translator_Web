import React, { useEffect, useState } from 'react';
import { 
  X, Download, Image as ImageIcon, Book, 
  Check, Loader2, FileText, Eraser
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { getApiUrl } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Chapter {
  id: number;
  order: number;
  title_original: string | null;
  title_translated: string | null;
  has_translation: boolean;
}

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  threadId: number;
  threadTitle: string;
  threadAuthor?: string;
  currentCover?: string | null;
  chapters: Chapter[];
}

export default function ExportModal({ isOpen, onClose, threadId, threadTitle, threadAuthor, currentCover, chapters }: ExportModalProps) {
  const [format, setFormat] = useState<'epub' | 'txt' | 'cleanup'>('epub');
  const [title, setTitle] = useState(threadTitle);
  const [author, setAuthor] = useState(threadAuthor || 'SMONE');
  const [cover, setCover] = useState<string | null>(null);
  const [coverSource, setCoverSource] = useState<'file' | 'url'>('file');
  const [coverUrl, setCoverUrl] = useState('');
  const [selectedIds, setSelectedIds] = useState<number[]>(
    chapters.filter(c => c.has_translation).map(c => c.id)
  );
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setTitle(threadTitle);
    setAuthor(threadAuthor || 'SMONE');
    setCover(currentCover || null);
    setCoverSource(currentCover && currentCover.startsWith('http') ? 'url' : 'file');
    setCoverUrl(currentCover && currentCover.startsWith('http') ? currentCover : '');
    setSelectedIds(chapters.filter(c => c.has_translation).map(c => c.id));
  }, [isOpen, threadTitle, threadAuthor, currentCover, chapters]);

  if (!isOpen) return null;

  const handleCoverUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setCover(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const toggleChapter = (id: number) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const handleExport = async () => {
    if (selectedIds.length === 0) {
      alert('Please select at least one chapter.');
      return;
    }

    setIsExporting(true);
    try {
      if (format === 'cleanup') {
        const res = await fetch(getApiUrl(`/api/threads/${threadId}/cleanup-preview`), {
          method: 'POST',
        });
        if (!res.ok) throw new Error('Cleanup preview failed');
        const data = await res.json();
        
        const blob = new Blob([data.cleaned_text], { type: 'text/plain' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${title.replace(/[^\\w\\s]/gi, '_')}_cleaned.txt`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);

        const apply = window.confirm(`Cleanup preview generated and downloaded!\\n\\nStats:\\n- Chapters Scanned: ${data.chapters_scanned}\\n- Chapters Deleted: ${data.chapters_deleted}\\n- Chapters Updated: ${data.chapters_updated}\\n- Lines Removed: ${data.lines_removed}\\n\\nDo you want to APPLY these changes destructively to the database?`);
        
        if (apply) {
          const applyRes = await fetch(getApiUrl(`/api/threads/${threadId}/cleanup-apply`), {
            method: 'POST',
          });
          if (!applyRes.ok) throw new Error('Apply failed');
          alert('Cleanup successfully applied to thread!');
          window.location.reload();
        }
        
        onClose();
        return;
      }

      const res = await fetch(getApiUrl(`/api/threads/${threadId}/export`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          format,
          title,
          author,
          cover_b64: coverSource === 'file' ? cover : null,
          cover_url: coverSource === 'url' ? coverUrl : null,
          chapter_ids: selectedIds
        })
      });

      if (!res.ok) throw new Error('Export failed');

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${title.replace(/[^\w\s]/gi, '_')}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      onClose();
    } catch (err) {
      console.error(err);
      alert('Failed to export or cleanup. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-0 sm:p-6 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
      <Card className="w-full h-full sm:h-auto sm:max-h-[90vh] sm:max-w-4xl overflow-hidden shadow-2xl border-0 sm:border-[var(--border)] bg-[var(--card)] flex flex-col md:flex-row rounded-none sm:rounded-xl">
        
        {/* Left: Metadata & Settings */}
        <div className="w-full md:w-1/2 p-4 sm:p-6 md:border-r border-[var(--border)] space-y-5 overflow-y-auto">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-black flex items-center gap-2">
              <Download className="w-5 h-5 text-[var(--primary)]" />
              Book Builder
            </h2>
            <Button variant="ghost" size="icon" onClick={onClose} className="rounded-full md:hidden">
              <X className="w-5 h-5" />
            </Button>
          </div>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Book Format</label>
              <div className="grid grid-cols-3 gap-2">
                <button 
                  onClick={() => setFormat('epub')}
                  className={cn(
                    "flex items-center justify-center gap-2 p-3 rounded-xl border transition-all",
                    format === 'epub' ? "bg-[var(--primary)]/10 border-[var(--primary)] text-[var(--primary)] shadow-sm" : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--secondary)]"
                  )}
                >
                  <Book className="w-4 h-4" />
                  <span className="text-xs font-bold">EPUB</span>
                </button>
                <button 
                  onClick={() => setFormat('txt')}
                  className={cn(
                    "flex items-center justify-center gap-2 p-3 rounded-xl border transition-all",
                    format === 'txt' ? "bg-[var(--primary)]/10 border-[var(--primary)] text-[var(--primary)] shadow-sm" : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--secondary)]"
                  )}
                >
                  <FileText className="w-4 h-4" />
                  <span className="text-xs font-bold">TEXT</span>
                </button>
                <button 
                  onClick={() => setFormat('cleanup')}
                  className={cn(
                    "flex items-center justify-center gap-2 p-3 rounded-xl border transition-all",
                    format === 'cleanup' ? "bg-[var(--primary)]/10 border-[var(--primary)] text-[var(--primary)] shadow-sm" : "border-[var(--border)] text-[var(--muted-foreground)] hover:bg-[var(--secondary)]"
                  )}
                >
                  <Eraser className="w-4 h-4" />
                  <span className="text-xs font-bold">CLEAN</span>
                </button>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Title</label>
              <input 
                type="text" 
                value={title} 
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-[var(--secondary)]/50 border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm focus:ring-2 ring-[var(--primary)]/20 outline-none transition-all"
                placeholder="Enter book title..."
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Author</label>
              <input 
                type="text" 
                value={author} 
                onChange={(e) => setAuthor(e.target.value)}
                className="w-full bg-[var(--secondary)]/50 border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm focus:ring-2 ring-[var(--primary)]/20 outline-none transition-all"
                placeholder="Enter author name..."
              />
            </div>

            <div className="space-y-2">
              <label className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Cover Image</label>
              
              {/* Cover Source Selector Tabs */}
              <div className="grid grid-cols-2 gap-1 p-1 bg-[var(--secondary)]/30 rounded-xl border border-[var(--border)]">
                <button
                  type="button"
                  onClick={() => setCoverSource('file')}
                  className={cn(
                    "py-1.5 rounded-lg text-[10px] font-bold transition-all",
                    coverSource === 'file' 
                      ? "bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] shadow-sm" 
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  )}
                >
                  Upload File
                </button>
                <button
                  type="button"
                  onClick={() => setCoverSource('url')}
                  className={cn(
                    "py-1.5 rounded-lg text-[10px] font-bold transition-all",
                    coverSource === 'url' 
                      ? "bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] shadow-sm" 
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  )}
                >
                  Image URL
                </button>
              </div>

              {coverSource === 'file' ? (
                <div className="relative group aspect-[3/4] max-w-[140px] sm:max-w-[150px] mx-auto rounded-2xl border-2 border-dashed border-[var(--border)] overflow-hidden hover:border-[var(--primary)]/50 transition-all">
                  {cover ? (
                    <>
                      <img src={cover} alt="Cover Preview" className="w-full h-full object-cover" />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-all">
                        <label className="cursor-pointer bg-white/20 backdrop-blur-md px-3 py-1.5 rounded-lg text-[10px] font-bold text-white">Change Cover</label>
                      </div>
                    </>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-full gap-2 text-[var(--muted-foreground)]">
                      <ImageIcon className="w-8 h-8 opacity-20" />
                      <span className="text-[10px] font-bold uppercase tracking-tighter">Upload Cover</span>
                    </div>
                  )}
                  <input type="file" accept="image/*" onChange={handleCoverUpload} className="absolute inset-0 opacity-0 cursor-pointer" />
                </div>
              ) : (
                <div className="space-y-3">
                  <input 
                    type="url" 
                    value={coverUrl} 
                    onChange={(e) => setCoverUrl(e.target.value)}
                    className="w-full bg-[var(--secondary)]/50 border border-[var(--border)] rounded-xl px-4 py-2.5 text-xs focus:ring-2 ring-[var(--primary)]/20 outline-none transition-all"
                    placeholder="https://example.com/cover.jpg"
                  />
                  {coverUrl && (
                    <div className="relative aspect-[3/4] max-w-[140px] mx-auto rounded-2xl border border-[var(--border)] overflow-hidden">
                      <img 
                        src={coverUrl} 
                        alt="URL Cover Preview" 
                        className="w-full h-full object-cover" 
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = "https://images.unsplash.com/photo-1543002588-bfa74002ed7e?q=80&w=300";
                        }}
                      />
                      <div className="absolute top-1 right-1 bg-black/60 backdrop-blur-md px-2 py-0.5 rounded text-[8px] font-bold text-[var(--primary)]">
                        Preview
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right: Chapter Selection */}
        <div className="w-full md:w-1/2 p-4 sm:p-6 flex flex-col overflow-hidden min-h-0">
          <div className="flex items-center justify-between mb-4">
            <div className="space-y-0.5">
              <label className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Select Chapters</label>
              <p className="text-[10px] text-[var(--muted-foreground)]">{selectedIds.length} of {chapters.length} selected</p>
            </div>
            <div className="flex gap-2">
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => setSelectedIds(chapters.map(c => c.id))}
                className="text-[9px] h-7 px-2 rounded-lg"
              >
                All
              </Button>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={() => setSelectedIds(chapters.filter(c => c.has_translation).map(c => c.id))}
                className="text-[9px] h-7 px-2 rounded-lg text-[var(--primary)]"
              >
                Translated
              </Button>
            </div>
          </div>

          <div className="flex-1 min-h-[240px] md:min-h-0 overflow-y-auto space-y-1.5 pr-1 sm:pr-2 custom-scrollbar">
            {chapters.map((ch) => (
              <div 
                key={ch.id}
                onClick={() => toggleChapter(ch.id)}
                className={cn(
                  "flex items-center gap-3 p-3 rounded-xl border transition-all cursor-pointer group",
                  selectedIds.includes(ch.id) ? "bg-[var(--primary)]/5 border-[var(--primary)]/30" : "bg-[var(--secondary)]/30 border-transparent hover:border-[var(--border)]"
                )}
              >
                <div className={cn(
                  "w-5 h-5 rounded-md border flex items-center justify-center transition-all",
                  selectedIds.includes(ch.id) ? "bg-[var(--primary)] border-[var(--primary)] text-white" : "border-[var(--border)] bg-white"
                )}>
                  {selectedIds.includes(ch.id) && <Check className="w-3 h-3" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={cn(
                    "text-xs font-bold truncate",
                    selectedIds.includes(ch.id) ? "text-[var(--foreground)]" : "text-[var(--muted-foreground)]"
                  )}>
                    {ch.title_translated || ch.title_original || `Chapter ${ch.order + 1}`}
                  </p>
                  <p className="text-[9px] text-[var(--muted-foreground)]/50 uppercase tracking-tighter">
                    Chapter {ch.order + 1} • {ch.has_translation ? 'Translated' : 'Original Only'}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <div className="pt-4 sm:pt-6 mt-auto flex items-center justify-between border-t border-[var(--border)] bg-[var(--card)] sticky bottom-0">
            <Button variant="ghost" onClick={onClose} className="hidden md:flex rounded-xl">Cancel</Button>
            <Button 
              onClick={handleExport} 
              disabled={isExporting}
              className="flex-1 md:flex-none min-w-[140px] rounded-xl shadow-lg shadow-[var(--primary)]/20 gap-2 h-11"
            >
              {isExporting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Building...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  {format === 'cleanup' ? 'Preview Cleanup' : `Export ${format.toUpperCase()}`}
                </>
              )}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
