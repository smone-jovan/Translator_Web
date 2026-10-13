/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  X, AlertTriangle, CheckCircle2, RotateCw, 
  Search, ShieldAlert, Sparkles, Filter, CheckSquare, Square
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { getApiUrl } from '@/lib/api';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

export interface ChapterFidelityIssue {
  chapter_id: number;
  chapter_order: number;
  title_original: string | null;
  title_translated: string | null;
  fidelity_warning: string;
  original_paragraphs: number;
  translated_paragraphs: number;
  paragraph_ratio: number;
  is_truncated: boolean;
  severity: 'critical' | 'medium' | 'minor';
  issue_types: string[];
}

export interface ThreadFidelityAudit {
  thread_id: number;
  total_chapters: number;
  flagged_chapters_count: number;
  issues: ChapterFidelityIssue[];
}

interface FidelityManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  threadId: number;
  threadTitle: string;
  onRefresh?: () => void;
  onOpenReader?: (chapterId: number) => void;
}

export default function FidelityManagementModal({
  isOpen,
  onClose,
  threadId,
  threadTitle,
  onRefresh,
  onOpenReader,
}: FidelityManagementModalProps) {
  const [issues, setIssues] = useState<ChapterFidelityIssue[]>([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [activeFilter, setActiveFilter] = useState<'all' | 'critical' | 'medium' | 'minor'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const fetchIssues = useCallback(async () => {
    if (!threadId) return;
    setLoading(true);
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/fidelity-issues`));
      if (!res.ok) throw new Error('Gagal mengambil data issue fidelity');
      const data: ThreadFidelityAudit = await res.json();
      setIssues(data.issues || []);
      // Reset selected when fetching fresh
      setSelectedIds(new Set());
    } catch (err) {
      console.error(err);
      toast.error('Gagal memuat daftar isu fidelity');
    } finally {
      setLoading(false);
    }
  }, [threadId]);

  useEffect(() => {
    if (isOpen) {
      fetchIssues();
    }
  }, [isOpen, fetchIssues]);

  // Counts
  const counts = useMemo(() => {
    return {
      all: issues.length,
      critical: issues.filter(i => i.severity === 'critical').length,
      medium: issues.filter(i => i.severity === 'medium').length,
      minor: issues.filter(i => i.severity === 'minor').length,
    };
  }, [issues]);

  // Filtered issues
  const filteredIssues = useMemo(() => {
    return issues.filter(item => {
      // Filter tab
      if (activeFilter !== 'all' && item.severity !== activeFilter) {
        return false;
      }
      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const chNum = `bab ${item.chapter_order}`.toLowerCase();
        const titleTrans = (item.title_translated || '').toLowerCase();
        const titleOrig = (item.title_original || '').toLowerCase();
        const warning = (item.fidelity_warning || '').toLowerCase();
        return chNum.includes(q) || titleTrans.includes(q) || titleOrig.includes(q) || warning.includes(q);
      }
      return true;
    });
  }, [issues, activeFilter, searchQuery]);

  // Select / Deselect Handlers
  const handleToggleSelect = (chapterId: number) => {
    const next = new Set(selectedIds);
    if (next.has(chapterId)) {
      next.delete(chapterId);
    } else {
      next.add(chapterId);
    }
    setSelectedIds(next);
  };

  const handleSelectAllVisible = () => {
    const next = new Set(selectedIds);
    const visibleIds = filteredIssues.map(i => i.chapter_id);
    const allSelected = visibleIds.every(id => next.has(id));

    if (allSelected) {
      visibleIds.forEach(id => next.delete(id));
    } else {
      visibleIds.forEach(id => next.add(id));
    }
    setSelectedIds(next);
  };

  const handleSelectOnlyMinor = () => {
    const minorIds = issues.filter(i => i.severity === 'minor').map(i => i.chapter_id);
    setSelectedIds(new Set(minorIds));
    setActiveFilter('minor');
    toast.info(`Memilih ${minorIds.length} bab dengan variasi ringan (0.8–0.9)`);
  };

  // Actions
  const handleDismissSelected = async () => {
    if (selectedIds.size === 0) return;
    setActionLoading(true);
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/fidelity/dismiss`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter_ids: Array.from(selectedIds) }),
      });
      if (!res.ok) throw new Error('Gagal mengabaikan peringatan');
      const data = await res.json();
      toast.success(`${data.dismissed_count} peringatan berhasil ditandai beres / diabaikan`);
      await fetchIssues();
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error(err);
      toast.error('Terjadi kesalahan saat mengabaikan peringatan');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRetranslateSelected = async () => {
    if (selectedIds.size === 0) return;
    setActionLoading(true);
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/fidelity/retranslate`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chapter_ids: Array.from(selectedIds) }),
      });
      if (!res.ok) throw new Error('Gagal menjadwalkan terjemahan ulang');
      const data = await res.json();
      toast.success(`${data.queued_count} bab berhasil dijadwalkan untuk diterjemahkan ulang`);
      await fetchIssues();
      if (onRefresh) onRefresh();
      onClose();
    } catch (err) {
      console.error(err);
      toast.error('Terjadi kesalahan saat memulai penerjemahan ulang');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSingleDismiss = async (chapterId: number) => {
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/chapters/${chapterId}/dismiss-fidelity`), {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Gagal mengabaikan');
      toast.success('Peringatan fidelity berhasil diabaikan');
      setIssues(prev => prev.filter(i => i.chapter_id !== chapterId));
      setSelectedIds(prev => {
        const next = new Set(prev);
        next.delete(chapterId);
        return next;
      });
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error(err);
      toast.error('Gagal mengabaikan peringatan');
    }
  };

  const handleSingleRetranslate = async (chapterId: number) => {
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/chapters/${chapterId}/retranslate-fidelity`), {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Gagal menjadwalkan');
      toast.success('Bab telah masuk antrean terjemahan ulang');
      setIssues(prev => prev.filter(i => i.chapter_id !== chapterId));
      setSelectedIds(prev => {
        const next = new Set(prev);
        next.delete(chapterId);
        return next;
      });
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error(err);
      toast.error('Gagal menjadwalkan terjemahan ulang');
    }
  };

  if (!isOpen) return null;

  const isAllVisibleSelected = filteredIssues.length > 0 && filteredIssues.every(i => selectedIds.has(i.chapter_id));

  return (
    <div className="fixed inset-0 z-50 flex sm:items-center sm:justify-center bg-black/70 backdrop-blur-sm sm:p-4 p-0 animate-in fade-in duration-200">
      <Card className="relative w-full h-full sm:h-auto sm:max-h-[90vh] sm:max-w-4xl flex flex-col bg-card sm:border sm:border-border sm:rounded-3xl rounded-none shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-3.5 sm:py-4 border-b border-border bg-muted/40 flex-shrink-0">
          <div className="flex items-center gap-2.5 sm:gap-3 min-w-0 flex-1 pr-2">
            <div className="p-2 sm:p-2.5 rounded-2xl bg-amber-500/10 text-amber-500 border border-amber-500/20 flex-shrink-0 shadow-sm">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-base sm:text-lg font-bold text-foreground tracking-tight truncate">
                Fidelity Management Hub
              </h2>
              <p className="text-[11px] sm:text-xs text-muted-foreground truncate">
                {threadTitle} • <strong className="text-foreground">{issues.length}</strong> bab bermasalah
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={fetchIssues}
              disabled={loading || actionLoading}
              title="Segarkan Data"
              className="h-9 w-9 rounded-xl text-muted-foreground hover:text-foreground active:scale-95"
            >
              <RotateCw className={cn("w-4 h-4", loading && "animate-spin")} />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="h-9 w-9 rounded-xl text-muted-foreground hover:text-foreground active:scale-95"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Filter & Toolbar */}
        <div className="flex flex-col gap-2.5 px-4 sm:px-6 py-3 border-b border-border bg-background/50 flex-shrink-0">
          {/* Scrollable Filter Tabs on Mobile */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden flex-nowrap">
            <button
              onClick={() => setActiveFilter('all')}
              className={cn(
                "px-3 py-1.5 text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5 flex-shrink-0 cursor-pointer",
                activeFilter === 'all'
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "bg-muted hover:bg-muted/80 text-muted-foreground"
              )}
            >
              <Filter className="w-3 h-3" />
              Semua ({counts.all})
            </button>
            <button
              onClick={() => setActiveFilter('critical')}
              className={cn(
                "px-3 py-1.5 text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5 flex-shrink-0 cursor-pointer",
                activeFilter === 'critical'
                  ? "bg-red-600 text-white shadow-sm"
                  : "bg-red-500/10 hover:bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/20"
              )}
            >
              <AlertTriangle className="w-3 h-3" />
              Kritis ({counts.critical})
            </button>
            <button
              onClick={() => setActiveFilter('medium')}
              className={cn(
                "px-3 py-1.5 text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5 flex-shrink-0 cursor-pointer",
                activeFilter === 'medium'
                  ? "bg-amber-600 text-white shadow-sm"
                  : "bg-amber-500/10 hover:bg-amber-500/20 text-amber-600 dark:text-amber-400 border border-amber-500/20"
              )}
            >
              Sedang ({counts.medium})
            </button>
            <button
              onClick={() => setActiveFilter('minor')}
              className={cn(
                "px-3 py-1.5 text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5 flex-shrink-0 cursor-pointer",
                activeFilter === 'minor'
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-blue-500/10 hover:bg-blue-500/20 text-blue-600 dark:text-blue-400 border border-blue-500/20"
              )}
            >
              Ringan ({counts.minor})
            </button>
          </div>

          {/* Search Box & Quick Action */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2">
            <div className="relative flex-1 sm:max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Cari nomor bab atau judul..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="w-full h-8.5 pl-8.5 pr-8 text-xs rounded-xl border border-border bg-background/80 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-0.5 rounded-full"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {counts.minor > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleSelectOnlyMinor}
                className="h-8.5 text-xs font-semibold text-blue-600 dark:text-blue-400 border-blue-500/30 hover:bg-blue-500/10 rounded-xl"
              >
                Pilih Semua Ringan ({counts.minor})
              </Button>
            )}
          </div>
        </div>

        {/* Content Table / Card List */}
        <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-2">
          {loading ? (
            <div className="flex flex-col items-center justify-center h-64 gap-2 text-muted-foreground">
              <RotateCw className="w-7 h-7 animate-spin text-primary" />
              <p className="text-xs font-medium">Memeriksa data kualitas bab...</p>
            </div>
          ) : filteredIssues.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3 text-muted-foreground p-4 text-center">
              <div className="p-3 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
                <CheckCircle2 className="w-8 h-8" />
              </div>
              <div>
                <p className="text-sm font-bold text-foreground">Tidak Ada Isu Kualitas Ditemukan</p>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                  {issues.length === 0 
                    ? "Semua bab dalam novel ini bersih dari peringatan pemotongan atau ringkasan abnormal." 
                    : "Tidak ada bab yang cocok dengan filter atau kata kunci pencarian saat ini."}
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              {/* Header Checklist Row */}
              <div className="flex items-center justify-between px-3 py-2 text-xs text-muted-foreground bg-muted/40 rounded-xl border border-border/40">
                <button 
                  onClick={handleSelectAllVisible}
                  className="flex items-center gap-2 font-semibold hover:text-foreground transition-colors cursor-pointer"
                >
                  {isAllVisibleSelected ? (
                    <CheckSquare className="w-4 h-4 text-primary" />
                  ) : (
                    <Square className="w-4 h-4 text-muted-foreground" />
                  )}
                  <span>Pilih Semua yang Tampil ({filteredIssues.length})</span>
                </button>
                <span className="text-[10px] uppercase font-bold tracking-wider hidden sm:inline">Diagnostik</span>
              </div>

              {/* Items List */}
              {filteredIssues.map(item => {
                const isSelected = selectedIds.has(item.chapter_id);
                return (
                  <div
                    key={item.chapter_id}
                    className={cn(
                      "flex flex-col gap-2.5 p-3 sm:p-3.5 rounded-2xl border transition-all duration-200",
                      isSelected
                        ? "bg-primary/5 border-primary/50 shadow-sm"
                        : "bg-card hover:bg-muted/30 border-border/70",
                      item.severity === 'critical' && !isSelected && "border-l-4 border-l-red-500",
                      item.severity === 'medium' && !isSelected && "border-l-4 border-l-amber-500",
                      item.severity === 'minor' && !isSelected && "border-l-4 border-l-blue-500"
                    )}
                  >
                    {/* Top: Selection Header & Info */}
                    <div className="flex items-start gap-2.5 min-w-0">
                      <button
                        onClick={() => handleToggleSelect(item.chapter_id)}
                        className="mt-0.5 p-1 -m-1 rounded-lg text-primary hover:opacity-80 transition-opacity cursor-pointer flex-shrink-0"
                      >
                        {isSelected ? (
                          <CheckSquare className="w-4.5 h-4.5 text-primary" />
                        ) : (
                          <Square className="w-4.5 h-4.5 text-muted-foreground" />
                        )}
                      </button>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap mb-1">
                          <span className="font-extrabold text-xs text-foreground font-mono">
                            Bab {item.chapter_order}
                          </span>
                          <span className="text-xs text-muted-foreground truncate max-w-[200px] sm:max-w-md">
                            {item.title_translated || item.title_original || '(Tanpa Judul)'}
                          </span>

                          {/* Badge Severity */}
                          {item.severity === 'critical' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20 ml-auto sm:ml-0">
                              <AlertTriangle className="w-2.5 h-2.5" /> 
                              {item.is_truncated 
                                ? 'Kritis: Terpotong' 
                                : item.issue_types.includes('empty') 
                                  ? 'Kritis: Kosong' 
                                  : 'Kritis: Paragraf Anjlok'}
                            </span>
                          )}
                          {item.severity === 'medium' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 ml-auto sm:ml-0">
                              {item.issue_types.includes('inflated')
                                ? `Paragraf Menggelembung (${item.paragraph_ratio.toFixed(2)}x)`
                                : item.issue_types.includes('dialogue_drop')
                                  ? 'Dialog Berkurang'
                                  : `Sedang (${item.paragraph_ratio.toFixed(2)}x)`}
                            </span>
                          )}
                          {item.severity === 'minor' && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 ml-auto sm:ml-0">
                              {item.issue_types.includes('consolidated')
                                ? `Format Paragraf Prosa (${item.paragraph_ratio.toFixed(2)}x)`
                                : `Ringan (${item.paragraph_ratio.toFixed(2)}x)`}
                            </span>
                          )}
                        </div>

                        {/* Diagnostic Detail Message */}
                        <p className="text-[11px] sm:text-xs text-muted-foreground leading-relaxed bg-muted/30 p-2 rounded-xl border border-border/40">
                          {item.fidelity_warning}
                        </p>
                      </div>
                    </div>

                    {/* Bottom / Right: Action Buttons Group */}
                    <div className="flex items-center justify-end gap-1.5 pt-1 border-t border-border/30 sm:border-t-0 sm:pt-0">
                      {onOpenReader && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            onClose();
                            onOpenReader(item.chapter_id);
                          }}
                          className="h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground rounded-xl"
                        >
                          Lihat
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleSingleDismiss(item.chapter_id)}
                        disabled={actionLoading}
                        title="Abaikan peringatan ini tanpa terjemah ulang"
                        className="h-8 px-3 text-xs text-muted-foreground hover:text-foreground hover:bg-muted rounded-xl"
                      >
                        Abaikan
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => handleSingleRetranslate(item.chapter_id)}
                        disabled={actionLoading}
                        title="Jadwalkan ulang penerjemahan bab ini"
                        className="h-8 px-3 text-xs font-bold rounded-xl bg-amber-500/15 text-amber-600 dark:text-amber-400 hover:bg-amber-500/25 border border-amber-500/30"
                      >
                        <RotateCw className="w-3 h-3 mr-1" />
                        Perbaiki
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer Bulk Action Bar */}
        <div className="sticky bottom-0 z-10 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 sm:gap-4 px-4 sm:px-6 py-3 border-t border-border bg-card/95 backdrop-blur-md flex-shrink-0 shadow-lg">
          <div className="text-xs text-muted-foreground text-center sm:text-left font-medium">
            Terpilih: <strong className="text-foreground">{selectedIds.size}</strong> dari {issues.length} bab bermasalah
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDismissSelected}
              disabled={selectedIds.size === 0 || actionLoading}
              className="flex-1 sm:flex-initial h-9.5 text-xs font-semibold rounded-xl"
            >
              <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 text-emerald-500" />
              Abaikan ({selectedIds.size})
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={handleRetranslateSelected}
              disabled={selectedIds.size === 0 || actionLoading}
              className="flex-1 sm:flex-initial h-9.5 text-xs font-bold rounded-xl shadow-md bg-amber-500 hover:bg-amber-600 text-white"
            >
              <Sparkles className="w-3.5 h-3.5 mr-1.5 text-amber-200" />
              Perbaiki Terpilih ({selectedIds.size})
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
