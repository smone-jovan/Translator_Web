import { useState, useEffect } from 'react';
import { Wifi, WifiOff, Server, RefreshCw } from 'lucide-react';

interface ModelInfo {
  id: string;
  object: string;
}

export default function SettingsPage() {
  const [lmUrl, setLmUrl] = useState(() => localStorage.getItem('lm_url') || 'http://localhost:1234');
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem('lm_model') || '');
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [status, setStatus] = useState<'idle' | 'checking' | 'connected' | 'error'>('idle');

  // Persist
  useEffect(() => { localStorage.setItem('lm_url', lmUrl); }, [lmUrl]);
  useEffect(() => { localStorage.setItem('lm_model', selectedModel); }, [selectedModel]);

  const testConnection = async () => {
    setStatus('checking');
    setModels([]);
    try {
      const res = await fetch(`${lmUrl}/v1/models`);
      const data = await res.json();
      const list: ModelInfo[] = data.data || [];
      setModels(list);
      setStatus('connected');
      if (list.length > 0 && !selectedModel) {
        setSelectedModel(list[0].id);
      }
    } catch {
      setStatus('error');
    }
  };

  return (
    <div className="space-y-4">
      <div className="glass rounded-xl p-5">
        <h2 className="text-lg font-medium mb-1">Settings</h2>
        <p className="text-xs text-[var(--muted-foreground)] mb-5">Configure LM Studio connection.</p>

        {/* LM Studio URL */}
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1.5">LM Studio Base URL</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Server size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]" />
                <input
                  value={lmUrl}
                  onChange={e => setLmUrl(e.target.value)}
                  className="w-full bg-[var(--secondary)] border border-[var(--border)] rounded-lg pl-9 pr-4 py-2.5 text-sm focus:outline-none focus:border-[var(--ring)]"
                />
              </div>
              <button
                onClick={testConnection}
                disabled={status === 'checking'}
                className="flex items-center gap-1.5 bg-[var(--accent)] hover:bg-[var(--muted)] border border-[var(--border)] px-4 py-2.5 rounded-lg text-sm transition-colors disabled:opacity-50"
              >
                <RefreshCw size={14} className={status === 'checking' ? 'animate-spin' : ''} />
                Test
              </button>
            </div>
          </div>

          {/* Connection status */}
          {status !== 'idle' && (
            <div className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg border fade-in ${
              status === 'connected'
                ? 'bg-green-500/10 border-green-500/30 text-green-400'
                : status === 'error'
                ? 'bg-red-500/10 border-red-500/30 text-red-400'
                : 'bg-[var(--secondary)] border-[var(--border)] text-[var(--muted-foreground)]'
            }`}>
              {status === 'connected' && <><Wifi size={14} /> Connected — {models.length} model(s) found</>}
              {status === 'error' && <><WifiOff size={14} /> Cannot reach LM Studio at {lmUrl}</>}
              {status === 'checking' && <>Checking...</>}
            </div>
          )}

          {/* Model selector */}
          {models.length > 0 && (
            <div>
              <label className="block text-sm font-medium mb-1.5">Model</label>
              <select
                value={selectedModel}
                onChange={e => setSelectedModel(e.target.value)}
                className="w-full bg-[var(--secondary)] border border-[var(--border)] rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--ring)]"
              >
                {models.map(m => (
                  <option key={m.id} value={m.id}>{m.id}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {/* Backend status */}
      <div className="glass rounded-xl p-5">
        <h3 className="text-sm font-medium mb-3">Backend (FastAPI)</h3>
        <div className="text-xs text-[var(--muted-foreground)] space-y-1">
          <div>URL: <code className="text-[var(--foreground)]">http://localhost:8000</code></div>
          <div>DB: <code className="text-[var(--foreground)]">SQLite (app.db)</code></div>
          <div>Scraping: <code className="text-[var(--foreground)]">Crawl4AI</code></div>
        </div>
      </div>
    </div>
  );
}
