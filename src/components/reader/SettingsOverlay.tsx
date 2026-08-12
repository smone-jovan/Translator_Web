import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { getApiUrl } from '@/lib/api';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

interface SettingsOverlayProps {
  fontSize: number;
  setFontSize: (size: number) => void;
  displayMode: string;
  setDisplayMode: (mode: string) => void;
  prefetchEnabled: boolean;
  setPrefetchEnabled: (enabled: boolean) => void;
  prefetchCount: number;
  setPrefetchCount: (count: number) => void;
  prefetchMode: string;
  setPrefetchMode: (mode: string) => void;
  alwaysHideThoughts: boolean;
  setAlwaysHideThoughts: (val: boolean) => void;
  onClose: () => void;
  mobileMode?: boolean;
  threadId?: number;
}

export default function SettingsOverlay({
  fontSize,
  setFontSize,
  displayMode,
  setDisplayMode,
  prefetchEnabled,
  setPrefetchEnabled,
  prefetchCount,
  setPrefetchCount,
  prefetchMode,
  setPrefetchMode,
  alwaysHideThoughts,
  setAlwaysHideThoughts,
  onClose,
  mobileMode = false,
  threadId,
}: SettingsOverlayProps) {
  const [styleGuide, setStyleGuide] = useState('');
  const [isSavingGuide, setIsSavingGuide] = useState(false);

  useEffect(() => {
    if (threadId) {
      fetch(getApiUrl(`/api/threads/${threadId}`))
        .then(res => res.json())
        .then(data => setStyleGuide(data.style_guide || ''))
        .catch(() => {});
    }
  }, [threadId]);

  const saveStyleGuide = async () => {
    if (!threadId) return;
    setIsSavingGuide(true);
    try {
      await fetch(getApiUrl(`/api/threads/${threadId}/style-guide`), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ style_guide: styleGuide || null })
      });
      toast.success('Style guide saved');
    } catch {
      toast.error('Failed to save style guide');
    } finally {
      setIsSavingGuide(false);
    }
  };

  const saveSetting = async (key: string, value: string | number) => {
    try {
      await fetch(getApiUrl('/api/settings'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value })
      });
    } catch (err) {
      console.error(`Failed to save setting ${key}`, err);
    }
  };

  return (
    <div className={cn(
      "z-50",
      mobileMode
        ? "fixed inset-0 flex items-end bg-black/40 backdrop-blur-[2px] animate-in fade-in duration-200"
        : "absolute top-20 right-4 w-72 animate-in fade-in slide-in-from-top-4 duration-300"
    )}>
      {mobileMode && (
        <button
          type="button"
          aria-label="Close settings"
          className="absolute inset-0 border-none bg-transparent"
          onClick={onClose}
        />
      )}
      <Card className={cn(
        "shadow-2xl border-[var(--border)] bg-[var(--card)] backdrop-blur-xl relative",
        mobileMode
          ? "w-full rounded-t-3xl rounded-b-none border-b-0 max-h-[85vh] overflow-y-auto animate-in slide-in-from-bottom-8 duration-300"
          : ""
      )}>
        <CardContent className="p-6 space-y-6">
          {mobileMode && (
            <div className="flex flex-col items-center gap-3">
              <div className="h-1.5 w-14 rounded-full bg-[var(--border)]" />
              <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-[var(--muted-foreground)]">
                Reader Settings
              </div>
            </div>
          )}
          <div>
            <label className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">Font Size</label>
            <div className="flex flex-col gap-2 mt-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono text-[var(--muted-foreground)]">12px</span>
                <span className="text-sm font-bold text-[var(--accent)]">{fontSize}px</span>
                <span className="text-[10px] font-mono text-[var(--muted-foreground)]">32px</span>
              </div>
              <input 
                type="range" 
                min="12" 
                max="32" 
                value={fontSize} 
                onChange={(e) => setFontSize(parseInt(e.target.value, 10))}
                className="w-full h-1.5 bg-[var(--secondary)] rounded-lg appearance-none cursor-pointer accent-[var(--accent)]"
              />
            </div>
          </div>
          
          <div>
            <label className="text-xs font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">Layout Mode</label>
            <div className="grid grid-cols-3 gap-2 mt-3">
              {['original', 'translated', 'both'].map((mode) => (
                <Button 
                  key={mode}
                  variant={displayMode === mode ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setDisplayMode(mode);
                    localStorage.setItem('display_mode', mode);
                    saveSetting('display_mode', mode);
                  }}
                  className="text-[10px] capitalize h-8"
                >
                  {mode}
                </Button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]">
            <div className="space-y-0.5">
              <label className="text-xs font-semibold text-[var(--foreground)]">Hide AI Thoughts</label>
              <p className="text-[10px] text-[var(--muted-foreground)]">Hide model reasoning process (<code className="text-[9px] bg-black/10 dark:bg-white/10 px-1 py-0.5 rounded">{"<think>"}</code> blocks)</p>
            </div>
            <Button 
              variant={alwaysHideThoughts ? "default" : "outline"} 
              size="sm" 
              className={cn(
                "h-7 px-3 rounded-full text-[10px]",
                alwaysHideThoughts ? "bg-amber-600 hover:bg-amber-700 text-white border-amber-600" : ""
              )}
              onClick={async () => {
                const newVal = !alwaysHideThoughts;
                setAlwaysHideThoughts(newVal);
                saveSetting('always_hide_thoughts', newVal ? 1 : 0);
              }}
            >
              {alwaysHideThoughts ? 'HIDE' : 'SHOW'}
            </Button>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]">
            <div className="space-y-0.5">
              <label className="text-xs font-semibold text-[var(--foreground)]">Auto-Prefetch</label>
              <p className="text-[10px] text-[var(--muted-foreground)]">Translate next chapter in background</p>
            </div>
            <Button 
              variant={prefetchEnabled ? "default" : "outline"} 
              size="sm" 
              className={cn(
                "h-7 px-3 rounded-full text-[10px]",
                prefetchEnabled ? "bg-green-600 hover:bg-green-700 text-white" : ""
              )}
              onClick={async () => {
                const newVal = !prefetchEnabled;
                setPrefetchEnabled(newVal);
                saveSetting('prefetch_enabled', newVal ? 1 : 0);
              }}
            >
              {prefetchEnabled ? 'ON' : 'OFF'}
            </Button>
          </div>

          {prefetchEnabled && (
            <div className="pt-2 border-t border-[var(--border)] animate-in fade-in slide-in-from-top-2">
              <div className="flex items-center justify-between mb-2">
                <label className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider">Prefetch Range</label>
                <span className="text-[10px] font-bold text-[var(--primary)] bg-[var(--primary)]/10 px-2 py-0.5 rounded-md">{prefetchCount} Ch</span>
              </div>
              <input 
                type="range" 
                min="1" 
                max="5" 
                value={prefetchCount} 
                onChange={async (e) => {
                  const val = parseInt(e.target.value, 10);
                  setPrefetchCount(val);
                  saveSetting('prefetch_count', val);
                }}
                className="w-full h-1.5 bg-[var(--secondary)] rounded-lg appearance-none cursor-pointer accent-[var(--primary)]"
              />
              <div className="flex justify-between text-[9px] text-[var(--muted-foreground)] mt-1 px-1">
                <span>1</span>
                <span>2</span>
                <span>3</span>
                <span>4</span>
                <span>5</span>
              </div>

              <div className="mt-4 pt-3 border-t border-[var(--border)]">
                <label className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider block mb-2">Prefetch Mode</label>
                <div className="flex bg-[var(--secondary)] rounded-xl p-1">
                  <button
                    onClick={async () => {
                      setPrefetchMode('soft');
                      saveSetting('prefetch_mode', 'soft');
                    }}
                    className={cn(
                      "flex-1 py-1.5 text-[9px] font-bold rounded-lg transition-all border-none bg-transparent cursor-pointer",
                      prefetchMode === 'soft' ? "bg-[var(--card)] text-[var(--primary)] shadow-sm" : "text-[var(--muted-foreground)]"
                    )}
                  >
                    SOFT
                  </button>
                  <button
                    onClick={async () => {
                      setPrefetchMode('hard');
                      saveSetting('prefetch_mode', 'hard');
                    }}
                    className={cn(
                      "flex-1 py-1.5 text-[9px] font-bold rounded-lg transition-all border-none bg-transparent cursor-pointer",
                      prefetchMode === 'hard' ? "bg-[var(--card)] text-orange-500 shadow-sm" : "text-[var(--muted-foreground)]"
                    )}
                  >
                    HARD
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Style Guide (per-thread) */}
          {threadId && (
            <div className="mt-4 pt-3 border-t border-[var(--border)]">
              <label className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-wider block mb-2">
                Style Guide (Quality Mode)
              </label>
              <p className="text-[10px] text-[var(--muted-foreground)] mb-2">
                Define translation style, tone, and rules for this novel. Injected into prompts in Quality mode.
              </p>
              <Textarea
                value={styleGuide}
                onChange={(e) => setStyleGuide(e.target.value)}
                placeholder="e.g., Use formal Indonesian for narration, casual for dialogue. Keep cultivation terms in pinyin. Translate system notifications in ALL CAPS."
                className="min-h-[100px] text-xs bg-[var(--secondary)] border-[var(--border)] resize-none"
              />
              <Button
                size="sm"
                className="w-full text-xs h-8 mt-2 bg-[var(--primary)] text-[var(--primary-foreground)]"
                onClick={saveStyleGuide}
                disabled={isSavingGuide}
              >
                {isSavingGuide ? 'Saving...' : 'Save Style Guide'}
              </Button>
            </div>
          )}

          <Button variant="ghost" size="sm" className="w-full text-xs h-8 mt-2" onClick={onClose}>Close</Button>
        </CardContent>
      </Card>
    </div>
  );
}
