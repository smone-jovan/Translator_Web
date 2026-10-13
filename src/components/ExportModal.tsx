import React, { useEffect, useState, useMemo } from 'react';
import { 
  X, Download, Image as ImageIcon, Book, 
  Check, Loader2, FileText, Eraser, Search, Settings, BookOpen, ArrowRight
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { getApiUrl } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useConfirm } from '@/hooks/use-confirm';
import { toast } from 'sonner';

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
  const { confirm } = useConfirm();
  const [format, setFormat] = useState<'epub' | 'txt' | 'cleanup'>('epub');
  const [title, setTitle] = useState(threadTitle);
  const [author, setAuthor] = useState(threadAuthor || 'SMONE');
  const [cover, setCover] = useState<string | null>(null);
  const [coverSource, setCoverSource] = useState<'file' | 'url'>('file');
  const [coverUrl, setCoverUrl] = useState('');
  const [hideThoughts, setHideThoughts] = useState(true);
  const [selectedIds, setSelectedIds] = useState<number[]>(
    chapters.filter(c => c.has_translation).map(c => c.id)
  );
  const [isExporting, setIsExporting] = useState(false);
  const [mobileTab, setMobileTab] = useState<'settings' | 'chapters'>('settings');
  const [chapterSearch, setChapterSearch] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    // Sync props to local state when modal opens — intentional reset pattern
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTitle(threadTitle);
    setAuthor(threadAuthor || 'SMONE');
    setCover(currentCover || null);
    setCoverSource(currentCover && currentCover.startsWith('http') ? 'url' : 'file');
    setCoverUrl(currentCover && currentCover.startsWith('http') ? currentCover : '');
    setSelectedIds(chapters.filter(c => c.has_translation).map(c => c.id));
    setMobileTab('settings');
    setChapterSearch('');
  }, [isOpen, threadTitle, threadAuthor, currentCover, chapters]);

  const filteredChapters = useMemo(() => {
    const q = chapterSearch.trim().toLowerCase();
    if (!q) return chapters;
    return chapters.filter(c => {
      const t = (c.title_translated || c.title_original || '').toLowerCase();
      const num = String(c.order + 1);
      return t.includes(q) || num.includes(q);
    });
  }, [chapters, chapterSearch]);

  const translatedCount = useMemo(() => {
    return chapters.filter(c => c.has_translation).length;
  }, [chapters]);

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
      toast.error('Pilih setidaknya 1 bab untuk diekspor.');
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
        a.download = `${title.replace(/[^\w\s]/gi, '_')}_cleaned.txt`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);

        const apply = await confirm({
          title: "Apply Cleanup?",
          description: `Cleanup preview generated and downloaded!\n\nStats:\n- Chapters Scanned: ${data.chapters_scanned}\n- Chapters Deleted: ${data.chapters_deleted}\n- Chapters Updated: ${data.chapters_updated}\n- Lines Removed: ${data.lines_removed}\n\nDo you want to APPLY these changes destructively to the database?`,
          confirmText: "Apply Cleanup",
          cancelText: "Cancel"
        });
        
        if (apply) {
          const applyRes = await fetch(getApiUrl(`/api/threads/${threadId}/cleanup-apply`), {
            method: 'POST',
          });
          if (!applyRes.ok) throw new Error('Apply failed');
          toast.success('Cleanup successfully applied to thread!');
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
          chapter_ids: selectedIds,
          hide_thoughts: hideThoughts
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
      toast.success(`E-Book ${title} berhasil diekspor!`);
      onClose();
    } catch (err) {
      console.error(err);
      toast.error('Gagal mengekspor e-book. Silakan coba lagi.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex sm:items-center sm:justify-center bg-black/70 backdrop-blur-sm sm:p-4 p-0 animate-in fade-in duration-200">
      <Card className="w-full h-full sm:h-auto sm:max-h-[90vh] sm:max-w-4xl overflow-hidden shadow-2xl border-0 sm:border border-border bg-card flex flex-col md:flex-row sm:rounded-3xl rounded-none">
        
        {/* Top Header Bar for Mobile & Desktop */}
        <div className="md:hidden flex items-center justify-between px-4 py-3 border-b border-border bg-muted/40 flex-shrink-0">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-xl bg-primary/10 text-primary border border-primary/20">
              <Download className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-foreground">Book Builder</h2>
              <p className="text-[10px] text-muted-foreground truncate max-w-[200px]">{threadTitle}</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 rounded-xl text-muted-foreground hover:text-foreground">
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Mobile Step Segmented Tabs */}
        <div className="md:hidden px-4 pt-3 pb-1 bg-background/50 flex-shrink-0">
          <div className="grid grid-cols-2 gap-1.5 p-1 bg-muted/60 rounded-2xl border border-border">
            <button
              type="button"
              onClick={() => setMobileTab('settings')}
              className={cn(
                "py-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer",
                mobileTab === 'settings' 
                  ? "bg-card text-foreground shadow-sm border border-border" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Settings className="w-3.5 h-3.5 text-primary" />
              <span>1. Format & Cover</span>
            </button>
            <button
              type="button"
              onClick={() => setMobileTab('chapters')}
              className={cn(
                "py-2 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer",
                mobileTab === 'chapters' 
                  ? "bg-card text-foreground shadow-sm border border-border" 
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <BookOpen className="w-3.5 h-3.5 text-primary" />
              <span>2. Bab ({selectedIds.length})</span>
            </button>
          </div>
        </div>

        {/* Left Panel: Metadata & Settings */}
        <div className={cn(
          "w-full md:w-1/2 p-4 sm:p-6 md:border-r border-border space-y-4 sm:space-y-5 overflow-y-auto flex-1 md:flex-initial",
          mobileTab === 'settings' ? "flex flex-col" : "hidden md:flex md:flex-col"
        )}>
          <div className="hidden md:flex items-center justify-between mb-2">
            <h2 className="text-xl font-black flex items-center gap-2 text-foreground">
              <Download className="w-5 h-5 text-primary" />
              Book Builder
            </h2>
            <Button variant="ghost" size="icon" onClick={onClose} className="rounded-xl h-8 w-8 text-muted-foreground hover:text-foreground">
              <X className="w-4 h-4" />
            </Button>
          </div>

          <div className="space-y-4 flex-1">
            {/* Format Selector */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Format Buku</label>
              <div className="grid grid-cols-3 gap-2">
                <button 
                  type="button"
                  onClick={() => setFormat('epub')}
                  className={cn(
                    "flex items-center justify-center gap-2 p-2.5 sm:p-3 rounded-2xl border transition-all cursor-pointer",
                    format === 'epub' 
                      ? "bg-primary/10 border-primary text-primary shadow-sm font-bold" 
                      : "border-border text-muted-foreground hover:bg-secondary/60"
                  )}
                >
                  <Book className="w-4 h-4" />
                  <span className="text-xs font-bold">EPUB</span>
                </button>
                <button 
                  type="button"
                  onClick={() => setFormat('txt')}
                  className={cn(
                    "flex items-center justify-center gap-2 p-2.5 sm:p-3 rounded-2xl border transition-all cursor-pointer",
                    format === 'txt' 
                      ? "bg-primary/10 border-primary text-primary shadow-sm font-bold" 
                      : "border-border text-muted-foreground hover:bg-secondary/60"
                  )}
                >
                  <FileText className="w-4 h-4" />
                  <span className="text-xs font-bold">TEXT</span>
                </button>
                <button 
                  type="button"
                  onClick={() => setFormat('cleanup')}
                  className={cn(
                    "flex items-center justify-center gap-2 p-2.5 sm:p-3 rounded-2xl border transition-all cursor-pointer",
                    format === 'cleanup' 
                      ? "bg-primary/10 border-primary text-primary shadow-sm font-bold" 
                      : "border-border text-muted-foreground hover:bg-secondary/60"
                  )}
                >
                  <Eraser className="w-4 h-4" />
                  <span className="text-xs font-bold">CLEAN</span>
                </button>
              </div>
            </div>

            {/* Remove Thoughts Toggle */}
            <div className="p-3 rounded-2xl bg-muted/40 border border-border/60 space-y-1">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input 
                  type="checkbox" 
                  checked={hideThoughts} 
                  onChange={(e) => setHideThoughts(e.target.checked)}
                  className="rounded border-border text-primary focus:ring-primary h-4 w-4 cursor-pointer"
                />
                <span className="text-xs font-bold text-foreground">Hapus Pemikiran AI (&lt;think&gt;)</span>
              </label>
              <p className="text-[10px] text-muted-foreground pl-6">
                Membersihkan teks pemikiran internal LLM dari buku yang diekspor.
              </p>
            </div>

            {/* Title & Author Inputs */}
            <div className="space-y-3">
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Judul E-Book</label>
                <input 
                  type="text" 
                  value={title} 
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-secondary/50 border border-border rounded-xl px-3.5 py-2 text-xs sm:text-sm text-foreground focus:ring-2 ring-primary/20 outline-none transition-all"
                  placeholder="Masukkan judul buku..."
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Nama Pengarang</label>
                <input 
                  type="text" 
                  value={author} 
                  onChange={(e) => setAuthor(e.target.value)}
                  className="w-full bg-secondary/50 border border-border rounded-xl px-3.5 py-2 text-xs sm:text-sm text-foreground focus:ring-2 ring-primary/20 outline-none transition-all"
                  placeholder="SMONE"
                />
              </div>
            </div>

            {/* Cover Selector */}
            <div className="space-y-2">
              <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Sampul E-Book (Cover)</label>
              
              <div className="grid grid-cols-2 gap-1 p-1 bg-secondary/30 rounded-xl border border-border">
                <button
                  type="button"
                  onClick={() => setCoverSource('file')}
                  className={cn(
                    "py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer",
                    coverSource === 'file' 
                      ? "bg-card text-foreground border border-border shadow-sm" 
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Upload File
                </button>
                <button
                  type="button"
                  onClick={() => setCoverSource('url')}
                  className={cn(
                    "py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer",
                    coverSource === 'url' 
                      ? "bg-card text-foreground border border-border shadow-sm" 
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Image URL
                </button>
              </div>

              {coverSource === 'file' ? (
                <div className="relative group aspect-[3/4] max-w-[130px] sm:max-w-[140px] mx-auto rounded-2xl border-2 border-dashed border-border overflow-hidden hover:border-primary/50 transition-all bg-muted/20">
                  {cover ? (
                    <>
                      <img src={cover} alt="Cover Preview" className="w-full h-full object-cover" />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-all">
                        <label className="cursor-pointer bg-white/20 backdrop-blur-md px-2.5 py-1 rounded-lg text-[10px] font-bold text-white">Ganti</label>
                      </div>
                    </>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-full gap-1.5 text-muted-foreground p-3 text-center">
                      <ImageIcon className="w-7 h-7 opacity-30" />
                      <span className="text-[10px] font-bold uppercase tracking-tight">Upload Cover</span>
                    </div>
                  )}
                  <input type="file" accept="image/*" onChange={handleCoverUpload} className="absolute inset-0 opacity-0 cursor-pointer" />
                </div>
              ) : (
                <div className="space-y-2.5">
                  <input 
                    type="url" 
                    value={coverUrl} 
                    onChange={(e) => setCoverUrl(e.target.value)}
                    className="w-full bg-secondary/50 border border-border rounded-xl px-3.5 py-2 text-xs text-foreground focus:ring-2 ring-primary/20 outline-none transition-all"
                    placeholder="https://example.com/cover.jpg"
                  />
                  {coverUrl && (
                    <div className="relative aspect-[3/4] max-w-[130px] mx-auto rounded-2xl border border-border overflow-hidden bg-muted/20 shadow-md">
                      <img 
                        src={coverUrl} 
                        alt="URL Cover Preview" 
                        className="w-full h-full object-cover" 
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = "https://images.unsplash.com/photo-1543002588-bfa74002ed7e?q=80&w=300";
                        }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Mobile Bottom Quick Switch to Step 2 */}
          <div className="md:hidden pt-3 border-t border-border mt-auto">
            <Button
              type="button"
              onClick={() => setMobileTab('chapters')}
              className="w-full h-10 rounded-xl font-bold text-xs gap-1.5"
            >
              Lanjut ke Pilih Bab ({selectedIds.length})
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Right Panel: Chapter Selection */}
        <div className={cn(
          "w-full md:w-1/2 p-4 sm:p-6 flex flex-col overflow-hidden min-h-0 flex-1",
          mobileTab === 'chapters' ? "flex" : "hidden md:flex"
        )}>
          {/* Chapter Selection Toolbar */}
          <div className="flex flex-col gap-2.5 mb-3 flex-shrink-0">
            <div className="flex items-center justify-between">
              <div>
                <label className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Pilih Bab</label>
                <p className="text-[11px] text-foreground font-semibold">
                  <strong className="text-primary">{selectedIds.length}</strong> dari {chapters.length} bab dipilih
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setSelectedIds(chapters.map(c => c.id))}
                  className="text-[10px] h-7 px-2 rounded-lg"
                >
                  Semua ({chapters.length})
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={() => setSelectedIds(chapters.filter(c => c.has_translation).map(c => c.id))}
                  className="text-[10px] h-7 px-2 rounded-lg text-primary border-primary/30"
                >
                  Terjemahan ({translatedCount})
                </Button>
                {selectedIds.length > 0 && (
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => setSelectedIds([])}
                    className="text-[10px] h-7 px-2 rounded-lg text-muted-foreground"
                  >
                    Reset
                  </Button>
                )}
              </div>
            </div>

            {/* Search filter for chapters */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Cari nomor atau judul bab..."
                value={chapterSearch}
                onChange={e => setChapterSearch(e.target.value)}
                className="w-full h-8 pl-8.5 pr-8 text-xs rounded-xl border border-border bg-secondary/40 focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
              {chapterSearch && (
                <button
                  onClick={() => setChapterSearch('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-0.5 rounded-full"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Scrollable Chapter List */}
          <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 sm:pr-2 [scrollbar-width:thin]">
            {filteredChapters.length === 0 ? (
              <div className="py-16 text-center text-xs text-muted-foreground">
                Tidak ada bab yang cocok dengan "{chapterSearch}"
              </div>
            ) : (
              filteredChapters.map((ch) => {
                const isSelected = selectedIds.includes(ch.id);
                return (
                  <div 
                    key={ch.id}
                    onClick={() => toggleChapter(ch.id)}
                    className={cn(
                      "flex items-center gap-2.5 sm:gap-3 p-2.5 sm:p-3 rounded-2xl border transition-all cursor-pointer group",
                      isSelected 
                        ? "bg-primary/5 border-primary/40 shadow-sm" 
                        : "bg-secondary/20 border-border/40 hover:border-border"
                    )}
                  >
                    <div className={cn(
                      "w-5 h-5 rounded-lg border flex items-center justify-center transition-all flex-shrink-0",
                      isSelected ? "bg-primary border-primary text-primary-foreground font-bold" : "border-border bg-background"
                    )}>
                      {isSelected && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={cn(
                        "text-xs font-bold truncate",
                        isSelected ? "text-foreground" : "text-muted-foreground"
                      )}>
                        {ch.title_translated || ch.title_original || `Bab ${ch.order + 1}`}
                      </p>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="text-[9px] font-mono text-muted-foreground/70">
                          Bab {ch.order + 1}
                        </span>
                        <span className="text-[9px] text-muted-foreground/50">•</span>
                        <span className={cn(
                          "text-[9px] font-semibold",
                          ch.has_translation ? "text-emerald-500" : "text-muted-foreground/60"
                        )}>
                          {ch.has_translation ? "Terjemahan Selesai" : "Hanya Teks Asli"}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Sticky Bottom Action Bar */}
          <div className="pt-3 sm:pt-4 mt-2 flex items-center justify-between border-t border-border bg-card flex-shrink-0">
            <Button variant="ghost" onClick={onClose} className="hidden md:flex rounded-xl">
              Batal
            </Button>
            <Button 
              onClick={handleExport} 
              disabled={isExporting || selectedIds.length === 0}
              className="w-full md:w-auto min-w-[160px] rounded-xl shadow-lg shadow-primary/20 gap-2 h-11 text-xs font-bold"
            >
              {isExporting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Membangun E-Book...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4" />
                  {format === 'cleanup' ? 'Preview Cleanup' : `Ekspor ${format.toUpperCase()} (${selectedIds.length})`}
                </>
              )}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
