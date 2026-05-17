import { useState, useEffect, useCallback } from 'react';
import { 
  Wifi, WifiOff, Server, RefreshCw, Moon, Sun, 
  CheckCircle2, Languages, Eye, Layout, ShieldCheck, Database, Info, Globe
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/api';

interface ModelInfo {
  id: string;
  object: string;
}

const ThemeCard = ({ 
  id,
  label, 
  active, 
  onClick, 
  gradient, 
  textColor, 
  icon: Icon 
}: { 
  id?: string,
  label: string, 
  active: boolean, 
  onClick: () => void, 
  gradient: string, 
  textColor: string, 
  icon: React.ElementType 
}) => (
  <button
    id={id}
    onClick={onClick}
    className={cn(
      "relative flex flex-col items-center justify-center p-6 rounded-2xl border-2 transition-all duration-300 group",
      active 
        ? "border-[var(--primary)] scale-105 shadow-lg" 
        : "border-transparent hover:border-[var(--border)]"
    )}
  >
    <div 
      className="w-full aspect-video rounded-xl mb-3 flex items-center justify-center shadow-inner overflow-hidden"
      style={{ background: gradient }}
    >
      <Icon className={cn("w-8 h-8 transition-transform group-hover:scale-110")} style={{ color: textColor }} />
    </div>
    <span className="text-sm font-bold text-[var(--foreground)]">{label}</span>
    {active && (
      <div className="absolute top-2 right-2 bg-[var(--primary)] text-[var(--primary-foreground)] rounded-full p-1">
        <CheckCircle2 size={14} />
      </div>
    )}
  </button>
);

export default function SettingsPage() {
  const [lmUrl, setLmUrl] = useState(() => localStorage.getItem('lm_url') || 'http://localhost:1234');
  const [selectedModel, setSelectedModel] = useState(() => localStorage.getItem('lm_model') || '');
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [status, setStatus] = useState<'idle' | 'checking' | 'connected' | 'error'>('idle');
  const [targetLang, setTargetLang] = useState(() => localStorage.getItem('target_language') || 'Indonesian');
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'sepia');
  const [displayMode, setDisplayMode] = useState(() => localStorage.getItem('display_mode') || 'both');
  const [prefetchEnabled, setPrefetchEnabled] = useState(() => localStorage.getItem('prefetch_enabled') === '1');
  const [prefetchCount, setPrefetchCount] = useState(() => parseInt(localStorage.getItem('prefetch_count') || '2'));
  const [prefetchMode, setPrefetchMode] = useState(() => localStorage.getItem('prefetch_mode') || 'soft');
  const [maxContextTerms, setMaxContextTerms] = useState<number>(() => parseInt(localStorage.getItem('max_context_terms') || '50'));
  const [isSaving, setIsSaving] = useState(false);

  const fetchGlobalSettings = useCallback(async () => {
    try {
      const res = await fetch(getApiUrl('/api/global-context'));
      const data = await res.json();
      if (data.lm_url) {
        setLmUrl(data.lm_url);
        localStorage.setItem('lm_url', data.lm_url);
      }
      if (data.lm_model) {
        setSelectedModel(data.lm_model);
        localStorage.setItem('lm_model', data.lm_model);
      }
      if (data.target_language) {
        setTargetLang(data.target_language);
        localStorage.setItem('target_language', data.target_language);
      }
      if (data.prefetch_enabled !== undefined) {
        setPrefetchEnabled(data.prefetch_enabled === 1);
        localStorage.setItem('prefetch_enabled', data.prefetch_enabled.toString());
      }
      if (data.prefetch_count !== undefined) {
        setPrefetchCount(data.prefetch_count);
        localStorage.setItem('prefetch_count', data.prefetch_count.toString());
      }
      if (data.prefetch_mode !== undefined) {
        setPrefetchMode(data.prefetch_mode);
        localStorage.setItem('prefetch_mode', data.prefetch_mode);
      }
      if (data.max_context_terms !== undefined) {
        setMaxContextTerms(data.max_context_terms);
        localStorage.setItem('max_context_terms', data.max_context_terms.toString());
      }
    } catch {
      console.error('Failed to fetch server settings');
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchGlobalSettings();
  }, [fetchGlobalSettings]);

  const saveSettingsToServer = async (updates: Record<string, string>) => {
    setIsSaving(true);
    try {
      await fetch(getApiUrl('/api/settings'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
    } catch (e) {
      console.error('Failed to sync settings', e);
    } finally {
      setTimeout(() => setIsSaving(false), 800);
    }
  };

  // Persist
  useEffect(() => { localStorage.setItem('lm_url', lmUrl); }, [lmUrl]);
  useEffect(() => { localStorage.setItem('lm_model', selectedModel); }, [selectedModel]);
  useEffect(() => { 
    localStorage.setItem('target_language', targetLang);
    // Sync to server without showing the saving indicator to avoid render cycle warning
    const sync = async () => {
      try {
        await fetch(getApiUrl('/api/settings'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_language: targetLang })
        });
      } catch { /* silent fail */ }
    };
    // eslint-disable-next-line react-hooks/set-state-in-effect
    sync();
  }, [targetLang]);

  useEffect(() => { localStorage.setItem('display_mode', displayMode); }, [displayMode]);
  useEffect(() => { 
    localStorage.setItem('theme', theme); 
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const testConnection = async () => {
    setStatus('checking');
    try {
      const res = await fetch(`${lmUrl}/v1/models`);
      const data = await res.json();
      const list: ModelInfo[] = data.data || [];
      setModels(list);
      setStatus('connected');
      
      // Save URL to server on successful connection
      saveSettingsToServer({ lm_url: lmUrl });

      if (list.length > 0 && !selectedModel) {
        setSelectedModel(list[0].id);
        saveSettingsToServer({ lm_model: list[0].id });
      }
    } catch {
      setStatus('error');
    }
  };

  const handleModelChange = (val: string) => {
    setSelectedModel(val);
    localStorage.setItem('lm_model', val);
    saveSettingsToServer({ lm_model: val });
  };

  const handlePrefetchToggle = (enabled: boolean) => {
    setPrefetchEnabled(enabled);
    localStorage.setItem('prefetch_enabled', enabled ? '1' : '0');
    saveSettingsToServer({ prefetch_enabled: enabled ? '1' : '0' });
  };

  const handlePrefetchCountChange = (count: number) => {
    setPrefetchCount(count);
    localStorage.setItem('prefetch_count', count.toString());
    saveSettingsToServer({ prefetch_count: count.toString() });
  };

  const handlePrefetchModeChange = (mode: string) => {
    setPrefetchMode(mode);
    localStorage.setItem('prefetch_mode', mode);
    saveSettingsToServer({ prefetch_mode: mode });
  };

  const handleMaxContextTermsChange = (count: number) => {
    setMaxContextTerms(count);
    localStorage.setItem('max_context_terms', count.toString());
    saveSettingsToServer({ max_context_terms: count.toString() });
  };

  return (
    <div className="max-w-4xl mx-auto py-8 space-y-12 pb-20">
      {/* Header */}
      <header>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-4xl font-bold text-[var(--foreground)] tracking-tight">Settings</h1>
            <p className="text-[var(--muted-foreground)] text-lg">Personalize your translation environment.</p>
          </div>
          {isSaving && (
            <div className="flex items-center gap-2 text-[var(--primary)] text-sm font-bold bg-[var(--primary)]/10 px-4 py-2 rounded-full animate-pulse">
              <RefreshCw size={14} className="animate-spin" />
              Syncing to server...
            </div>
          )}
        </div>
      </header>

      {/* Section: Connection */}
      <section className="space-y-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center text-[var(--primary)]">
            <Server size={18} />
          </div>
          <h2 className="text-xl font-bold">Local AI Connection</h2>
        </div>
        
        <Card>
          <CardContent className="p-8 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <div className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">LM Studio Base URL</label>
                  <div className="flex gap-2">
                    <input 
                      value={lmUrl}
                      onChange={e => setLmUrl(e.target.value)}
                      className="flex-1 bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--primary)] transition-all"
                    />
                    <Button 
                      variant="outline" 
                      onClick={testConnection}
                      className="rounded-xl"
                      disabled={status === 'checking'}
                    >
                      <RefreshCw size={16} className={status === 'checking' ? 'animate-spin' : ''} />
                    </Button>
                  </div>
                </div>

                {status !== 'idle' && (
                  <div className={cn(
                    "flex items-center gap-3 px-4 py-3 rounded-xl border text-sm transition-all animate-in fade-in slide-in-from-top-1",
                    status === 'connected' ? "bg-green-500/10 border-green-500/30 text-green-700 dark:text-green-400" :
                    status === 'error' ? "bg-red-500/10 border-red-500/30 text-red-700 dark:text-red-400" :
                    "bg-[var(--secondary)] border-[var(--border)] text-[var(--muted-foreground)]"
                  )}>
                    {status === 'connected' ? <Wifi size={18} /> : <WifiOff size={18} />}
                    <span>
                      {status === 'connected' ? `Connected: ${models.length} models available` : 
                       status === 'error' ? 'Connection failed. Ensure LM Studio is running.' : 'Checking connection...'}
                    </span>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">Active Model</label>
                  <select
                    value={selectedModel}
                    onChange={e => handleModelChange(e.target.value)}
                    className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--primary)] transition-all appearance-none"
                  >
                    <option value="">No model selected</option>
                    {models.map(m => (
                      <option key={m.id} value={m.id}>{m.id}</option>
                    ))}
                  </select>
                </div>
                <p className="text-[10px] text-[var(--muted-foreground)] leading-relaxed italic">
                  Tip: Use models optimized for creative writing (like Llama-3 or Mistral) for better literary translations.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Section: Preferences */}
      <section className="space-y-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center text-[var(--primary)]">
            <Languages size={18} />
          </div>
          <h2 className="text-xl font-bold">Translation Preferences</h2>
        </div>

        <Card>
          <CardContent className="p-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
              <div className="flex items-start gap-5">
                <div className="w-12 h-12 rounded-2xl bg-[var(--secondary)] flex items-center justify-center shrink-0">
                  <Globe className="text-[var(--muted-foreground)]" size={24} />
                </div>
                <div className="space-y-3 flex-1">
                  <div>
                    <h3 className="font-bold">Target Language</h3>
                    <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Translate all content into this language.</p>
                  </div>
                  <div className="flex gap-2">
                    {['Indonesian', 'English'].map(lang => (
                      <button
                        key={lang}
                        onClick={() => setTargetLang(lang)}
                        className={cn(
                          "flex-1 py-2 px-4 rounded-xl text-xs font-bold transition-all border",
                          targetLang === lang 
                            ? "bg-[var(--primary)] text-[var(--primary-foreground)] border-[var(--primary)] shadow-md"
                            : "bg-[var(--card)] text-[var(--muted-foreground)] border-[var(--border)] hover:border-[var(--primary)]"
                        )}
                      >
                        {lang}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex items-start gap-5">
                <div className="w-12 h-12 rounded-2xl bg-[var(--secondary)] flex items-center justify-center shrink-0">
                  <Eye className="text-[var(--muted-foreground)]" size={24} />
                </div>
                <div className="space-y-3 flex-1">
                  <div>
                    <h3 className="font-bold">Reader Display</h3>
                    <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Default view for new translations.</p>
                  </div>
                  <select
                    value={displayMode}
                    onChange={e => setDisplayMode(e.target.value)}
                    className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2 text-sm focus:outline-none"
                  >
                    <option value="both">Side-by-side (Original & Translated)</option>
                    <option value="translated">Translated Only</option>
                    <option value="original">Original Only</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Glossary Limit Slider / Selector */}
            <div className="pt-8 mt-8 border-t border-[var(--border)] space-y-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
                <div>
                  <h3 className="font-bold flex items-center gap-2 text-[var(--foreground)]">
                    <Database size={16} className="text-[var(--primary)]" />
                    Max Context Terms Limit
                  </h3>
                  <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                    Maximum number of active glossary terms kept per thread. Excess items are archived and compressed to save tokens.
                  </p>
                </div>
                <div className="flex items-center gap-1.5 px-3 py-1 bg-[var(--primary)]/10 text-[var(--primary)] rounded-xl text-xs font-bold border border-[var(--primary)]/20 shadow-sm shrink-0 self-start md:self-auto">
                  <span>Active Limit: {maxContextTerms} terms</span>
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-2">
                {[20, 50, 70, 100, 150].map((limit) => {
                  const tokenEstimates: Record<number, string> = {
                    20: "~500 tokens",
                    50: "~1,250 tokens",
                    70: "~1,750 tokens",
                    100: "~2,500 tokens",
                    150: "~3,750 tokens"
                  };
                  const active = maxContextTerms === limit;
                  return (
                    <button
                      key={limit}
                      onClick={() => handleMaxContextTermsChange(limit)}
                      className={cn(
                        "relative flex flex-col items-center justify-center p-4 rounded-xl border transition-all duration-300 group hover:scale-[1.02]",
                        active
                          ? "border-[var(--primary)] bg-[var(--primary)]/5 shadow-md"
                          : "border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted-foreground)]"
                      )}
                    >
                      <span className={cn(
                        "text-lg font-black transition-colors",
                        active ? "text-[var(--primary)]" : "text-[var(--foreground)]"
                      )}>
                        {limit}
                      </span>
                      <span className="text-[10px] text-[var(--muted-foreground)] mt-1 font-semibold group-hover:text-[var(--foreground)]">
                        {tokenEstimates[limit]}
                      </span>
                      {active && (
                        <div className="absolute -top-1.5 -right-1.5 bg-[var(--primary)] text-[var(--primary-foreground)] rounded-full p-0.5 shadow-sm">
                          <CheckCircle2 size={12} />
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Section: Advanced Prefetch */}
      <section className="space-y-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center text-[var(--primary)]">
            <RefreshCw size={18} />
          </div>
          <h2 className="text-xl font-bold">Advanced Prefetch</h2>
        </div>

        <Card>
          <CardContent className="p-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-bold">Enable Prefetching</h3>
                    <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Automatically translate next chapters in background.</p>
                  </div>
                  <button
                    onClick={() => handlePrefetchToggle(!prefetchEnabled)}
                    className={cn(
                      "relative inline-flex h-6 w-11 items-center rounded-full transition-colors",
                      prefetchEnabled ? "bg-[var(--primary)]" : "bg-[var(--secondary)]"
                    )}
                  >
                    <span
                      className={cn(
                        "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                        prefetchEnabled ? "translate-x-6" : "translate-x-1"
                      )}
                    />
                  </button>
                </div>
                <p className="text-[10px] text-[var(--muted-foreground)] leading-relaxed italic">
                  Note: Prefetching helps reduce waiting time between chapters but consumes more tokens/server resources.
                </p>
                
                <div className="pt-4 border-t border-[var(--border)]">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold">Prefetch Mode</h3>
                  </div>
                  <div className="flex bg-[var(--secondary)] rounded-xl p-1">
                    <button
                      onClick={() => handlePrefetchModeChange('soft')}
                      className={cn(
                        "flex-1 py-1.5 text-[10px] font-bold rounded-lg transition-all",
                        prefetchMode === 'soft' 
                          ? "bg-[var(--card)] text-[var(--primary)] shadow-sm" 
                          : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                      )}
                    >
                      SOFT LOAD
                    </button>
                    <button
                      onClick={() => handlePrefetchModeChange('hard')}
                      className={cn(
                        "flex-1 py-1.5 text-[10px] font-bold rounded-lg transition-all",
                        prefetchMode === 'hard' 
                          ? "bg-[var(--card)] text-orange-500 shadow-sm" 
                          : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                      )}
                    >
                      HARD LOAD
                    </button>
                  </div>
                  <p className="text-[9px] text-[var(--muted-foreground)] mt-2 px-1">
                    {prefetchMode === 'soft' 
                      ? "Sequential: Translates next chapter one-by-one (Safe & Efficient)." 
                      : "Aggressive: Translates entire range in parallel (Fast & Resource Intensive)."}
                  </p>
                </div>
              </div>

              <div className={cn("space-y-4 transition-opacity", !prefetchEnabled && "opacity-50 pointer-events-none")}>
                <div className="flex items-center justify-between">
                  <h3 className="font-bold">Prefetch Range</h3>
                  <span className="text-[var(--primary)] font-bold px-3 py-1 bg-[var(--primary)]/10 rounded-lg">{prefetchCount} Chapters</span>
                </div>
                <input
                  type="range"
                  min="1"
                  max="5"
                  step="1"
                  value={prefetchCount}
                  onChange={(e) => handlePrefetchCountChange(parseInt(e.target.value))}
                  className="w-full h-2 bg-[var(--secondary)] rounded-lg appearance-none cursor-pointer accent-[var(--primary)]"
                />
                <div className="flex justify-between text-[10px] text-[var(--muted-foreground)] font-medium px-1">
                  <span>1 Ch</span>
                  <span>2 Ch</span>
                  <span>3 Ch</span>
                  <span>4 Ch</span>
                  <span>5 Ch</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Section: Appearance */}
      <section className="space-y-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center text-[var(--primary)]">
            <Layout size={18} />
          </div>
          <h2 className="text-xl font-bold">Appearance</h2>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6">
          <ThemeCard 
            id="white" label="White" active={theme === 'white'} 
            onClick={() => setTheme('white')} gradient="linear-gradient(135deg, #ffffff, #e2e8f0)" 
            textColor="#0f172a" icon={Sun} 
          />
          <ThemeCard 
            id="sepia" label="Sepia" active={theme === 'sepia'} 
            onClick={() => setTheme('sepia')} gradient="linear-gradient(135deg, #fdf6e3, #d4c2aa)" 
            textColor="#5c4a3d" icon={Sun} 
          />
          <ThemeCard 
            id="omni" label="Omni" active={theme === 'omni'} 
            onClick={() => setTheme('omni')} gradient="linear-gradient(135deg, #1e4591, #0f2b60)" 
            textColor="#e0e7ff" icon={Moon} 
          />
          <ThemeCard 
            id="black" label="Black" active={theme === 'black'} 
            onClick={() => setTheme('black')} gradient="linear-gradient(135deg, #1e293b, #0f172a)" 
            textColor="#fff" icon={Moon} 
          />
          <ThemeCard 
            id="oled" label="OLED" active={theme === 'oled'} 
            onClick={() => setTheme('oled')} gradient="linear-gradient(135deg, #0a0a0a, #000000)" 
            textColor="#fff" icon={Moon} 
          />
        </div>
      </section>

      {/* Section: System Info */}
      <section className="space-y-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center text-[var(--primary)]">
            <Info size={18} />
          </div>
          <h2 className="text-xl font-bold">System Information</h2>
        </div>

        <Card className="bg-[var(--secondary)]/30">
          <CardContent className="p-8">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="flex items-center gap-4">
                <ShieldCheck className="text-[var(--primary)]" size={32} />
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">Version</h4>
                  <p className="font-bold">v1.2.0 (Premium)</p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <Database className="text-[var(--primary)]" size={32} />
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">Database</h4>
                  <p className="font-bold">Local SQLite (app.db)</p>
                </div>
              </div>
              <div className="flex items-center gap-4 text-[var(--muted-foreground)]">
                <Server size={32} className="opacity-50" />
                <div>
                  <h4 className="text-xs font-bold uppercase tracking-widest">Backend</h4>
                  <p className="font-bold">Python FastAPI</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
