import { useState, useEffect } from 'react';
import { 
  X, Plus, BookOpen, Globe, Save, FileText, Sparkles, 
  Loader2, Check, Search, Filter, MoreVertical, Trash2 
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

interface LorebookEntry {
  id: number;
  original_term: string;
  translated_term: string;
  notes?: string;
  auto_extracted?: boolean;
}

interface ThreadItem {
  id: number;
  title: string;
  author?: string;
}

interface ExtractedTerm {
  original_term: string;
  notes?: string;
}

export default function ContextLibraryPage() {
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<number | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<'glossary' | 'context'>('glossary');
  
  // Contexts
  const [globalContext, setGlobalContext] = useState('');
  const [threadContext, setThreadContext] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Glossary
  const [entries, setEntries] = useState<LorebookEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [newEntry, setNewEntry] = useState({ original: '', translated: '', notes: '' });

  // AI Extract
  const [isExtracting, setIsExtracting] = useState(false);
  const [suggestions, setSuggestions] = useState<ExtractedTerm[]>([]);

  // Initial load
  useEffect(() => {
    fetch('http://localhost:8000/api/threads')
      .then(res => res.json())
      .then(data => {
        setThreads(data);
        if (data.length > 0) setSelectedThreadId(data[0].id);
      })
      .catch(e => console.error('Failed to fetch threads', e));

    fetch('http://localhost:8000/api/global-context')
      .then(res => res.json())
      .then(data => setGlobalContext(data.global_context || ''))
      .catch(e => console.error('Failed to fetch global context', e));
  }, []);

  // Thread selection load
  useEffect(() => {
    if (!selectedThreadId) {
      setEntries([]);
      setThreadContext('');
      return;
    }
    fetch(`http://localhost:8000/api/threads/${selectedThreadId}/lorebook`)
      .then(res => res.json())
      .then(data => setEntries(data))
      .catch(e => console.error('Failed to fetch lorebook', e));

    fetch(`http://localhost:8000/api/threads/${selectedThreadId}/context`)
      .then(res => res.json())
      .then(data => setThreadContext(data.thread_context || ''))
      .catch(e => console.error('Failed to fetch thread context', e));
  }, [selectedThreadId]);

  const saveContext = async (type: 'global' | 'thread') => {
    setIsSaving(true);
    const endpoint = type === 'global' ? '/api/global-context' : `/api/threads/${selectedThreadId}/context`;
    const body = { context: type === 'global' ? globalContext : threadContext };
    
    try {
      await fetch(`http://localhost:8000${endpoint}`, {
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
      const res = await fetch(`http://localhost:8000/api/threads/${selectedThreadId}/lorebook`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_term: newEntry.original,
          translated_term: newEntry.translated,
          notes: newEntry.notes || undefined
        })
      });
      const data = await res.json();
      setEntries(prev => [...prev, data]);
      setNewEntry({ original: '', translated: '', notes: '' });
      setShowAddForm(false);
    } catch (e) {
      console.error('Failed to add entry', e);
    }
  };

  const removeEntry = async (id: number) => {
    try {
      await fetch(`http://localhost:8000/api/lorebook/${id}`, { method: 'DELETE' });
      setEntries(prev => prev.filter(e => e.id !== id));
    } catch (e) {
      console.error('Failed to remove entry', e);
    }
  };

  const handleExtractContext = async () => {
    if (!selectedThreadId) return;
    setIsExtracting(true);
    
    const lmUrl = localStorage.getItem('lm_url') || 'http://localhost:1234';
    const lmModel = localStorage.getItem('lm_model') || '';

    try {
      const res = await fetch(`http://localhost:8000/api/threads/${selectedThreadId}/extract-context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lm_url: lmUrl, model: lmModel || undefined })
      });
      const data = await res.json();
      setSuggestions(data.terms || []);
    } catch (e) {
      alert('Extraction failed.');
    } finally {
      setIsExtracting(false);
    }
  };

  const selectedThread = threads.find(t => t.id === selectedThreadId);

  const filteredEntries = entries.filter(e => 
    e.original_term.toLowerCase().includes(searchQuery.toLowerCase()) ||
    e.translated_term.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (e.notes || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-[calc(100vh-64px)] w-full overflow-hidden bg-[var(--background)]">
      {/* Internal Sidebar: Thread List */}
      <aside className="w-72 border-r border-[var(--border)] flex flex-col bg-[var(--card)]/50">
        <div className="p-6 border-b border-[var(--border)]">
          <h2 className="text-lg font-bold text-[var(--foreground)] mb-1">Context Library</h2>
          <p className="text-xs text-[var(--muted-foreground)]">Manage lore and terminology</p>
        </div>
        
        <div className="flex-1 overflow-auto py-4 px-3 space-y-1">
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

        <div className="p-4 border-t border-[var(--border)]">
          <button className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-[var(--border)] text-sm font-medium text-[var(--muted-foreground)] hover:bg-[var(--secondary)] transition-all">
            <Plus size={16} /> New Context
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {selectedThread ? (
          <>
            {/* Thread Header */}
            <header className="px-8 py-6 border-b border-[var(--border)] bg-[var(--card)]/30 backdrop-blur-sm">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h1 className="text-2xl font-bold text-[var(--foreground)] tracking-tight">
                    {selectedThread.title}
                  </h1>
                  <p className="text-sm text-[var(--muted-foreground)] mt-1">
                    Consistent translation memory for this series.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="rounded-lg gap-2"
                    onClick={handleExtractContext}
                    disabled={isExtracting}
                  >
                    {isExtracting ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} className="text-yellow-500" />}
                    AI Extract
                  </Button>
                  <Button 
                    size="sm" 
                    className="rounded-lg gap-2"
                    onClick={() => setShowAddForm(true)}
                  >
                    <Plus size={14} /> Add Term
                  </Button>
                </div>
              </div>

              {/* Sub-Tabs */}
              <div className="flex gap-8 border-b border-[var(--border)] -mb-6">
                <button 
                  onClick={() => setActiveSubTab('glossary')}
                  className={cn(
                    "pb-4 text-sm font-semibold transition-all relative",
                    activeSubTab === 'glossary' ? "text-[var(--primary)]" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  )}
                >
                  Glossary ({entries.length})
                  {activeSubTab === 'glossary' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />}
                </button>
                <button 
                  onClick={() => setActiveSubTab('context')}
                  className={cn(
                    "pb-4 text-sm font-semibold transition-all relative",
                    activeSubTab === 'context' ? "text-[var(--primary)]" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  )}
                >
                  Context & Style
                  {activeSubTab === 'context' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />}
                </button>
              </div>
            </header>

            {/* Content Tab: Glossary */}
            <div className="flex-1 overflow-auto p-8">
              {activeSubTab === 'glossary' && (
                <div className="space-y-8">
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

                  {/* Add Entry Form (Modal Style Overlay or inline) */}
                  {showAddForm && (
                    <Card className="border-[var(--primary)]/30 bg-[var(--accent)]/10 shadow-lg fade-in">
                      <CardContent className="p-6 space-y-4">
                        <div className="flex justify-between items-center mb-2">
                          <h3 className="font-bold text-sm">Add New Term</h3>
                          <button onClick={() => setShowAddForm(false)}><X size={16} /></button>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="space-y-1.5">
                            <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Original Term</label>
                            <input 
                              value={newEntry.original}
                              onChange={e => setNewEntry({...newEntry, original: e.target.value})}
                              placeholder="e.g. 仙侠" 
                              className="w-full bg-[var(--card)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Translated Term</label>
                            <input 
                              value={newEntry.translated}
                              onChange={e => setNewEntry({...newEntry, translated: e.target.value})}
                              placeholder="e.g. Xianxia" 
                              className="w-full bg-[var(--card)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
                            />
                          </div>
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Notes / Context</label>
                          <input 
                            value={newEntry.notes}
                            onChange={e => setNewEntry({...newEntry, notes: e.target.value})}
                            placeholder="e.g. Name of the protagonist's sword style." 
                            className="w-full bg-[var(--card)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm"
                          />
                        </div>
                        <div className="flex justify-end gap-3 pt-2">
                          <Button variant="ghost" size="sm" onClick={() => setShowAddForm(false)}>Cancel</Button>
                          <Button size="sm" onClick={addEntry}>Save Term</Button>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* AI Suggestions Section */}
                  {suggestions.length > 0 && (
                    <div className="space-y-4">
                      <h3 className="text-xs font-bold uppercase tracking-widest text-[var(--primary)] flex items-center gap-2">
                        <Sparkles size={14} /> AI Detected Suggestions
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {suggestions.map((sug, i) => (
                          <Card key={i} className="border-yellow-200 bg-yellow-50/30 dark:border-yellow-900/30 dark:bg-yellow-900/10">
                            <CardContent className="p-4 flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="font-bold text-sm truncate">{sug.original_term}</div>
                                <div className="text-[10px] text-[var(--muted-foreground)] mt-1 line-clamp-2">{sug.notes}</div>
                              </div>
                              <button 
                                onClick={() => {
                                  setNewEntry({ original: sug.original_term, translated: '', notes: sug.notes || '' });
                                  setShowAddForm(true);
                                }}
                                className="p-1.5 bg-yellow-100 dark:bg-yellow-900/50 rounded-lg text-yellow-700 dark:text-yellow-400 hover:scale-110 transition-transform"
                              >
                                <Check size={14} />
                              </button>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Term Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filteredEntries.map(entry => (
                      <Card key={entry.id} className="group hover:border-[var(--primary)]/50 transition-all duration-300 shadow-sm hover:shadow-md relative overflow-hidden">
                        <CardContent className="p-6">
                          <div className="flex justify-between items-start mb-4">
                            <div className="w-10 h-10 rounded-xl bg-[var(--accent)] flex items-center justify-center text-[var(--primary)] font-bold">
                              {entry.original_term.charAt(0)}
                            </div>
                            <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                              <button onClick={() => removeEntry(entry.id)} className="p-1.5 text-[var(--muted-foreground)] hover:text-red-500 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20">
                                <Trash2 size={14} />
                              </button>
                              <button className="p-1.5 text-[var(--muted-foreground)] hover:text-[var(--foreground)] rounded-lg hover:bg-[var(--secondary)]">
                                <MoreVertical size={14} />
                              </button>
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
                  </div>
                </div>
              )}

              {/* Content Tab: Context & Style */}
              {activeSubTab === 'context' && (
                <div className="space-y-8 max-w-4xl">
                  {/* Thread Context */}
                  <Card className="border-l-4 border-l-[var(--primary)] bg-[var(--card)]/50">
                    <CardContent className="p-8 space-y-6">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-[var(--accent)] flex items-center justify-center text-[var(--primary)]">
                            <FileText size={20} />
                          </div>
                          <h3 className="text-lg font-bold">Thread Context</h3>
                        </div>
                        <Button 
                          size="sm" 
                          variant={isSaving ? "outline" : "default"} 
                          onClick={() => saveContext('thread')}
                          disabled={isSaving}
                        >
                          {isSaving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                          Save Changes
                        </Button>
                      </div>
                      <p className="text-sm text-[var(--muted-foreground)]">
                        Instructions specific to <span className="font-bold text-[var(--foreground)]">"{selectedThread.title}"</span>. 
                        Define character personalities, relationship dynamics, or specific narrative rules.
                      </p>
                      <Textarea 
                        value={threadContext}
                        onChange={e => setThreadContext(e.target.value)}
                        placeholder="e.g. The protagonist is cynical and uses informal language. Their rival is extremely polite but cold."
                        className="min-h-[200px] text-base bg-[var(--background)]/50"
                      />
                    </CardContent>
                  </Card>

                  {/* Global Context */}
                  <Card className="border-l-4 border-l-[var(--muted-foreground)] bg-[var(--card)]/30 opacity-80 hover:opacity-100 transition-opacity">
                    <CardContent className="p-8 space-y-6">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-[var(--secondary)] flex items-center justify-center text-[var(--muted-foreground)]">
                            <Globe size={20} />
                          </div>
                          <h3 className="text-lg font-bold">Global System Instructions</h3>
                        </div>
                        <Button 
                          size="sm" 
                          variant="outline" 
                          onClick={() => saveContext('global')}
                          disabled={isSaving}
                        >
                          <Save size={16} /> Save Global
                        </Button>
                      </div>
                      <p className="text-sm text-[var(--muted-foreground)]">
                        Universal literary style rules applied to ALL translations.
                      </p>
                      <Textarea 
                        value={globalContext}
                        onChange={e => setGlobalContext(e.target.value)}
                        placeholder="e.g. Translate in a professional literary style. Keep all honorifics in original pinyin."
                        className="min-h-[150px] text-base bg-[var(--background)]/50"
                      />
                    </CardContent>
                  </Card>
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
    </div>
  );
}
