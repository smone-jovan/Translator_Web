import { useState, useEffect, useCallback, type ElementType } from 'react';
import { 
  Wifi, WifiOff, Server, RefreshCw, Moon, Sun, 
  CheckCircle2, Languages, Eye, EyeOff, Layout, ShieldCheck, Database, Info, Globe, Sparkles
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/api';

const POPULAR_OPENAI_MODELS = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1-mini'];

// Text-out models only, with free tier info (RPD > 0 = free available)
const GEMINI_MODELS = [
  { id: 'gemini-3.1-flash-lite', free: true, rpm: 15, rpd: 500 },
  { id: 'gemini-2.5-flash-lite', free: true, rpm: 10, rpd: 20 },
  { id: 'gemini-2.5-flash', free: true, rpm: 5, rpd: 20 },
  { id: 'gemini-3-flash', free: true, rpm: 5, rpd: 20 },
  { id: 'gemini-3.5-flash', free: true, rpm: 5, rpd: 20 },
  { id: 'gemma-4-31b', free: true, rpm: 15, rpd: 1500 },
  { id: 'gemma-4-26b', free: true, rpm: 15, rpd: 1500 },
  { id: 'gemini-2.5-pro', free: false, rpm: 0, rpd: 0 },
  { id: 'gemini-3.1-pro', free: false, rpm: 0, rpd: 0 },
];

const POPULAR_GEMINI_MODELS = GEMINI_MODELS.map(m => m.id);
const CHAPTER_TOKEN_CAP_OPTIONS = [7000, 15000, 22000, 30000] as const;

interface ModelInfo {
  id: string;
  object: string;
}

type LlmProvider = 'lm_studio' | 'openai' | 'gemini';

function isLlmProvider(value: string | null): value is LlmProvider {
  return value === 'lm_studio' || value === 'openai' || value === 'gemini';
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
  icon: ElementType 
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

const ProviderCard = ({
  id,
  label,
  description,
  active,
  onClick,
  icon: Icon
}: {
  id: string,
  label: string,
  description: string,
  active: boolean,
  onClick: () => void,
  icon: ElementType
}) => (
  <button
    id={`provider-${id}`}
    onClick={onClick}
    className={cn(
      "relative flex flex-col items-start p-5 rounded-2xl border-2 text-left transition-all duration-300 group w-full",
      active 
        ? "border-[var(--primary)] bg-[var(--primary)]/5 shadow-md scale-[1.01]" 
        : "border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted-foreground)]"
    )}
  >
    <div className="flex items-center gap-3 mb-2">
      <div className={cn(
        "w-10 h-10 rounded-xl flex items-center justify-center transition-all",
        active ? "bg-[var(--primary)] text-[var(--primary-foreground)]" : "bg-[var(--secondary)] text-[var(--muted-foreground)]"
      )}>
        <Icon size={20} className="group-hover:scale-110 transition-transform" />
      </div>
      <div>
        <span className="font-extrabold text-[var(--foreground)] text-sm">{label}</span>
      </div>
    </div>
    <p className="text-[11px] text-[var(--muted-foreground)] leading-relaxed">{description}</p>
    {active && (
      <div className="absolute top-3 right-3 bg-[var(--primary)] text-[var(--primary-foreground)] rounded-full p-0.5 shadow-sm">
        <CheckCircle2 size={12} />
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
  const [polishMode, setPolishMode] = useState(() => localStorage.getItem('polish_mode') || 'soft');
  const [polishSoftLimit, setPolishSoftLimit] = useState(() => parseInt(localStorage.getItem('polish_soft_limit') || '100'));
  const [maxContextTerms, setMaxContextTerms] = useState<number>(() => parseInt(localStorage.getItem('max_context_terms') || '150'));
  const [chapterTokenCapEnabled, setChapterTokenCapEnabled] = useState(() => localStorage.getItem('chapter_token_cap_enabled') !== '0');
  const [chapterTokenCap, setChapterTokenCap] = useState<number>(() => parseInt(localStorage.getItem('chapter_token_cap') || '22000'));
  const [translationMode, setTranslationMode] = useState<'quality' | 'fast'>(() => (localStorage.getItem('translation_mode') as 'quality' | 'fast') || 'quality');
  const [isSaving, setIsSaving] = useState(false);

  // Cloud & swappable LLM states (ADR-029)
  const [llmProvider, setLlmProvider] = useState<LlmProvider>(() => {
    const saved = localStorage.getItem('llm_provider');
    return isLlmProvider(saved) ? saved : 'lm_studio';
  });
  const [openaiUrl, setOpenaiUrl] = useState(() => localStorage.getItem('openai_url') || 'https://api.openai.com/v1');
  const [openaiModel, setOpenaiModel] = useState(() => localStorage.getItem('openai_model') || 'gpt-4o');
  const [geminiModel, setGeminiModel] = useState(() => localStorage.getItem('gemini_model') || 'gemini-2.5-flash');
  const [openaiApiKey, setOpenaiApiKey] = useState(() => localStorage.getItem('openai_api_key') || '');
  const [geminiApiKey, setGeminiApiKey] = useState(() => localStorage.getItem('gemini_api_key') || '');
  
  // Multiple API keys
  const [geminiApiKeys, setGeminiApiKeys] = useState<string[]>([]);
  const [geminiActiveKeyIndex, setGeminiActiveKeyIndex] = useState(0);
  const [openaiApiKeys, setOpenaiApiKeys] = useState<string[]>([]);
  const [openaiActiveKeyIndex, setOpenaiActiveKeyIndex] = useState(0);
  const [newGeminiKey, setNewGeminiKey] = useState('');
  const [newOpenaiKey, setNewOpenaiKey] = useState('');
  
  // UI password toggles
  const [showOpenaiKey, setShowOpenaiKey] = useState(false);
  const [showGeminiKey, setShowGeminiKey] = useState(false);

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
      if (data.llm_provider) {
        setLlmProvider(data.llm_provider);
        localStorage.setItem('llm_provider', data.llm_provider);
      }
      if (data.openai_url) {
        setOpenaiUrl(data.openai_url);
        localStorage.setItem('openai_url', data.openai_url);
      }
      if (data.openai_model) {
        setOpenaiModel(data.openai_model);
        localStorage.setItem('openai_model', data.openai_model);
      }
      if (data.gemini_model) {
        setGeminiModel(data.gemini_model);
        localStorage.setItem('gemini_model', data.gemini_model);
      }
      if (data.openai_api_key !== undefined) {
        setOpenaiApiKey(data.openai_api_key);
        localStorage.setItem('openai_api_key', data.openai_api_key);
      }
      if (data.gemini_api_key !== undefined) {
        setGeminiApiKey(data.gemini_api_key);
        localStorage.setItem('gemini_api_key', data.gemini_api_key);
      }
      // Multiple API keys
      if (data.gemini_api_keys) {
        setGeminiApiKeys(data.gemini_api_keys);
      }
      if (data.gemini_active_key_index !== undefined) {
        setGeminiActiveKeyIndex(data.gemini_active_key_index);
      }
      if (data.openai_api_keys) {
        setOpenaiApiKeys(data.openai_api_keys);
      }
      if (data.openai_active_key_index !== undefined) {
        setOpenaiActiveKeyIndex(data.openai_active_key_index);
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
      if (data.polish_mode !== undefined) {
        setPolishMode(data.polish_mode);
        localStorage.setItem('polish_mode', data.polish_mode);
      }
      if (data.polish_soft_limit !== undefined) {
        setPolishSoftLimit(data.polish_soft_limit);
        localStorage.setItem('polish_soft_limit', data.polish_soft_limit.toString());
      }
      if (data.max_context_terms !== undefined) {
        setMaxContextTerms(data.max_context_terms);
        localStorage.setItem('max_context_terms', data.max_context_terms.toString());
      }
      if (data.chapter_token_cap_enabled !== undefined) {
        setChapterTokenCapEnabled(data.chapter_token_cap_enabled === 1);
        localStorage.setItem('chapter_token_cap_enabled', data.chapter_token_cap_enabled.toString());
      }
      if (data.chapter_token_cap !== undefined) {
        setChapterTokenCap(data.chapter_token_cap);
        localStorage.setItem('chapter_token_cap', data.chapter_token_cap.toString());
      }
      if (data.translation_mode) {
        setTranslationMode(data.translation_mode);
        localStorage.setItem('translation_mode', data.translation_mode);
      }
    } catch {
      console.error('Failed to fetch server settings');
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchGlobalSettings();
  }, [fetchGlobalSettings]);

  const saveSettingsToServer = async (updates: Record<string, string | number | string[]>) => {
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

  // Multiple key management helpers
  const addGeminiKey = () => {
    if (!newGeminiKey.trim()) return;
    const updated = [...geminiApiKeys, newGeminiKey.trim()];
    setGeminiApiKeys(updated);
    setNewGeminiKey('');
    saveSettingsToServer({ gemini_api_keys: updated });
  };
  const removeGeminiKey = (index: number) => {
    const updated = geminiApiKeys.filter((_, i) => i !== index);
    setGeminiApiKeys(updated);
    const newIndex = geminiActiveKeyIndex >= updated.length ? Math.max(0, updated.length - 1) : geminiActiveKeyIndex;
    setGeminiActiveKeyIndex(newIndex);
    saveSettingsToServer({ gemini_api_keys: updated, gemini_active_key_index: newIndex });
  };
  const setActiveGeminiKey = (index: number) => {
    setGeminiActiveKeyIndex(index);
    saveSettingsToServer({ gemini_active_key_index: index });
  };

  const addOpenaiKey = () => {
    if (!newOpenaiKey.trim()) return;
    const updated = [...openaiApiKeys, newOpenaiKey.trim()];
    setOpenaiApiKeys(updated);
    setNewOpenaiKey('');
    saveSettingsToServer({ openai_api_keys: updated });
  };
  const removeOpenaiKey = (index: number) => {
    const updated = openaiApiKeys.filter((_, i) => i !== index);
    setOpenaiApiKeys(updated);
    const newIndex = openaiActiveKeyIndex >= updated.length ? Math.max(0, updated.length - 1) : openaiActiveKeyIndex;
    setOpenaiActiveKeyIndex(newIndex);
    saveSettingsToServer({ openai_api_keys: updated, openai_active_key_index: newIndex });
  };
  const setActiveOpenaiKey = (index: number) => {
    setOpenaiActiveKeyIndex(index);
    saveSettingsToServer({ openai_active_key_index: index });
  };

  // Persist local states
  useEffect(() => { localStorage.setItem('lm_url', lmUrl); }, [lmUrl]);
  useEffect(() => { localStorage.setItem('lm_model', selectedModel); }, [selectedModel]);
  useEffect(() => { localStorage.setItem('llm_provider', llmProvider); }, [llmProvider]);
  useEffect(() => { localStorage.setItem('openai_url', openaiUrl); }, [openaiUrl]);
  useEffect(() => { localStorage.setItem('openai_model', openaiModel); }, [openaiModel]);
  useEffect(() => { localStorage.setItem('gemini_model', geminiModel); }, [geminiModel]);
  useEffect(() => { localStorage.setItem('openai_api_key', openaiApiKey); }, [openaiApiKey]);
  useEffect(() => { localStorage.setItem('gemini_api_key', geminiApiKey); }, [geminiApiKey]);

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

  const handleLlmProviderChange = (provider: 'lm_studio' | 'openai' | 'gemini') => {
    setLlmProvider(provider);
    localStorage.setItem('llm_provider', provider);
    saveSettingsToServer({ llm_provider: provider });
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

  const handlePolishModeChange = (mode: string) => {
    setPolishMode(mode);
    localStorage.setItem('polish_mode', mode);
    saveSettingsToServer({ polish_mode: mode });
  };

  const handlePolishSoftLimitChange = (limit: number) => {
    setPolishSoftLimit(limit);
    localStorage.setItem('polish_soft_limit', limit.toString());
    saveSettingsToServer({ polish_soft_limit: limit.toString() });
  };

  const handleMaxContextTermsChange = (count: number) => {
    setMaxContextTerms(count);
    localStorage.setItem('max_context_terms', count.toString());
    saveSettingsToServer({ max_context_terms: count.toString() });
  };

  const handleChapterTokenCapToggle = (enabled: boolean) => {
    setChapterTokenCapEnabled(enabled);
    localStorage.setItem('chapter_token_cap_enabled', enabled ? '1' : '0');
    saveSettingsToServer({ chapter_token_cap_enabled: enabled ? 1 : 0 });
  };

  const handleChapterTokenCapChange = (cap: number) => {
    setChapterTokenCap(cap);
    localStorage.setItem('chapter_token_cap', cap.toString());
    saveSettingsToServer({ chapter_token_cap: cap });
  };

  const handleTranslationModeChange = (mode: 'quality' | 'fast') => {
    setTranslationMode(mode);
    localStorage.setItem('translation_mode', mode);
    saveSettingsToServer({ translation_mode: mode });
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
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center text-[var(--primary)] animate-pulse">
            <Sparkles size={18} />
          </div>
          <h2 className="text-xl font-bold">AI Translation Model</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <ProviderCard
            id="lm_studio"
            label="LM Studio (Local)"
            description="Terjemahan offline gratis menggunakan model LLM lokal Anda di komputer."
            active={llmProvider === 'lm_studio'}
            onClick={() => handleLlmProviderChange('lm_studio')}
            icon={Server}
          />
          <ProviderCard
            id="openai"
            label="OpenAI (Cloud)"
            description="Akses cloud berbayar ke OpenAI API (GPT-4o, GPT-4o-mini)."
            active={llmProvider === 'openai'}
            onClick={() => handleLlmProviderChange('openai')}
            icon={Sparkles}
          />
          <ProviderCard
            id="gemini"
            label="Google Gemini"
            description="Akses Gemini API berkecepatan sangat tinggi & gratis/premium dengan konteks raksasa."
            active={llmProvider === 'gemini'}
            onClick={() => handleLlmProviderChange('gemini')}
            icon={Globe}
          />
        </div>
        
        <Card className="overflow-hidden border border-[var(--border)] transition-all duration-300">
          <CardContent className="p-8 space-y-6">
            <div className="rounded-2xl border border-[var(--primary)]/20 bg-[var(--primary)]/5 px-4 py-3">
              <div className="flex items-start gap-3">
                <ShieldCheck size={18} className="text-[var(--primary)] mt-0.5 shrink-0" />
                <div className="space-y-1">
                  <div className="text-sm font-bold text-[var(--foreground)]">Chapter Safety Cap</div>
                  <p className="text-[11px] leading-relaxed text-[var(--muted-foreground)]">
                    Single-chapter translation now uses configurable safety cap presets. Default is <span className="font-bold text-[var(--foreground)]">22K max tokens</span> to reduce long-output hallucination and context drift.
                  </p>
                </div>
              </div>
            </div>

            {llmProvider === 'lm_studio' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 animate-in slide-in-from-bottom-2 duration-300">
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
                    Tip: Gunakan model yang dioptimasi untuk penulisan kreatif (seperti Llama-3 atau Mistral) untuk terjemahan sastra yang lebih indah.
                  </p>
                </div>
              </div>
            )}

            {llmProvider === 'openai' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 animate-in slide-in-from-bottom-2 duration-300">
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">OpenAI Custom API Base URL</label>
                    <input 
                      value={openaiUrl}
                      onChange={e => {
                        setOpenaiUrl(e.target.value);
                        saveSettingsToServer({ openai_url: e.target.value });
                      }}
                      placeholder="https://api.openai.com/v1"
                      className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--primary)] transition-all"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">OpenAI API Key</label>
                    <div className="relative">
                      <input 
                        type={showOpenaiKey ? "text" : "password"}
                        value={openaiApiKey}
                        onChange={e => {
                          setOpenaiApiKey(e.target.value);
                          saveSettingsToServer({ openai_api_key: e.target.value });
                        }}
                        placeholder="sk-..."
                        className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl pl-4 pr-10 py-2.5 text-sm focus:outline-none focus:border-[var(--primary)] transition-all"
                      />
                      <button 
                        type="button"
                        onClick={() => setShowOpenaiKey(!showOpenaiKey)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                      >
                        {showOpenaiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>

                  {/* Multiple OpenAI Keys */}
                  <div className="space-y-2 pt-2 border-t border-[var(--border)]">
                    <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">
                      Multiple Keys ({openaiApiKeys.length})
                    </label>
                    
                    {openaiApiKeys.length > 0 && (
                      <div className="space-y-1.5">
                        {openaiApiKeys.map((key, i) => (
                          <div key={i} className={cn(
                            "flex items-center gap-2 px-3 py-2 rounded-lg border text-xs",
                            i === openaiActiveKeyIndex
                              ? "border-[var(--primary)] bg-[var(--primary)]/10"
                              : "border-[var(--border)] bg-[var(--secondary)]"
                          )}>
                            <button
                              onClick={() => setActiveOpenaiKey(i)}
                              className={cn(
                                "w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0",
                                i === openaiActiveKeyIndex
                                  ? "border-[var(--primary)] bg-[var(--primary)]"
                                  : "border-[var(--border)]"
                              )}
                            >
                              {i === openaiActiveKeyIndex && <div className="w-2 h-2 rounded-full bg-white" />}
                            </button>
                            <span className="flex-1 font-mono truncate">
                              {key.substring(0, 8)}...{key.substring(key.length - 4)}
                            </span>
                            <span className="text-[10px] text-[var(--muted-foreground)]">Key {i + 1}</span>
                            <button
                              onClick={() => removeOpenaiKey(i)}
                              className="text-red-400 hover:text-red-300 ml-1"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="flex gap-2">
                      <input
                        type="password"
                        value={newOpenaiKey}
                        onChange={e => setNewOpenaiKey(e.target.value)}
                        placeholder="Tambah key baru..."
                        className="flex-1 bg-[var(--background)] border border-[var(--border)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-[var(--primary)]"
                        onKeyDown={e => e.key === 'Enter' && addOpenaiKey()}
                      />
                      <button
                        onClick={addOpenaiKey}
                        disabled={!newOpenaiKey.trim()}
                        className="px-3 py-2 bg-[var(--primary)] text-[var(--primary-foreground)] rounded-lg text-xs font-bold disabled:opacity-50"
                      >
                        + Add
                      </button>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">OpenAI Model</label>
                    <select
                      value={POPULAR_OPENAI_MODELS.includes(openaiModel) ? openaiModel : "custom"}
                      onChange={e => {
                        const val = e.target.value;
                        if (val !== "custom") {
                          setOpenaiModel(val);
                          saveSettingsToServer({ openai_model: val });
                        }
                      }}
                      className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--primary)] transition-all"
                    >
                      {POPULAR_OPENAI_MODELS.map(m => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                      <option value="custom">Custom (Type below)...</option>
                    </select>
                  </div>

                  {(!POPULAR_OPENAI_MODELS.includes(openaiModel) || !openaiModel) && (
                    <div className="space-y-1.5 animate-in fade-in duration-200">
                      <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">Custom Model Name</label>
                      <input 
                        value={openaiModel}
                        onChange={e => {
                          setOpenaiModel(e.target.value);
                          saveSettingsToServer({ openai_model: e.target.value });
                        }}
                        placeholder="gpt-4o"
                        className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--primary)] transition-all"
                      />
                    </div>
                  )}

                  <p className="text-[10px] text-[var(--muted-foreground)] leading-relaxed italic">
                    OpenAI API memerlukan saldo aktif. Model `gpt-4o-mini` sangat disukai karena berbiaya rendah dan sangat handal.
                  </p>
                </div>
              </div>
            )}

            {llmProvider === 'gemini' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 animate-in slide-in-from-bottom-2 duration-300">
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">Gemini API Key</label>
                    <div className="relative">
                      <input 
                        type={showGeminiKey ? "text" : "password"}
                        value={geminiApiKey}
                        onChange={e => {
                          setGeminiApiKey(e.target.value);
                          saveSettingsToServer({ gemini_api_key: e.target.value });
                        }}
                        placeholder="AIzaSy..."
                        className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl pl-4 pr-10 py-2.5 text-sm focus:outline-none focus:border-[var(--primary)] transition-all"
                      />
                      <button 
                        type="button"
                        onClick={() => setShowGeminiKey(!showGeminiKey)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                      >
                        {showGeminiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                      </button>
                    </div>
                  </div>
                  
                  <div className="bg-[var(--secondary)] border border-[var(--border)] rounded-xl p-4 text-xs space-y-1.5 text-[var(--muted-foreground)] leading-relaxed">
                    <p className="font-semibold text-[var(--foreground)]">💡 Ingin Menggunakan Secara Gratis?</p>
                    <p>Google Gemini API menyediakan Tier Gratis di Google AI Studio dengan limit yang sangat melimpah untuk penggunaan personal!</p>
                    <a 
                      href="https://aistudio.google.com/" 
                      target="_blank" 
                      rel="noreferrer" 
                      className="inline-block text-[var(--primary)] hover:underline font-bold mt-1"
                    >
                      Dapatkan API Key Gratis di Google AI Studio &rarr;
                    </a>
                  </div>

                  {/* Multiple Gemini Keys */}
                  <div className="space-y-2 pt-2 border-t border-[var(--border)]">
                    <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">
                      Multiple Keys ({geminiApiKeys.length})
                    </label>
                    <p className="text-[10px] text-[var(--muted-foreground)]">
                      Tambah beberapa key. Saat key utama kena rate limit, switch ke key berikutnya.
                    </p>
                    
                    {geminiApiKeys.length > 0 && (
                      <div className="space-y-1.5">
                        {geminiApiKeys.map((key, i) => (
                          <div key={i} className={cn(
                            "flex items-center gap-2 px-3 py-2 rounded-lg border text-xs",
                            i === geminiActiveKeyIndex
                              ? "border-[var(--primary)] bg-[var(--primary)]/10"
                              : "border-[var(--border)] bg-[var(--secondary)]"
                          )}>
                            <button
                              onClick={() => setActiveGeminiKey(i)}
                              className={cn(
                                "w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0",
                                i === geminiActiveKeyIndex
                                  ? "border-[var(--primary)] bg-[var(--primary)]"
                                  : "border-[var(--border)]"
                              )}
                            >
                              {i === geminiActiveKeyIndex && <div className="w-2 h-2 rounded-full bg-white" />}
                            </button>
                            <span className="flex-1 font-mono truncate">
                              {key.substring(0, 8)}...{key.substring(key.length - 4)}
                            </span>
                            <span className="text-[10px] text-[var(--muted-foreground)]">Key {i + 1}</span>
                            <button
                              onClick={() => removeGeminiKey(i)}
                              className="text-red-400 hover:text-red-300 ml-1"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="flex gap-2">
                      <input
                        type="password"
                        value={newGeminiKey}
                        onChange={e => setNewGeminiKey(e.target.value)}
                        placeholder="Tambah key baru..."
                        className="flex-1 bg-[var(--background)] border border-[var(--border)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-[var(--primary)]"
                        onKeyDown={e => e.key === 'Enter' && addGeminiKey()}
                      />
                      <button
                        onClick={addGeminiKey}
                        disabled={!newGeminiKey.trim()}
                        className="px-3 py-2 bg-[var(--primary)] text-[var(--primary-foreground)] rounded-lg text-xs font-bold disabled:opacity-50"
                      >
                        + Add
                      </button>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">Gemini Model (Text-out only)</label>
                    <select
                      value={POPULAR_GEMINI_MODELS.includes(geminiModel) ? geminiModel : "custom"}
                      onChange={e => {
                        const val = e.target.value;
                        if (val !== "custom") {
                          setGeminiModel(val);
                          saveSettingsToServer({ gemini_model: val });
                        }
                      }}
                      className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--primary)] transition-all"
                    >
                      {GEMINI_MODELS.map(m => (
                        <option key={m.id} value={m.id}>
                          {m.id} {m.free ? '(free)' : ''} [{m.rpm} RPM]
                        </option>
                      ))}
                      <option value="custom">Custom (Type below)...</option>
                    </select>
                  </div>

                  {(!POPULAR_GEMINI_MODELS.includes(geminiModel) || !geminiModel) && (
                    <div className="space-y-1.5 animate-in fade-in duration-200">
                      <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">Custom Model Name</label>
                      <input 
                        value={geminiModel}
                        onChange={e => {
                          setGeminiModel(e.target.value);
                          saveSettingsToServer({ gemini_model: e.target.value });
                        }}
                        placeholder="gemini-2.5-flash"
                        className="w-full bg-[var(--background)] border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-[var(--primary)] transition-all"
                      />
                    </div>
                  )}

                  <p className="text-[10px] text-[var(--muted-foreground)] leading-relaxed italic">
                    Rekomendasi: `gemini-3.1-flash-lite` (free, 15 RPM, 500 RPD) untuk batch. `gemini-2.5-flash` untuk kualitas lebih tinggi.
                  </p>
                </div>
              </div>
            )}
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

            {/* Translation Quality Mode */}
            <div className="pt-8 mt-8 border-t border-[var(--border)] space-y-4">
              <div className="flex flex-col gap-4 pb-8 border-b border-[var(--border)]">
                <div>
                  <h3 className="font-bold flex items-center gap-2 text-[var(--foreground)]">
                    <Sparkles size={16} className="text-[var(--primary)]" />
                    Default Translation Quality
                  </h3>
                  <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                    Quality mode uses full glossary (30 terms), style guide injection, and higher token caps. Fast mode uses minimal glossary (10 terms) and 10K token cap for local LLMs.
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => handleTranslationModeChange('quality')}
                    className={cn(
                      "relative flex flex-col items-center justify-center p-5 rounded-xl border-2 transition-all duration-300 group hover:scale-[1.02]",
                      translationMode === 'quality'
                        ? "border-purple-500 bg-purple-500/10 shadow-md"
                        : "border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted-foreground)]"
                    )}
                  >
                    <Sparkles size={20} className={translationMode === 'quality' ? "text-purple-500" : "text-[var(--muted-foreground)]"} />
                    <span className={cn(
                      "text-sm font-black mt-2 transition-colors",
                      translationMode === 'quality' ? "text-purple-500" : "text-[var(--foreground)]"
                    )}>
                      Quality
                    </span>
                    <span className="text-[10px] text-[var(--muted-foreground)] mt-1 text-center">
                      Full context, style guide, 30 glossary terms
                    </span>
                    {translationMode === 'quality' && (
                      <div className="absolute -top-1.5 -right-1.5 bg-purple-500 text-white rounded-full p-0.5 shadow-sm">
                        <CheckCircle2 size={12} />
                      </div>
                    )}
                  </button>

                  <button
                    onClick={() => handleTranslationModeChange('fast')}
                    className={cn(
                      "relative flex flex-col items-center justify-center p-5 rounded-xl border-2 transition-all duration-300 group hover:scale-[1.02]",
                      translationMode === 'fast'
                        ? "border-orange-500 bg-orange-500/10 shadow-md"
                        : "border-[var(--border)] bg-[var(--card)] hover:border-[var(--muted-foreground)]"
                    )}
                  >
                    <Wifi size={20} className={translationMode === 'fast' ? "text-orange-500" : "text-[var(--muted-foreground)]"} />
                    <span className={cn(
                      "text-sm font-black mt-2 transition-colors",
                      translationMode === 'fast' ? "text-orange-500" : "text-[var(--foreground)]"
                    )}>
                      Fast
                    </span>
                    <span className="text-[10px] text-[var(--muted-foreground)] mt-1 text-center">
                      Minimal context, 10K cap, best for LM Studio
                    </span>
                    {translationMode === 'fast' && (
                      <div className="absolute -top-1.5 -right-1.5 bg-orange-500 text-white rounded-full p-0.5 shadow-sm">
                        <CheckCircle2 size={12} />
                      </div>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {/* Glossary Limit Slider / Selector */}
            <div className="pt-8 mt-8 border-t border-[var(--border)] space-y-4">
              <div className="flex flex-col gap-4 pb-8 border-b border-[var(--border)]">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h3 className="font-bold flex items-center gap-2 text-[var(--foreground)]">
                      <ShieldCheck size={16} className="text-[var(--primary)]" />
                      Chapter Token Safety Cap
                    </h3>
                    <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                      Prevents hallucination drift and wasted tokens on long chapter translations.
                    </p>
                    <p className="text-[10px] text-[var(--muted-foreground)] mt-1">
                      Turning this off may increase hallucination and burn more tokens away.
                    </p>
                  </div>
                  <button
                    onClick={() => handleChapterTokenCapToggle(!chapterTokenCapEnabled)}
                    className={cn(
                      "relative inline-flex h-6 w-11 items-center rounded-full transition-colors shrink-0 mt-1",
                      chapterTokenCapEnabled ? "bg-[var(--primary)]" : "bg-[var(--secondary)]"
                    )}
                  >
                    <span
                      className={cn(
                        "inline-block h-4 w-4 transform rounded-full bg-white transition-transform",
                        chapterTokenCapEnabled ? "translate-x-6" : "translate-x-1"
                      )}
                    />
                  </button>
                </div>

                <div className={cn("grid grid-cols-2 sm:grid-cols-4 gap-3", !chapterTokenCapEnabled && "opacity-50 pointer-events-none")}>
                  {CHAPTER_TOKEN_CAP_OPTIONS.map((cap) => {
                    const active = chapterTokenCap === cap;
                    return (
                      <button
                        key={cap}
                        onClick={() => handleChapterTokenCapChange(cap)}
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
                          {cap / 1000}K
                        </span>
                        <span className="text-[10px] text-[var(--muted-foreground)] mt-1 font-semibold group-hover:text-[var(--foreground)]">
                          per chapter
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

              <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-8 gap-3 pt-2">
                {[20, 50, 100, 200, 300, 500, 750, 1000].map((limit) => {
                  const tokenEstimates: Record<number, string> = {
                    20: "~0.5k tokens",
                    50: "~1.2k tokens",
                    100: "~2.5k tokens",
                    200: "~5.0k tokens",
                    300: "~7.5k tokens",
                    500: "~12k tokens",
                    750: "~18k tokens",
                    1000: "~25k tokens",
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

      {/* Section: Infinite Title Polish */}
      <section className="space-y-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center text-[var(--primary)]">
            <Sparkles size={18} />
          </div>
          <h2 className="text-xl font-bold">Infinite Title Polish</h2>
        </div>

        <Card>
          <CardContent className="p-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
              <div className="space-y-4">
                <div>
                  <h3 className="font-bold">Title Polish Mode</h3>
                  <p className="text-xs text-[var(--muted-foreground)] mt-0.5">Configure how chapters are loaded and polished with AI.</p>
                </div>
                
                <div className="flex bg-[var(--secondary)] rounded-xl p-1 mt-2">
                  <button
                    onClick={() => handlePolishModeChange('soft')}
                    className={cn(
                      "flex-1 py-1.5 text-[10px] font-bold rounded-lg transition-all",
                      polishMode === 'soft' 
                        ? "bg-[var(--card)] text-[var(--primary)] shadow-sm" 
                        : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                    )}
                  >
                    SOFT LOAD
                  </button>
                  <button
                    onClick={() => handlePolishModeChange('hard')}
                    className={cn(
                      "flex-1 py-1.5 text-[10px] font-bold rounded-lg transition-all",
                      polishMode === 'hard' 
                        ? "bg-[var(--card)] text-orange-500 shadow-sm" 
                        : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                    )}
                  >
                    HARD LOAD
                  </button>
                </div>
                <p className="text-[9px] text-[var(--muted-foreground)] leading-relaxed mt-2 px-1">
                  {polishMode === 'soft' 
                    ? "Safe Mode: Only processes the specified limit of chapters from the current reading progress." 
                    : "Aggressive Mode: Processes and polishes all chapter titles in the thread regardless of count."}
                </p>
                <p className="text-[9px] text-[var(--muted-foreground)] leading-relaxed italic border-t border-[var(--border)] pt-3 mt-3">
                  💡 Dynamic Actions: When triggered, the system also automatically translates the novel synopsis/description (if it is still in Mandarin) and extracts/beautifies the clean core Chinese title as per ADR-020.
                </p>
              </div>

              <div className={cn("space-y-4 transition-opacity", polishMode === 'hard' && "opacity-50 pointer-events-none")}>
                <div className="flex items-center justify-between">
                  <h3 className="font-bold">Polish Limit (Soft Load)</h3>
                  <span className="text-[var(--primary)] font-bold px-3 py-1 bg-[var(--primary)]/10 rounded-lg">{polishSoftLimit} Titles</span>
                </div>
                <input
                  type="range"
                  min="50"
                  max="150"
                  step="10"
                  value={polishSoftLimit}
                  onChange={(e) => handlePolishSoftLimitChange(parseInt(e.target.value))}
                  className="w-full h-2 bg-[var(--secondary)] rounded-lg appearance-none cursor-pointer accent-[var(--primary)]"
                />
                <div className="flex justify-between text-[10px] text-[var(--muted-foreground)] font-medium px-1">
                  <span>50 Titles</span>
                  <span>100 Titles</span>
                  <span>150 Titles</span>
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
