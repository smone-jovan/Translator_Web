/* eslint-disable react-hooks/set-state-in-effect */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useEffect, useRef } from 'react';
import {
  X, Plus, BookOpen, Globe, FileText, Sparkles,
  Loader2, Search, Filter, Trash2, Lock,
  Settings2, Zap, Edit2, ScanSearch
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { getApiUrl } from '@/lib/api';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import RelationshipGraph from '@/components/RelationshipGraph';

interface LorebookEntry {
  id: number;
  original_term: string;
  translated_term: string;
  notes?: string;
  auto_extracted?: boolean;
  is_locked?: boolean;
  is_archived?: boolean;
}

interface ThreadItem {
  id: number;
  title: string;
  author?: string;
}

interface ExtractedTerm {
  original_term: string;
  translated_term?: string;
  notes?: string;
}

export default function ContextLibraryPage() {
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<number | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<'glossary' | 'context' | 'relationships'>('glossary');

  // Relationships
  const [relationships, setRelationships] = useState<any[]>([]);
  const [isScanningRels, setIsScanningRels] = useState(false);
  
  // Contexts
  const [globalContext, setGlobalContext] = useState('');
  const [threadContext, setThreadContext] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Glossary
  const [entries, setEntries] = useState<LorebookEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [visibleCount, setVisibleCount] = useState(50);
  
  useEffect(() => {
    setVisibleCount(50);
  }, [searchQuery]);
  const [newEntry, setNewEntry] = useState({ original: '', translated: '', notes: '' });
  const [editingEntryId, setEditingEntryId] = useState<number | null>(null);

  // AI Extract
  const [isExtracting, setIsExtracting] = useState(false);
  const [suggestions, setSuggestions] = useState<ExtractedTerm[]>([]);
  const [aiReasoning, setAiReasoning] = useState<string>('');
  const [showAiReasoning, setShowAiReasoning] = useState(false);
  const [extractMode, setExtractMode] = useState<'easy' | 'advanced'>('easy');
  const [extractSettings, setExtractSettings] = useState({ chapterCount: 25, sampleSize: 1000 });
  const [showExtractSettings, setShowExtractSettings] = useState(false);

  // Presets
  const [presets, setPresets] = useState<{ key: string; name: string; description: string; entry_count: number }[]>([]);
  const [showPresetsModal, setShowPresetsModal] = useState(false);
  const [isApplyingPreset, setIsApplyingPreset] = useState<string | null>(null);

  // Refs
  const formRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to form
  useEffect(() => {
    if (showAddForm && formRef.current) {
      formRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [showAddForm]);

  // Initial load
  useEffect(() => {
    fetch(getApiUrl('/api/threads'))
      .then(res => res.json())
      .then(data => {
        setThreads(data);
        if (data.length > 0) setSelectedThreadId(data[0].id);
      })
      .catch(e => console.error('Failed to fetch threads', e));

    fetch(getApiUrl('/api/global-context'))
      .then(res => res.json())
      .then(data => {
        setGlobalContext(data.global_context || '');
        if (data.extract_chapter_count && data.extract_sample_size) {
          setExtractSettings({
            chapterCount: data.extract_chapter_count,
            sampleSize: data.extract_sample_size
          });
        }
      })
      .catch(e => console.error('Failed to fetch global context', e));

    fetch(getApiUrl('/api/presets'))
      .then(res => res.json())
      .then(data => setPresets(data))
      .catch(e => console.error('Failed to fetch presets', e));
  }, []);

  const fetchRelationships = async () => {
    if (!selectedThreadId) return;
    try {
      const res = await fetch(getApiUrl(`/api/threads/${selectedThreadId}/relationships`));
      const data = await res.json();
      setRelationships(data);
    } catch (e) {
      console.error('Failed to fetch relationships', e);
    }
  };

  // Thread selection load
  useEffect(() => {
    if (!selectedThreadId) {
      setEntries([]);
      setThreadContext('');
      setSuggestions([]);
      setRelationships([]);
      setEditingEntryId(null);
      setShowAddForm(false);
      return;
    }
    setSuggestions([]);
    setEditingEntryId(null);
    setShowAddForm(false);
    fetch(getApiUrl(`/api/threads/${selectedThreadId}/lorebook`))
      .then(res => res.json())
      .then(data => setEntries(data))
      .catch(e => console.error('Failed to fetch lorebook', e));

    fetch(getApiUrl(`/api/threads/${selectedThreadId}/context`))
      .then(res => res.json())
      .then(data => setThreadContext(data.thread_context || ''))
      .catch(e => console.error('Failed to fetch thread context', e));

    fetchRelationships();
  }, [selectedThreadId]); // eslint-disable-line react-hooks/exhaustive-deps

  const scanRelationships = async () => {
    if (!selectedThreadId) return;
    setIsScanningRels(true);
    try {
      const res = await fetch(getApiUrl(`/api/threads/${selectedThreadId}/extract-relationships`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chapter_count: extractSettings.chapterCount,
          sample_size: extractSettings.sampleSize
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Scan failed');
      toast.success(`Scan complete! Found ${data.new_count} new relationships.`);
      fetchRelationships();
    } catch (e: any) {
      toast.error(e.message || 'Failed to scan relationships');
    } finally {
      setIsScanningRels(false);
    }
  };

  const handleApplyPreset = async (presetKey: string) => {
    if (!selectedThreadId) return;
    setIsApplyingPreset(presetKey);
    try {
      const res = await fetch(getApiUrl(`/api/threads/${selectedThreadId}/presets/${presetKey}`), {
        method: 'POST'
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to apply preset');
      toast.success(`Successfully applied preset! Added ${data.added} entries.`);
      
      // Fetch and update glossary/lorebook entries inline
      const entriesRes = await fetch(getApiUrl(`/api/threads/${selectedThreadId}/lorebook`));
      const entriesData = await entriesRes.json();
      setEntries(entriesData);
      setShowPresetsModal(false);
    } catch (e: any) {
      toast.error(e.message || 'Failed to apply preset');
    } finally {
      setIsApplyingPreset(null);
    }
  };

  const saveContext = async (type: 'global' | 'thread') => {
    setIsSaving(true);
    const endpoint = type === 'global' ? '/api/global-context' : `/api/threads/${selectedThreadId}/context`;
    const body = { context: type === 'global' ? globalContext : threadContext };
    
    try {
      await fetch(getApiUrl(endpoint), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
    } catch (e) {
      console.error('Failed to save context', e);
    } finally {
      setTimeout(() => setIsSaving(false), 500);
    }
  };

  const addEntry = async () => {
    if (!newEntry.original.trim() || !newEntry.translated.trim() || !selectedThreadId) return;
    try {
      const isEdit = editingEntryId !== null;
      const url = isEdit 
        ? getApiUrl(`/api/lorebook/${editingEntryId}`)
        : getApiUrl(`/api/threads/${selectedThreadId}/lorebook`);
      
      // Find the entry being edited to get its current lock status
      const editingEntry = entries.find(e => e.id === editingEntryId);
      const isLockedVal = editingEntry ? editingEntry.is_locked : false;

      const res = await fetch(url, {
        method: isEdit ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_term: newEntry.original,
          translated_term: newEntry.translated,
          notes: newEntry.notes || undefined,
          is_locked: isLockedVal
        })
      });
      const data = await res.json();
      
      if (isEdit) {
        setEntries(prev => prev.map(e => e.id === editingEntryId ? data : e));
      } else {
        setEntries(prev => [...prev, data]);
        // Remove from suggestions list if matching
        setSuggestions(prev => prev.filter(sug => sug.original_term.trim().toLowerCase() !== newEntry.original.trim().toLowerCase()));
      }
      
      setNewEntry({ original: '', translated: '', notes: '' });
      setEditingEntryId(null);
      setShowAddForm(false);
    } catch (e) {
      console.error('Failed to add/update entry', e);
    }
  };

  const quickAddEntry = async (sug: ExtractedTerm, isLocked: boolean = false) => {
    if (!sug.original_term.trim() || !selectedThreadId) return;
    try {
      const res = await fetch(getApiUrl(`/api/threads/${selectedThreadId}/lorebook`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_term: sug.original_term,
          translated_term: sug.translated_term || '',
          notes: sug.notes || undefined,
          is_locked: isLocked
        })
      });
      const data = await res.json();
      setEntries(prev => [...prev, data]);
      // Remove from suggestions array immediately
      setSuggestions(prev => prev.filter(s => s.original_term.toLowerCase() !== sug.original_term.toLowerCase()));
    } catch (e) {
      console.error('Failed to quick add entry', e);
    }
  };

  const toggleLock = async (entry: LorebookEntry) => {
    try {
      const res = await fetch(getApiUrl(`/api/lorebook/${entry.id}/lock`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_locked: !entry.is_locked })
      });
      const data = await res.json();
      setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, is_locked: data.is_locked } : e));
    } catch (e) {
      console.error('Failed to toggle lock', e);
    }
  };

  const handleDismissSuggestion = (originalTerm: string) => {
    setSuggestions(prev => prev.filter(s => s.original_term.toLowerCase() !== originalTerm.toLowerCase()));
  };

  const startEditing = (entry: LorebookEntry) => {
    setNewEntry({
      original: entry.original_term,
      translated: entry.translated_term,
      notes: entry.notes || ''
    });
    setEditingEntryId(entry.id);
    setShowAddForm(true);
  };

  const removeEntry = async (id: number) => {
    try {
      await fetch(getApiUrl(`/api/lorebook/${id}`), { method: 'DELETE' });
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch (e) {
      console.error('Failed to remove entry', e);
    }
  };

  const handleExtractContext = async () => {
    if (!selectedThreadId) return;
    setIsExtracting(true);
    setAiReasoning('');
    setShowAiReasoning(false);
    
    const lmUrl = localStorage.getItem('lm_url') || 'http://localhost:1234';
    const lmModel = localStorage.getItem('lm_model') || '';

    try {
      const res = await fetch(getApiUrl(`/api/threads/${selectedThreadId}/extract-context`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          lm_url: lmUrl, 
          model: lmModel || undefined,
          chapter_count: extractSettings.chapterCount,
          sample_size: extractSettings.sampleSize
        })
      });
      
      let data: any = {};
      try {
        data = await res.json();
      } catch (err) {
        throw new Error('Server returned an unexpected plain text format. Please check the backend uvicorn terminal logs.', { cause: err });
      }
      
      if (!res.ok) {
        throw new Error(data.detail || 'Extraction failed.');
      }

      if (data.metadata?.reasoning) {
        setAiReasoning(data.metadata.reasoning);
      }

      // Filter out suggestions that already exist in the glossary (entries state)
      const existingOriginals = new Set(entries.map(e => e.original_term.trim().toLowerCase()));
      const filteredSuggestions = (data.terms || []).filter((sug: ExtractedTerm) => 
        !existingOriginals.has(sug.original_term.trim().toLowerCase())
      );
      setSuggestions(filteredSuggestions);
    } catch (e: any) {
      alert(`Extraction Failed: ${e.message || 'Unknown error'}`);
    } finally {
      setIsExtracting(false);
    }
  };

  const saveExtractSettings = async (chapterCount: number, sampleSize: number) => {
    try {
      await fetch(getApiUrl('/api/settings'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          extract_chapter_count: chapterCount,
          extract_sample_size: sampleSize
        })
      });
    } catch (e) {
      console.error('Failed to save extract settings to server', e);
    }
  };

  const setPreset = (type: 'quick' | 'normal' | 'deep') => {
    let cc = 25, ss = 1000;
    if (type === 'quick') { cc = 5; ss = 1000; }
    else if (type === 'normal') { cc = 15; ss = 1000; }
    else if (type === 'deep') { cc = 25; ss = 1000; }
    setExtractSettings({ chapterCount: cc, sampleSize: ss });
    saveExtractSettings(cc, ss);
  };

  const estInputTokens = Math.ceil(
    150 + 
    (globalContext.length / 4) + 
    (extractSettings.chapterCount * extractSettings.sampleSize * 1.5)
  );
  const estTotalTokens = estInputTokens + 1500;

  const selectedThread = threads.find(t => t.id === selectedThreadId);

  const filteredEntries = entries.filter(e => 
    e.original_term.toLowerCase().includes(searchQuery.toLowerCase()) ||
    e.translated_term.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (e.notes || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const displayedEntries = filteredEntries.slice(0, visibleCount);

  return (
    <div className="flex flex-col md:flex-row min-h-[calc(100vh-100px)] w-full bg-[var(--background)] gap-6">
      {/* Internal Sidebar: Thread List */}
      <aside className="w-full md:w-72 md:sticky md:top-8 md:h-[calc(100vh-8rem)] rounded-3xl flex flex-col bg-[var(--card)]/50 border border-[var(--border)] overflow-hidden shadow-xl">
        <div className="p-4 border-b border-[var(--border)] bg-[var(--card)] flex-shrink-0">
          <div className="flex items-center gap-2 mb-4">
            <BookOpen size={18} className="text-[var(--primary)]" />
            <h2 className="font-bold text-[var(--foreground)] tracking-tight">Global Context</h2>
          </div>
          
          <button 
            onClick={() => setSelectedThreadId(null)}
            className={cn(
              "w-full flex items-center justify-between px-3 py-2.5 rounded-xl transition-all font-medium text-sm border",
              selectedThreadId === null 
                ? "bg-[var(--primary)]/10 text-[var(--primary)] border-[var(--primary)]/30" 
                : "bg-[var(--secondary)] text-[var(--foreground)] border-transparent hover:border-[var(--border)]"
            )}
          >
            <div className="flex items-center gap-2">
              <Globe size={16} />
              <span>All Threads</span>
            </div>
            {selectedThreadId === null && <div className="w-1.5 h-1.5 rounded-full bg-[var(--primary)]" />}
          </button>
        </div>
        
        <div className="md:hidden p-4 border-b border-[var(--border)]">
          <select
            value={selectedThreadId ?? ''}
            onChange={(e) => setSelectedThreadId(e.target.value ? parseInt(e.target.value, 10) : null)}
            className="w-full rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3 text-sm outline-none"
          >
            {threads.map(thread => (
              <option key={thread.id} value={thread.id}>{thread.title}</option>
            ))}
          </select>
        </div>

        <div className="hidden md:block flex-1 overflow-auto py-4 px-3 space-y-1 custom-scrollbar">
          {threads.map(thread => (
            <button
              key={thread.id}
              onClick={() => setSelectedThreadId(thread.id)}
              className={cn(
                "w-full text-left px-4 py-3 rounded-xl transition-all duration-200 group",
                selectedThreadId === thread.id
                  ? "bg-[var(--accent)] text-[var(--primary)] shadow-sm"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]"
              )}
            >
              <div className="font-medium text-sm truncate">{thread.title}</div>
              <div className="text-[10px] opacity-70 mt-0.5 truncate">{thread.author || 'Unknown Author'}</div>
            </button>
          ))}
        </div>

        <div className="p-4 border-t border-[var(--border)] bg-[var(--card)]">
          <button className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-[var(--border)] text-sm font-medium text-[var(--muted-foreground)] hover:bg-[var(--secondary)] transition-all">
            <Plus size={16} /> New Context
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 rounded-3xl bg-[var(--card)]/30 border border-[var(--border)] shadow-xl">
        {selectedThread ? (
          <>
            {/* Thread Header */}
            <header className="sticky top-0 px-4 md:px-8 py-5 md:py-6 border-b border-[var(--border)] bg-[var(--card)]/80 backdrop-blur-md z-[60]">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-6">
                <div>
                  <h1 className="text-2xl font-bold text-[var(--foreground)] tracking-tight">
                    {selectedThread.title}
                  </h1>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">
                    Manage terminology and translation behavior.
                  </p>
                </div>
                <div className="flex items-center gap-3 relative self-start lg:self-auto">
                  <div className="flex items-center bg-[var(--card)] border border-[var(--border)] rounded-xl p-1 shadow-sm">
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className={cn(
                        "rounded-lg gap-2 h-8 px-3 transition-all",
                        isExtracting ? "opacity-50" : "hover:bg-[var(--accent)] hover:text-[var(--primary)]"
                      )}
                      onClick={handleExtractContext}
                      disabled={isExtracting}
                    >
                      {isExtracting ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} className="text-yellow-500" />}
                      <span className="hidden sm:inline">AI Extract</span>
                    </Button>
                    <div className="w-[1px] h-4 bg-[var(--border)] mx-1" />
                    <button 
                      onClick={() => setShowExtractSettings(!showExtractSettings)}
                      className={cn(
                        "p-1.5 rounded-lg transition-colors hover:bg-[var(--secondary)]",
                        showExtractSettings ? "text-[var(--primary)] bg-[var(--accent)]" : "text-[var(--muted-foreground)]"
                      )}
                    >
                      <Settings2 size={14} />
                    </button>
                  </div>

                  {/* Extract Settings Popover */}
                  {showExtractSettings && (
                    <div className="absolute top-full right-0 mt-4 w-72 bg-[var(--card)] border border-[var(--border)] rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.3)] z-[100] p-5 animate-in fade-in slide-in-from-top-2 duration-200">
                      <div className="flex items-center justify-between mb-4">
                        <h4 className="text-sm font-bold flex items-center gap-2">
                          <Zap size={14} className="text-yellow-500" /> Extraction Scope
                        </h4>
                        <button 
                          onClick={() => setExtractMode(prev => prev === 'easy' ? 'advanced' : 'easy')}
                          className={cn(
                            "px-2.5 py-1 text-[10px] font-bold rounded-lg transition-all border",
                            extractMode === 'advanced' 
                              ? "bg-[var(--accent)] text-[var(--primary)] border-[var(--primary)]/20 shadow-sm" 
                              : "bg-[var(--secondary)] text-[var(--muted-foreground)] border-transparent hover:border-[var(--border)]"
                          )}
                        >
                          {extractMode === 'advanced' ? "FINE-TUNED" : "ADVANCED"}
                        </button>
                      </div>

                      {/* Presets - Always Visible for quick selection */}
                      <div className="grid grid-cols-3 gap-2 mb-4">
                        {[
                          { id: 'quick', label: 'Quick', ch: 5, size: 1000 },
                          { id: 'normal', label: 'Normal', ch: 15, size: 1000 },
                          { id: 'deep', label: 'Deep', ch: 25, size: 1000 }
                        ].map(p => {
                          const active = extractSettings.chapterCount === p.ch && extractSettings.sampleSize === p.size;
                          return (
                            <button
                              key={p.id}
                              onClick={() => {
                                setPreset(p.id as any);
                                setExtractMode('easy');
                              }}
                              className={cn(
                                "flex flex-col items-center py-2 rounded-xl border-2 transition-all duration-200",
                                active
                                  ? "border-[var(--primary)] bg-[var(--primary)]/5 text-[var(--primary)] shadow-sm"
                                  : "border-[var(--border)] bg-transparent text-[var(--muted-foreground)] hover:border-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                              )}
                            >
                              <span className="text-[10px] font-bold uppercase">{p.label}</span>
                              <span className="text-[9px] opacity-75 mt-0.5">{p.ch} Ch</span>
                            </button>
                          );
                        })}
                      </div>

                      {/* Collapsible Sliders in Advanced Mode */}
                      {extractMode === 'advanced' && (
                        <div className="space-y-4 mb-4 pt-3 border-t border-dashed border-[var(--border)] animate-in fade-in slide-in-from-top-1 duration-200">
                          <div>
                            <div className="flex justify-between mb-1">
                              <label className="text-[10px] font-bold uppercase text-[var(--muted-foreground)]">Chapters Ahead</label>
                              <span className="text-[10px] font-mono font-bold text-[var(--primary)]">{extractSettings.chapterCount} Ch</span>
                            </div>
                            <input 
                              type="range" min="1" max="50" step="1"
                              value={extractSettings.chapterCount}
                              onChange={e => {
                                const val = parseInt(e.target.value);
                                setExtractSettings(prev => {
                                  const next = { ...prev, chapterCount: val };
                                  saveExtractSettings(next.chapterCount, next.sampleSize);
                                  return next;
                                });
                              }}
                              className="w-full h-1.5 bg-[var(--secondary)] rounded-lg appearance-none cursor-pointer accent-[var(--primary)]"
                            />
                          </div>
                          <div>
                            <div className="flex justify-between mb-1">
                              <label className="text-[10px] font-bold uppercase text-[var(--muted-foreground)]">Sample Size</label>
                              <span className="text-[10px] font-mono font-bold text-[var(--primary)]">{extractSettings.sampleSize} Chars</span>
                            </div>
                            <input 
                              type="range" min="200" max="20000" step="100"
                              value={extractSettings.sampleSize}
                              onChange={e => {
                                const val = parseInt(e.target.value);
                                setExtractSettings(prev => {
                                  const next = { ...prev, sampleSize: val };
                                  saveExtractSettings(next.chapterCount, next.sampleSize);
                                  return next;
                                });
                              }}
                              className="w-full h-1.5 bg-[var(--secondary)] rounded-lg appearance-none cursor-pointer accent-[var(--primary)]"
                            />
                          </div>
                        </div>
                      )}

                      <div className="pt-3 border-t border-[var(--border)] space-y-2">
                        <div className="grid grid-cols-2 gap-2 text-left">
                          <div>
                            <span className="text-[9px] font-bold uppercase text-[var(--muted-foreground)] block">Est. Input</span>
                            <span className="text-xs font-mono font-bold text-[var(--foreground)]">~{estInputTokens.toLocaleString()} tokens</span>
                          </div>
                          <div>
                            <span className="text-[9px] font-bold uppercase text-[var(--muted-foreground)] block">Max Output</span>
                            <span className="text-xs font-mono font-bold text-[var(--foreground)]">~1,500 tokens</span>
                          </div>
                        </div>
                        <div className="pt-2 border-t border-dashed border-[var(--border)] flex items-center justify-between">
                          <div className="flex flex-col">
                            <span className="text-[9px] font-bold uppercase text-[var(--primary)]">Context Needed</span>
                            <span className="text-sm font-mono font-bold text-[var(--primary)]">~{estTotalTokens.toLocaleString()} tokens</span>
                          </div>
                          <Button size="sm" variant="outline" className="h-7 text-[10px] px-2 rounded-lg" onClick={() => setShowExtractSettings(false)}>
                            Done
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}

                  <Button 
                    variant="outline"
                    size="sm" 
                    className="rounded-xl gap-2 h-9 px-4"
                    onClick={() => setShowPresetsModal(true)}
                  >
                    <Sparkles size={14} className="text-[var(--primary)]" />
                    <span className="hidden sm:inline">Apply Preset</span>
                  </Button>

                  <Button 
                    size="sm" 
                    className="rounded-xl gap-2 shadow-lg shadow-[var(--primary)]/20"
                    onClick={() => {
                      setEditingEntryId(null);
                      setNewEntry({ original: '', translated: '', notes: '' });
                      setShowAddForm(true);
                    }}
                  >
                    <Plus size={14} /> <span className="hidden sm:inline">Add Term</span>
                  </Button>
                </div>
              </div>

              {/* Sub-Tabs */}
              <div className="flex gap-8 border-b border-[var(--border)] -mb-6">
                <button 
                  onClick={() => setActiveSubTab('glossary')}
                  className={cn(
                    "pb-4 text-sm font-semibold transition-all relative flex items-center gap-2",
                    activeSubTab === 'glossary' ? "text-[var(--primary)]" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  )}
                >
                  <BookOpen size={16} /> Glossary ({entries.length})
                  {activeSubTab === 'glossary' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />}
                </button>
                <button 
                  onClick={() => setActiveSubTab('context')}
                  className={cn(
                    "pb-4 text-sm font-semibold transition-all relative flex items-center gap-2",
                    activeSubTab === 'context' ? "text-[var(--primary)]" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  )}
                >
                  <Filter size={16} className="rotate-90" /> Rules
                  {activeSubTab === 'context' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />}
                </button>
                <button
                  onClick={() => setActiveSubTab('relationships')}
                  className={cn(
                    "pb-4 text-sm font-semibold transition-all relative flex items-center gap-2",
                    activeSubTab === 'relationships' ? "text-[var(--primary)]" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  )}
                >
                  <Globe size={16} /> Relationships ({relationships.length})
                  {activeSubTab === 'relationships' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />}
                </button>
              </div>
            </header>

            {/* Content Tab: Glossary or Rules */}
            <div className="flex-1 p-4 md:p-8">
              {activeSubTab === 'glossary' && (
                <div className="space-y-8">
                  {/* ... (Glossary content same as before) ... */}
                  {/* Search & Filter Bar */}
                  <div className="flex gap-4">
                    <div className="flex-1 relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]" size={18} />
                      <input 
                        type="text" 
                        value={searchQuery}
                        onChange={e => setSearchQuery(e.target.value)}
                        placeholder="Search glossary terms..."
                        className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-[var(--card)] border border-[var(--border)] text-sm focus:outline-none focus:border-[var(--primary)] transition-all"
                      />
                    </div>
                    <Button variant="outline" size="icon" className="rounded-xl"><Filter size={18} /></Button>
                  </div>

                  {/* Add Entry Form */}
                  {showAddForm && (
                    <div ref={formRef} className="scroll-mt-20">
                      <Card className="border-[var(--primary)] bg-[var(--accent)]/5 shadow-xl transition-all">
                        <CardContent className="p-6 space-y-6">
                          <div className="flex justify-between items-center pb-2 border-b border-[var(--border)]">
                            <div className="flex items-center gap-2">
                              <div className="w-8 h-8 rounded-lg bg-[var(--primary)] text-white flex items-center justify-center">
                                {editingEntryId ? <FileText size={16} /> : <Plus size={16} />}
                              </div>
                              <h3 className="font-bold text-base">{editingEntryId ? 'Edit Term' : 'Add New Term'}</h3>
                            </div>
                            <div className="flex items-center gap-3">
                              {editingEntryId && (
                                <button 
                                  onClick={() => {
                                    setEditingEntryId(null);
                                    setNewEntry({ original: '', translated: '', notes: '' });
                                    setShowAddForm(false);
                                  }}
                                  className="text-xs font-semibold text-red-500 hover:underline"
                                >
                                  Cancel Edit
                                </button>
                              )}
                              <button 
                                onClick={() => {
                                  setShowAddForm(false);
                                  setEditingEntryId(null);
                                  setNewEntry({ original: '', translated: '', notes: '' });
                                }}
                                className="p-2 hover:bg-[var(--secondary)] rounded-full transition-colors"
                              >
                                <X size={18} />
                              </button>
                            </div>
                          </div>
                          
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-2">
                              <label className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] ml-1">Original Term</label>
                              <input 
                                value={newEntry.original}
                                onChange={e => setNewEntry({...newEntry, original: e.target.value})}
                                placeholder="e.g. 仙侠" 
                                className="w-full bg-[var(--card)] border-2 border-[var(--border)] focus:border-[var(--primary)] rounded-xl px-4 py-3 text-sm transition-all outline-none"
                              />
                            </div>
                            <div className="space-y-2">
                              <label className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] ml-1">Translated Term</label>
                              <input 
                                value={newEntry.translated}
                                onChange={e => setNewEntry({...newEntry, translated: e.target.value})}
                                placeholder="e.g. Xianxia" 
                                className="w-full bg-[var(--card)] border-2 border-[var(--border)] focus:border-[var(--primary)] rounded-xl px-4 py-3 text-sm transition-all outline-none"
                              />
                            </div>
                          </div>
                          <div className="space-y-2">
                            <label className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)] ml-1">Notes / Context</label>
                            <input 
                              value={newEntry.notes}
                              onChange={e => setNewEntry({...newEntry, notes: e.target.value})}
                              placeholder="e.g. Name of the protagonist's sword style." 
                              className="w-full bg-[var(--card)] border-2 border-[var(--border)] focus:border-[var(--primary)] rounded-xl px-4 py-3 text-sm transition-all outline-none"
                            />
                          </div>
                          <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border)]">
                            <Button variant="ghost" className="rounded-xl px-6" onClick={() => {
                              setShowAddForm(false);
                              setEditingEntryId(null);
                              setNewEntry({ original: '', translated: '', notes: '' });
                            }}>Cancel</Button>
                            <Button className="rounded-xl px-8 shadow-lg shadow-[var(--primary)]/20" onClick={addEntry}>
                              {editingEntryId ? 'Update Term' : 'Save Term'}
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  )}

                  {/* AI Suggestions Section */}
                  {(suggestions.length > 0 || aiReasoning) && (
                    <div className="space-y-4">
                      {/* AI Reasoning Accordion */}
                      {aiReasoning && (
                        <div className="mb-6 rounded-xl border border-[var(--primary)]/20 bg-[var(--primary)]/5 overflow-hidden">
                          <button 
                            onClick={() => setShowAiReasoning(!showAiReasoning)}
                            className="w-full flex items-center justify-between p-4 text-left hover:bg-[var(--primary)]/5 transition-colors"
                          >
                            <div className="flex items-center gap-2">
                              <Sparkles size={16} className="text-[var(--primary)]" />
                              <span className="text-sm font-bold text-[var(--foreground)]">AI Reasoning & Lore Notes</span>
                            </div>
                            <span className="text-xs text-[var(--primary)] font-semibold uppercase tracking-wider">
                              {showAiReasoning ? 'Hide' : 'Read Notes'}
                            </span>
                          </button>
                          {showAiReasoning && (
                            <div className="p-4 border-t border-[var(--primary)]/10 text-sm text-[var(--muted-foreground)] leading-relaxed font-serif whitespace-pre-wrap">
                              {aiReasoning}
                            </div>
                          )}
                        </div>
                      )}

                      {suggestions.length > 0 && (
                        <>
                          <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--primary)] flex items-center gap-2">
                            <Sparkles size={14} /> AI Detected Suggestions <span className="text-[10px] text-[var(--muted-foreground)] font-medium normal-case">({suggestions.length} left)</span>
                          </h3>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {suggestions.map((sug, i) => (
                          <Card key={i} className="border-amber-200/50 bg-amber-50/20 dark:border-amber-950/30 dark:bg-amber-950/10">
                            <CardContent className="p-4 flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="font-bold text-sm truncate">{sug.original_term}</div>
                                {sug.translated_term && (
                                  <div className="text-xs font-semibold text-[var(--primary)] mb-1">{sug.translated_term}</div>
                                )}
                                <div className="text-[10px] text-[var(--muted-foreground)] mt-1 line-clamp-2">{sug.notes}</div>
                              </div>
                              <div className="flex flex-col gap-1.5 shrink-0">
                                <button 
                                  onClick={() => quickAddEntry(sug)}
                                  title="Quick Add"
                                  className="p-1.5 bg-emerald-100 dark:bg-emerald-950/40 rounded-lg text-emerald-700 dark:text-emerald-400 hover:scale-110 active:scale-95 transition-all"
                                >
                                  <Plus size={14} />
                                </button>
                                <button 
                                  onClick={() => quickAddEntry(sug, true)}
                                  title="Accept & Lock"
                                  className="p-1.5 bg-blue-100 dark:bg-blue-950/40 rounded-lg text-blue-700 dark:text-blue-400 hover:scale-110 active:scale-95 transition-all"
                                >
                                  <Lock size={14} />
                                </button>
                                <button 
                                  onClick={() => {
                                    setNewEntry({ 
                                      original: sug.original_term, 
                                      translated: sug.translated_term || '', 
                                      notes: sug.notes || '' 
                                    });
                                    setShowAddForm(true);
                                    setEditingEntryId(null);
                                  }}
                                  title="Edit & Add"
                                  className="p-1.5 bg-amber-100 dark:bg-amber-950/40 rounded-lg text-amber-700 dark:text-amber-400 hover:scale-110 active:scale-95 transition-all"
                                >
                                  <Edit2 size={14} />
                                </button>
                                <button 
                                  onClick={() => handleDismissSuggestion(sug.original_term)}
                                  title="Dismiss"
                                  className="p-1.5 bg-rose-100 dark:bg-rose-950/40 rounded-lg text-rose-700 dark:text-rose-400 hover:scale-110 active:scale-95 transition-all"
                                >
                                  <X size={14} />
                                </button>
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                        </>
                      )}
                    </div>
                  )}

                  {/* Term Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                    {displayedEntries.map(entry => (
                      <Card key={entry.id} className="group hover:border-[var(--primary)]/50 transition-all duration-300 shadow-sm hover:shadow-md relative overflow-hidden">
                        <CardContent className="p-6">
                          <div className="flex justify-between items-start mb-4">
                            <div className="w-10 h-10 rounded-xl bg-[var(--accent)] flex items-center justify-center text-[var(--primary)] font-bold">
                              {entry.original_term.charAt(0)}
                            </div>
                            <div className="flex gap-1.5 items-center">
                              {/* Lock Toggle Button - Always visible if locked, hover visible if unlocked */}
                              <button 
                                onClick={() => toggleLock(entry)}
                                className={cn(
                                  "p-1.5 rounded-lg hover:scale-110 active:scale-95 transition-all",
                                  entry.is_locked 
                                    ? "bg-amber-500/10 text-amber-500 border border-amber-500/20 shadow-sm" 
                                    : "bg-slate-50 dark:bg-slate-950/20 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900 opacity-0 group-hover:opacity-100 transition-all duration-300"
                                )}
                                title={entry.is_locked ? "Unlock Term (Allow Auto-Eviction)" : "Lock & Protect Term"}
                              >
                                <Lock size={14} className={cn(entry.is_locked ? "fill-amber-500/20" : "")} />
                              </button>

                              <div className="flex gap-1.5 opacity-0 group-hover:opacity-100 transition-all duration-300">
                                <button 
                                  onClick={() => startEditing(entry)}
                                  className="p-1.5 bg-amber-50 dark:bg-amber-950/20 text-amber-600 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-950/40 rounded-lg hover:scale-110 active:scale-95 transition-all"
                                  title="Edit term"
                                >
                                  <Edit2 size={14} />
                                </button>
                                <button 
                                  onClick={() => removeEntry(entry.id)} 
                                  className="p-1.5 bg-rose-50 dark:bg-rose-950/20 text-rose-600 dark:text-rose-400 hover:bg-rose-100 dark:hover:bg-rose-950/40 rounded-lg hover:scale-110 active:scale-95 transition-all"
                                  title="Delete term"
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </div>
                          </div>
                          
                          <div className="space-y-1">
                            <h3 className="font-bold text-lg text-[var(--foreground)] leading-tight">{entry.translated_term}</h3>
                            <p className="text-xs text-[var(--muted-foreground)] font-medium">{entry.original_term}</p>
                          </div>
                          
                          <div className="mt-4 pt-4 border-t border-[var(--border)]">
                            <p className="text-xs text-[var(--muted-foreground)] line-clamp-2 italic">
                              "{entry.notes || 'No description provided.'}"
                            </p>
                          </div>
                          
                          {entry.auto_extracted && (
                            <div className="mt-3 flex items-center gap-1.5">
                              <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                              <span className="text-[10px] text-blue-500 font-bold uppercase tracking-tighter">Auto-extracted</span>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    ))}

                    {filteredEntries.length === 0 && (
                      <div className="col-span-full py-20 text-center border-2 border-dashed border-[var(--border)] rounded-3xl">
                        <BookOpen className="mx-auto w-12 h-12 text-[var(--muted-foreground)] mb-4 opacity-20" />
                        <h3 className="text-lg font-bold text-[var(--foreground)]">No terms found</h3>
                        <p className="text-sm text-[var(--muted-foreground)]">Add your first term to build the glossary.</p>
                      </div>
                    )}

                    {filteredEntries.length > visibleCount && (
                      <div className="col-span-full flex justify-center py-6">
                        <Button 
                          variant="outline" 
                          onClick={() => setVisibleCount(v => v + 50)}
                          className="rounded-xl bg-[var(--card)] hover:bg-[var(--accent)] text-[var(--foreground)]"
                        >
                          Load More Context Terms ({filteredEntries.length - visibleCount} left)
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Content Tab: Rules */}
              {activeSubTab === 'context' && (
                <div className="space-y-8 md:space-y-10 max-w-5xl mx-auto pb-12">
                  {/* Section 1: Translation Instructions */}
                  <section className="space-y-4">
                    <div className="flex flex-col">
                      <h3 className="text-lg font-bold text-[var(--foreground)]">Translation Instructions</h3>
                      <p className="text-sm text-[var(--muted-foreground)]">Custom instructions for translation style — tone, point of view, fluency, and more.</p>
                    </div>
                    
                    <div className="space-y-3">
                      <Textarea 
                        value={globalContext}
                        onChange={e => setGlobalContext(e.target.value)}
                        placeholder="e.g. Translate strictly line-by-line, ensuring each source line corresponds to one output line. Preserve original sentence structure and word order as much as possible while keeping the translation natural and idiomatic."
                        className="min-h-[160px] text-sm bg-[var(--card)]/50 border-[var(--border)] focus:border-[var(--primary)] rounded-xl"
                      />
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-mono text-[var(--muted-foreground)] uppercase tracking-widest">
                          {globalContext.length}/1000
                        </span>
                        <Button 
                          size="sm" 
                          className="rounded-lg gap-2 bg-[#A89F8D] hover:bg-[#968D7B] text-white border-none shadow-none"
                          onClick={() => saveContext('global')}
                          disabled={isSaving}
                        >
                          {isSaving ? <Loader2 size={14} className="animate-spin" /> : null}
                          Save Instructions
                        </Button>
                      </div>
                    </div>
                  </section>

                  {/* Section 2: Term Conventions */}
                  <section className="space-y-4">
                    <div className="flex items-center gap-3">
                      <h3 className="text-lg font-bold text-[var(--foreground)]">Term Conventions</h3>
                      <span className="px-2 py-0.5 rounded-full bg-[var(--secondary)] text-[var(--muted-foreground)] text-[10px] font-medium border border-[var(--border)]">
                        Advanced term extraction only
                      </span>
                    </div>
                    <p className="text-sm text-[var(--muted-foreground)] -mt-2">Structured rules that control how terms are translated.</p>

                    <div className="space-y-3">
                      {/* Built-in Status Box */}
                      <div className="flex items-center justify-between p-4 bg-[var(--card)]/30 border border-[var(--border)] rounded-2xl">
                        <div className="flex items-center gap-3 text-sm text-[var(--muted-foreground)]">
                          <Globe size={16} />
                          <span>Using built-in defaults <span className="opacity-60">— built-in rules provided by SMONE</span></span>
                        </div>
                        <Button variant="outline" size="sm" className="rounded-lg gap-2 text-xs h-8 px-3">
                          <Plus size={14} /> Customize
                        </Button>
                      </div>

                      {/* Locked Rule Cards */}
                      {[
                        { 
                          title: "Context over Dictionary", 
                          desc: "Always deduce the entity type and domain from the provided context (e.g., surrounding text, sibling terms in a cluster). Prioritize structural consistency." 
                        },
                        { 
                          title: "Translate vs Transliterate", 
                          desc: "Fully translate objects, artifacts, techniques, and fictional organizations into English. Keep character names and established real-world terms in their standard Pinyin or localized forms." 
                        },
                        { 
                          title: "World-Building Context", 
                          desc: "Do not blindly map terms to real-world locations if the text is a fantasy or historical setting (e.g., translate 京都 as 'The Capital' or 'Imperial City' instead of 'Kyoto')." 
                        },
                        { 
                          title: "Honorifics & Address", 
                          desc: "Follow source language norms. Translate Chinese honorifics to English (e.g., Senior Brother, Elder, Young Master). Retain common Japanese/Korean suffixes if applicable." 
                        }
                      ].map((rule, idx) => (
                        <div key={idx} className="flex items-center justify-between p-4 bg-[var(--card)]/20 border border-[var(--border)] rounded-xl group hover:border-[var(--primary)]/30 transition-all">
                          <div className="flex-1 min-w-0 pr-4">
                            <span className="text-sm font-medium text-[var(--muted-foreground)] group-hover:text-[var(--foreground)] transition-colors">
                              {rule.title}: <span className="font-normal opacity-70">{rule.desc}</span>
                            </span>
                          </div>
                          <div className="flex items-center gap-3 shrink-0">
                            <span className="text-[10px] font-bold uppercase tracking-tighter px-2 py-0.5 rounded bg-[var(--secondary)] text-[var(--muted-foreground)]">All terms</span>
                            <Trash2 size={16} className="text-[var(--muted-foreground)] opacity-40" />
                            <div className="p-1 bg-[var(--secondary)] rounded text-[var(--muted-foreground)]">
                              <Lock size={12} />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </section>
                </div>
              )}

              {activeSubTab === 'relationships' && (
                <div className="space-y-6 h-full flex flex-col">
                  <div className="flex items-center justify-between">
                    <div className="space-y-1">
                      <h3 className="text-xl font-bold tracking-tight">Character Network</h3>
                      <p className="text-xs text-[var(--muted-foreground)]">AI-detected interpersonal connections and affiliations.</p>
                    </div>
                    <Button
                      onClick={scanRelationships}
                      disabled={isScanningRels}
                      className="rounded-xl gap-2 shadow-lg shadow-[var(--primary)]/20"
                    >
                      {isScanningRels ? <Loader2 size={14} className="animate-spin" /> : <ScanSearch size={14} />}
                      Scan Characters
                    </Button>
                  </div>
                  <div className="flex-1 min-h-0 bg-[var(--background)] rounded-2xl border border-[var(--border)] relative overflow-hidden">
                    <RelationshipGraph relationships={relationships} />
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center p-12">
            <div className="w-20 h-20 rounded-3xl bg-[var(--secondary)] flex items-center justify-center mb-6">
              <BookOpen size={40} className="text-[var(--muted-foreground)] opacity-30" />
            </div>
            <h2 className="text-2xl font-bold text-[var(--foreground)] mb-2">No Thread Selected</h2>
            <p className="text-[var(--muted-foreground)] max-w-sm">
              Select a series from the library on the left to manage its unique terminology and context.
            </p>
          </div>
        )}
      </main>

      {showPresetsModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          <Card className="w-full max-w-lg overflow-hidden shadow-2xl border border-[var(--border)] bg-[var(--card)] rounded-2xl flex flex-col">
            <div className="p-6 border-b border-[var(--border)] flex justify-between items-center bg-[var(--card)]">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-[var(--primary)]" />
                <h2 className="text-lg font-bold text-[var(--foreground)]">Apply Genre Preset</h2>
              </div>
              <button onClick={() => setShowPresetsModal(false)} className="p-1.5 hover:bg-[var(--secondary)] rounded-full transition-colors text-[var(--muted-foreground)]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto custom-scrollbar">
              <p className="text-xs text-[var(--muted-foreground)] mb-2">
                Select a preset to populate this thread's lorebook with common genre conventions. Preset entries are additive and will not overwrite existing terms.
              </p>
              {presets.map((preset) => (
                <div key={preset.key} className="p-4 rounded-xl border border-[var(--border)] bg-[var(--secondary)]/10 hover:border-[var(--primary)]/30 transition-all flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm text-[var(--foreground)]">{preset.name}</span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[var(--primary)]/10 text-[var(--primary)]">{preset.entry_count} terms</span>
                  </div>
                  <p className="text-xs text-[var(--muted-foreground)]">{preset.description}</p>
                  <Button
                    size="sm"
                    className="mt-2 w-full rounded-lg text-xs"
                    onClick={() => handleApplyPreset(preset.key)}
                    disabled={isApplyingPreset !== null}
                  >
                    {isApplyingPreset === preset.key ? (
                      <>
                        <Loader2 size={12} className="animate-spin mr-1.5" /> Applying...
                      </>
                    ) : 'Apply Preset'}
                  </Button>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
