import { useState } from 'react';
import { cn } from '@/lib/utils';

interface ApiKeyManagerProps {
  label: string;
  keys: string[];
  activeIndex: number;
  onAdd: (key: string) => void;
  onRemove: (index: number) => void;
  onSetActive: (index: number) => void;
}

export default function ApiKeyManager({ label, keys, activeIndex, onAdd, onRemove, onSetActive }: ApiKeyManagerProps) {
  const [newKey, setNewKey] = useState('');

  const handleAdd = () => {
    if (!newKey.trim()) return;
    onAdd(newKey.trim());
    setNewKey('');
  };

  return (
    <div className="space-y-2 pt-2 border-t border-[var(--border)]">
      <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)]">
        {label} ({keys.length})
      </label>

      {keys.length > 0 && (
        <div className="space-y-1.5">
          {keys.map((key, i) => (
            <div key={i} className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg border text-xs",
              i === activeIndex
                ? "border-[var(--primary)] bg-[var(--primary)]/10"
                : "border-[var(--border)] bg-[var(--secondary)]"
            )}>
              <button
                onClick={() => onSetActive(i)}
                className={cn(
                  "w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0",
                  i === activeIndex
                    ? "border-[var(--primary)] bg-[var(--primary)]"
                    : "border-[var(--border)]"
                )}
              >
                {i === activeIndex && <div className="w-2 h-2 rounded-full bg-white" />}
              </button>
              <span className="flex-1 font-mono truncate">
                {key.substring(0, 8)}...{key.substring(key.length - 4)}
              </span>
              <span className="text-[10px] text-[var(--muted-foreground)]">Key {i + 1}</span>
              <button
                onClick={() => onRemove(i)}
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
          value={newKey}
          onChange={e => setNewKey(e.target.value)}
          placeholder="Tambah key baru..."
          className="flex-1 bg-[var(--background)] border border-[var(--border)] rounded-lg px-3 py-2 text-xs focus:outline-none focus:border-[var(--primary)]"
          onKeyDown={e => e.key === 'Enter' && handleAdd()}
        />
        <button
          onClick={handleAdd}
          disabled={!newKey.trim()}
          className="px-3 py-2 bg-[var(--primary)] text-[var(--primary-foreground)] rounded-lg text-xs font-bold disabled:opacity-50"
        >
          + Add
        </button>
      </div>
    </div>
  );
}
