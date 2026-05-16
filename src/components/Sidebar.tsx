import { BookOpen, Languages, Library, Settings, X } from 'lucide-react';
import type { ReactNode } from 'react';

export type TabId = 'translate' | 'library' | 'context' | 'settings';

interface NavItem {
  id: TabId;
  icon: ReactNode;
  label: string;
}

export const navItems: NavItem[] = [
  { id: 'translate', icon: <Languages size={20} />, label: 'Translate' },
  { id: 'library', icon: <Library size={20} />, label: 'Library' },
  { id: 'context', icon: <BookOpen size={20} />, label: 'Context' },
  { id: 'settings', icon: <Settings size={20} />, label: 'Settings' },
];

interface SidebarProps {
  isOpen: boolean;
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  onClose: () => void;
}

export default function Sidebar({ isOpen, activeTab, onTabChange, onClose }: SidebarProps) {
  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden backdrop-blur-sm"
          onClick={onClose}
        />
      )}

      <aside className={`
        fixed md:static inset-y-0 left-0 z-50 w-64 glass border-r border-white/10
        transform transition-transform duration-300 ease-in-out flex flex-col
        ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}>
        {/* Brand */}
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded bg-[var(--accent)] flex items-center justify-center font-bold text-[var(--foreground)]">
              翻
            </div>
            <span className="font-semibold text-lg tracking-wide">
              Trans<span className="text-[var(--muted-foreground)]">lator</span>
            </span>
          </div>
          <button className="md:hidden" onClick={onClose}>
            <X size={20} className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => { onTabChange(item.id); onClose(); }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-sm ${
                activeTab === item.id
                  ? 'bg-[var(--accent)] text-[var(--foreground)] border border-[var(--border)]'
                  : 'text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]'
              }`}
            >
              {item.icon}
              <span className="font-medium">{item.label}</span>
            </button>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-white/10 text-xs text-[var(--muted-foreground)]">
          Self-hosted · LM Studio
        </div>
      </aside>
    </>
  );
}
