import { useState, useEffect, useCallback } from 'react';
import { getApiUrl } from './api';

export type EngineLoadMode = 'soft' | 'hard';

export const ENGINE_LOAD_MODE_EVENT = 'engine_load_mode_changed';

/**
 * Retrieve the current engine load mode from localStorage (checking both 'load_mode' and 'prefetch_mode').
 */
export function getStoredEngineLoadMode(): EngineLoadMode {
  if (typeof window === 'undefined') return 'soft';
  const stored = localStorage.getItem('load_mode') || localStorage.getItem('prefetch_mode');
  return stored === 'hard' ? 'hard' : 'soft';
}

/**
 * Synchronously and asynchronously persist engine load mode everywhere:
 * 1. Both localStorage keys ('load_mode' and 'prefetch_mode')
 * 2. In-memory window event for instant cross-component UI updates
 * 3. Backend database (/api/settings) so global settings follow the user's choice
 */
export async function syncEngineLoadMode(mode: EngineLoadMode): Promise<void> {
  if (typeof window === 'undefined') return;

  // 1. Update localStorage
  localStorage.setItem('load_mode', mode);
  localStorage.setItem('prefetch_mode', mode);

  // 2. Dispatch event for all mounted components
  window.dispatchEvent(new CustomEvent(ENGINE_LOAD_MODE_EVENT, { detail: mode }));
  window.dispatchEvent(new Event('storage'));

  // 3. Persist to backend server
  try {
    await fetch(getApiUrl('/api/settings'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ load_mode: mode, prefetch_mode: mode })
    });
  } catch (err) {
    console.error('Failed to sync engine load mode to server:', err);
  }
}

/**
 * React hook that binds a component to the synchronized Engine Load Mode in real time.
 */
export function useEngineLoadMode(): [EngineLoadMode, (mode: EngineLoadMode) => Promise<void>] {
  const [mode, setMode] = useState<EngineLoadMode>(getStoredEngineLoadMode);

  useEffect(() => {
    const handleModeChange = (e: Event) => {
      const customEvent = e as CustomEvent<EngineLoadMode>;
      if (customEvent.detail === 'hard' || customEvent.detail === 'soft') {
        setMode(customEvent.detail);
      } else {
        setMode(getStoredEngineLoadMode());
      }
    };

    window.addEventListener(ENGINE_LOAD_MODE_EVENT, handleModeChange);
    window.addEventListener('storage', handleModeChange);
    return () => {
      window.removeEventListener(ENGINE_LOAD_MODE_EVENT, handleModeChange);
      window.removeEventListener('storage', handleModeChange);
    };
  }, []);

  const updateMode = useCallback(async (newMode: EngineLoadMode) => {
    setMode(newMode);
    await syncEngineLoadMode(newMode);
  }, []);

  return [mode, updateMode];
}
