import React, { useState } from 'react';
import { 
  X, Download, Image as ImageIcon, Book, 
  Check, Loader2, FileText
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
  chapters: Chapter[];
}

export default function ExportModal({ isOpen, onClose, threadId, threadTitle, chapters }: ExportModalProps) {
  const [format, setFormat] = useState<'epub' | 'txt'>('epub');
  const [title, setTitle] = useState(threadTitle);
  const [author, setAuthor] = useState('SMONE');
  const [cover, setCover] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>(
    chapters.filter(c => c.has_translation).map(c => c.id)
  );
  const [isExporting, setIsExporting] = useState(false);

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
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/export`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          format,
          title,
          author,
          cover_b64: cover,
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
      alert('Failed to export. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
      <Card className="w-full max-w-4xl max-h-[90vh] overflow-hidden shadow-2xl border-[var(--border)] bg-[var(--card)] flex flex-col md:flex-row">
        
        {/* Left: Metadata & Settings */}
        <div className="w-full md:w-1/2 p-6 border-r border-[var(--border)] space-y-6 overflow-y-auto">
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
              <div className="grid grid-cols-2 gap-2">
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

            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-[var(--muted-foreground)] uppercase tracking-widest">Cover Image</label>
              <div className="relative group aspect-[3/4] max-w-[180px] mx-auto rounded-2xl border-2 border-dashed border-[var(--border)] overflow-hidden hover:border-[var(--primary)]/50 transition-all">
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
            </div>
          </div>
        </div>

        {/* Right: Chapter Selection */}
        <div className="w-full md:w-1/2 p-6 flex flex-col overflow-hidden">
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

          <div className="flex-1 overflow-y-auto space-y-1.5 pr-2 custom-scrollbar">
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

          <div className="pt-6 mt-auto flex items-center justify-between border-t border-[var(--border)] bg-[var(--card)]">
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
                  Export {format.toUpperCase()}
                </>
              )}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
