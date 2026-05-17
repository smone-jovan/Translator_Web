import { BookOpen, Languages, Library, Settings, Globe, User, Star } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export type TabId = 'translate' | 'library' | 'context' | 'settings';

interface NavItem {
  id: TabId;
  icon: ReactNode;
  label: string;
}

export const navItems: NavItem[] = [
  { id: 'translate', icon: <Languages size={24} />, label: 'Translate' },
  { id: 'library', icon: <Library size={24} />, label: 'Library' },
  { id: 'context', icon: <BookOpen size={24} />, label: 'Context' },
  { id: 'settings', icon: <Settings size={24} />, label: 'Settings' },
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
          className="fixed inset-0 bg-black/20 z-40 md:hidden backdrop-blur-sm"
          onClick={onClose}
        />
      )}

      <aside className={cn(
        "fixed md:static inset-y-0 left-0 z-50 w-20 bg-[var(--card)] border-r border-[var(--border)] flex flex-col items-center py-8 transition-transform duration-300 ease-in-out shadow-sm",
        isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
      )}>
        {/* Brand/Logo */}
        <div className="mb-12">
          <div className="w-10 h-10 rounded-xl bg-[var(--primary)] flex items-center justify-center text-[var(--primary-foreground)] font-bold text-xl shadow-lg shadow-[var(--primary)]/20">
            翻
          </div>
        </div>

        {/* Main Nav */}
        <nav className="flex-1 space-y-6 w-full px-2">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => { onTabChange(item.id); onClose(); }}
              className={cn(
                "w-full flex flex-col items-center gap-1 p-3 rounded-xl transition-all duration-200 group relative",
                activeTab === item.id
                  ? "bg-[var(--accent)] text-[var(--primary)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)]"
              )}
              title={item.label}
            >
              <div className={cn(
                "transition-transform group-hover:scale-110",
                activeTab === item.id && "scale-110"
              )}>
                {item.icon}
              </div>
              
              {/* Tooltip (CSS only for simplicity) */}
              <div className="absolute left-full ml-4 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all whitespace-nowrap z-50">
                {item.label}
              </div>
            </button>
          ))}
        </nav>

        {/* Bottom Section */}
        <div className="mt-auto space-y-6 w-full px-2">
           <button className="w-full flex flex-col items-center p-3 text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors group">
            <Globe size={22} />
          </button>
          <button className="w-full flex flex-col items-center p-3 text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors group">
            <Star size={22} />
          </button>
          <div className="w-10 h-10 rounded-full bg-[var(--muted)] border border-[var(--border)] flex items-center justify-center mx-auto cursor-pointer hover:border-[var(--primary)] transition-all">
            <User size={20} className="text-[var(--muted-foreground)]" />
          </div>
        </div>
      </aside>
    </>
  );
}
