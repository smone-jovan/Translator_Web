import { useState, useEffect } from 'react';
import { X, Plus, BookOpen, Globe2, Save, FileText } from 'lucide-react';

interface LorebookEntry {
  id: number;
  original_term: string;
  translated_term: string;
  notes?: string;
}

interface ThreadItem {
  id: number;
  title: string;
}

export default function ContextLibraryPage() {
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [selectedThread, setSelectedThread] = useState<number | ''>('');
  
  // Contexts
  const [globalContext, setGlobalContext] = useState('');
  const [savingGlobal, setSavingGlobal] = useState(false);
  const [threadContext, setThreadContext] = useState('');
  const [savingThread, setSavingThread] = useState(false);

  // Glossary
  const [entries, setEntries] = useState<LorebookEntry[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [newOriginal, setNewOriginal] = useState('');
  const [newTranslated, setNewTranslated] = useState('');
  const [newNotes, setNewNotes] = useState('');

  // Initial load: threads & global context
  useEffect(() => {
    fetch('http://localhost:8000/api/threads')
      .then(res => res.json())
      .then(data => setThreads(data))
      .catch(e => console.error('Failed to fetch threads', e));

    fetch('http://localhost:8000/api/global-context')
      .then(res => res.json())
      .then(data => setGlobalContext(data.global_context || ''))
      .catch(e => console.error('Failed to fetch global context', e));
  }, []);

  // Thread selection load: thread context & lorebook
  useEffect(() => {
    if (!selectedThread) {
      setEntries([]);
      setThreadContext('');
      return;
    }
    fetch(`http://localhost:8000/api/threads/${selectedThread}/lorebook`)
      .then(res => res.json())
      .then(data => setEntries(data))
      .catch(e => console.error('Failed to fetch lorebook', e));

    fetch(`http://localhost:8000/api/threads/${selectedThread}/context`)
      .then(res => res.json())
      .then(data => setThreadContext(data.thread_context || ''))
      .catch(e => console.error('Failed to fetch thread context', e));
  }, [selectedThread]);

  const saveGlobalContext = async () => {
    setSavingGlobal(true);
    try {
      await fetch('http://localhost:8000/api/global-context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context: globalContext })
      });
    } catch (e) {
      console.error('Failed to save global context', e);
    } finally {
      setTimeout(() => setSavingGlobal(false), 500);
    }
  };

  const saveThreadContext = async () => {
    if (!selectedThread) return;
    setSavingThread(true);
    try {
      await fetch(`http://localhost:8000/api/threads/${selectedThread}/context`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context: threadContext })
      });
    } catch (e) {
      console.error('Failed to save thread context', e);
    } finally {
      setTimeout(() => setSavingThread(false), 500);
    }
  };

  const addEntry = async () => {
    if (!newOriginal.trim() || !newTranslated.trim() || !selectedThread) return;
    try {
      const res = await fetch(`http://localhost:8000/api/threads/${selectedThread}/lorebook`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_term: newOriginal,
          translated_term: newTranslated,
          notes: newNotes || undefined
        })
      });
      const data = await res.json();
      setEntries(prev => [...prev, data]);
      setNewOriginal('');
      setNewTranslated('');
      setNewNotes('');
      setShowForm(false);
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

  return (
    <div className="space-y-6">
      <div className="glass rounded-xl p-5">
        <div className="mb-4">
          <h2 className="text-lg font-medium flex items-center gap-2">
            <Globe2 className="w-5 h-5 text-[var(--accent)]" />
            Global Context
          </h2>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">
            Default literary settings that apply to all threads (narrative voice, style).
          </p>
        </div>
        <div className="space-y-3">
          <textarea
            value={globalContext}
            onChange={(e) => setGlobalContext(e.target.value)}
            placeholder="e.g. Translate in a formal, literary tone. Use past tense consistently."
            className="w-full bg-[var(--background)] border border-[var(--border)] rounded-lg p-3 text-sm focus:outline-none focus:border-[var(--ring)] min-h-[100px] resize-y"
          />
          <div className="flex justify-end">
            <button
              onClick={saveGlobalContext}
              className="flex items-center gap-1.5 bg-[var(--accent)] hover:bg-[var(--muted)] border border-[var(--border)] px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
            >
              <Save size={16} />
              {savingGlobal ? 'Saved!' : 'Save Global Context'}
            </button>
          </div>
        </div>
      </div>

      <div className="glass rounded-xl p-5">
        <div className="mb-5">
          <h2 className="text-lg font-medium">Thread Context & Glossary</h2>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">
            Custom settings and vocabulary overriding global defaults for specific threads.
          </p>
        </div>

        {/* Thread selector */}
        <div className="mb-6 flex items-center gap-3">
          <BookOpen size={18} className="text-[var(--muted-foreground)]" />
          <select 
            value={selectedThread}
            onChange={(e) => setSelectedThread(e.target.value ? Number(e.target.value) : '')}
            className="bg-[var(--background)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--ring)] flex-1"
          >
            <option value="">-- Select a Book / Thread --</option>
            {threads.map(t => (
              <option key={t.id} value={t.id}>{t.title}</option>
            ))}
          </select>
        </div>

        {selectedThread ? (
          <div className="space-y-6 fade-in">
            {/* Thread Context */}
            <div>
              <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
                <FileText className="w-4 h-4 text-[var(--muted-foreground)]" />
                Thread-Specific Context
              </h3>
              <textarea
                value={threadContext}
                onChange={(e) => setThreadContext(e.target.value)}
                placeholder="Custom instructions for this thread..."
                className="w-full bg-[var(--background)] border border-[var(--border)] rounded-lg p-3 text-sm focus:outline-none focus:border-[var(--ring)] min-h-[80px] resize-y"
              />
              <div className="flex justify-end mt-2">
                <button
                  onClick={saveThreadContext}
                  className="flex items-center gap-1.5 bg-[var(--secondary)] hover:bg-[var(--accent)] border border-[var(--border)] px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
                >
                  <Save size={14} />
                  {savingThread ? 'Saved!' : 'Save Thread Context'}
                </button>
              </div>
            </div>

            {/* Glossary */}
            <div>
              <div className="flex justify-between items-center mb-3">
                <h3 className="text-sm font-medium">Glossary</h3>
                <button
                  onClick={() => setShowForm(!showForm)}
                  className="flex items-center gap-1.5 bg-[var(--secondary)] hover:bg-[var(--accent)] border border-[var(--border)] text-[var(--foreground)] px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                >
                  <Plus size={14} /> Add Term
                </button>
              </div>

              {/* Add form */}
              {showForm && (
                <div className="bg-[var(--secondary)] border border-[var(--border)] rounded-lg p-4 mb-4 space-y-3 fade-in">
                  <div className="grid grid-cols-2 gap-3">
                    <input
                      value={newOriginal}
                      onChange={e => setNewOriginal(e.target.value)}
                      placeholder="Original term (e.g. 仙侠)"
                      className="bg-[var(--background)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--ring)]"
                    />
                    <input
                      value={newTranslated}
                      onChange={e => setNewTranslated(e.target.value)}
                      placeholder="Translation (e.g. Xianxia)"
                      className="bg-[var(--background)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--ring)]"
                    />
                  </div>
                  <input
                    value={newNotes}
                    onChange={e => setNewNotes(e.target.value)}
                    placeholder="Notes (optional)"
                    className="w-full bg-[var(--background)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--ring)]"
                  />
                  <div className="flex gap-2 justify-end">
                    <button
                      onClick={() => setShowForm(false)}
                      className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)] px-3 py-1.5"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={addEntry}
                      className="text-sm bg-[var(--accent)] hover:bg-[var(--muted)] border border-[var(--border)] px-4 py-1.5 rounded-lg transition-colors"
                    >
                      Save Term
                    </button>
                  </div>
                </div>
              )}

              {/* Entries list */}
              <div className="space-y-2">
                {entries.map(entry => (
                  <div
                    key={entry.id}
                    className="bg-[var(--secondary)] border border-[var(--border)] rounded-lg px-4 py-3 flex justify-between items-center group"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm text-[var(--foreground)]">{entry.original_term}</span>
                        <span className="text-[var(--muted-foreground)]">→</span>
                        <span className="text-sm text-[var(--foreground)]">{entry.translated_term}</span>
                      </div>
                      {entry.notes && (
                        <div className="text-xs text-[var(--muted-foreground)] mt-0.5">{entry.notes}</div>
                      )}
                    </div>
                    <button
                      onClick={() => removeEntry(entry.id)}
                      className="text-[var(--muted-foreground)] hover:text-[var(--destructive)] opacity-0 group-hover:opacity-100 transition-opacity ml-2"
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}

                {entries.length === 0 && (
                  <div className="text-center text-sm text-[var(--muted-foreground)] py-8 border border-dashed border-[var(--border)] rounded-lg">
                    No terms yet. Add one to keep translations consistent.
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center text-sm text-[var(--muted-foreground)] py-8 border border-dashed border-[var(--border)] rounded-lg">
            Please select a thread to view or add thread-specific context and glossary.
          </div>
        )}
      </div>
    </div>
  );
}
