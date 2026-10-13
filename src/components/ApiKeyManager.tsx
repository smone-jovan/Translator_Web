import { useState } from 'react';
import { X, Plus, Key as KeyIcon } from 'lucide-react';
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
    <div className="space-y-2.5 pt-2.5 border-t border-[var(--border)]">
      <label className="text-xs font-bold uppercase tracking-widest text-[var(--muted-foreground)] flex items-center gap-1.5">
        <KeyIcon size={12} className="text-[var(--primary)]" />
        {label} ({keys.length})
      </label>

      {keys.length > 0 && (
        <div className="space-y-1.5">
          {keys.map((key, i) => (
            <div key={i} className={cn(
              "flex items-center gap-2.5 px-3 py-2 rounded-xl border text-xs transition-all",
              i === activeIndex
                ? "border-[var(--primary)] bg-[var(--primary)]/10 shadow-sm"
                : "border-[var(--border)] bg-[var(--secondary)]/60"
            )}>
              <button
                type="button"
                onClick={() => onSetActive(i)}
                className={cn(
                  "w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 cursor-pointer",
                  i === activeIndex
                    ? "border-[var(--primary)] bg-[var(--primary)]"
                    : "border-[var(--border)] bg-background"
                )}
                title="Pilih key ini sebagai aktif"
              >
                {i === activeIndex && <div className="w-2 h-2 rounded-full bg-white" />}
              </button>
              <span className="flex-1 font-mono truncate text-[11px]">
                {key.substring(0, 8)}...{key.substring(key.length - 4)}
              </span>
              <span className="text-[10px] font-semibold text-[var(--muted-foreground)] px-1.5 py-0.5 rounded bg-background/50 border border-[var(--border)]/40">
                Key {i + 1}
              </span>
              <button
                type="button"
                onClick={() => onRemove(i)}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-red-400 hover:text-red-300 hover:bg-red-500/10 active:scale-95 transition-all cursor-pointer shrink-0"
                title="Hapus API key"
              >
                <X size={14} />
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
          placeholder="Tambah API key baru..."
          className="flex-1 bg-[var(--background)] border border-[var(--border)] rounded-xl px-3.5 py-2 text-xs focus:outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)]"
          onKeyDown={e => e.key === 'Enter' && handleAdd()}
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={!newKey.trim()}
          className="px-4 py-2 bg-[var(--primary)] text-[var(--primary-foreground)] rounded-xl text-xs font-bold disabled:opacity-50 flex items-center gap-1 cursor-pointer active:scale-95 transition-all shrink-0"
        >
          <Plus size={14} />
          Add
        </button>
      </div>
    </div>
  );
}
