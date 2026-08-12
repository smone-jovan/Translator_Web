/* eslint-disable react-refresh/only-export-components */
import { BookOpen, Languages, Library, Settings, User, Star, X } from 'lucide-react';
import { type ReactNode, useState, useRef } from 'react';
import { cn } from '@/lib/utils';
import { getApiUrl } from '@/lib/api';

export type TabId = 'translate' | 'library' | 'context' | 'settings' | 'bookmarks';

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
  isOpen?: boolean;
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  onClose: () => void;
}

export default function Sidebar({ activeTab, onTabChange, onClose }: SidebarProps) {
  const [showPinModal, setShowPinModal] = useState(false);
  const [pinInput, setPinInput] = useState('');
  const [pinError, setPinError] = useState(false);
  const pressTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const startPress = () => {
    pressTimer.current = setTimeout(() => {
      setShowPinModal(true);
    }, 10000); // 10 seconds
  };

  const endPress = () => {
    if (pressTimer.current) {
      clearTimeout(pressTimer.current);
      pressTimer.current = null;
    }
  };

  const handlePinSubmit = async () => {
    try {
      const res = await fetch(getApiUrl('/api/system/workspace'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace: 'toggle', pin: pinInput })
      });
      if (!res.ok) {
        setPinError(true);
        setPinInput('');
        return;
      }
      window.location.reload();
    } catch (e) {
      console.error(e);
      setPinError(true);
    }
  };

  return (
    <>
      <aside className="hidden md:flex shrink-0 fixed top-0 left-0 h-screen h-[100dvh] z-50 w-20 bg-[var(--card)] border-r border-[var(--border)] flex-col items-center py-6 shadow-sm overflow-y-auto select-none">
        {/* Brand/Logo */}
        <div className="mb-8">
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
          <button 
             onClick={() => { onTabChange('bookmarks'); onClose(); }}
             title="Favorite Chapters"
             className={cn(
               "w-full flex flex-col items-center p-3 transition-colors group relative rounded-xl",
               activeTab === 'bookmarks'
                 ? "bg-yellow-500/10 text-yellow-500"
                 : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-yellow-500"
             )}
           >
            <Star size={22} className={activeTab === 'bookmarks' ? 'scale-110' : 'group-hover:scale-110 transition-transform'} />
            <div className="absolute left-full ml-4 px-2 py-1 bg-gray-900 text-white text-xs rounded opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all whitespace-nowrap z-50">
              Bookmarks
            </div>
          </button>
          <div 
            className="w-10 h-10 rounded-full bg-[var(--muted)] border border-[var(--border)] flex items-center justify-center mx-auto cursor-pointer hover:border-[var(--primary)] transition-all"
            onMouseDown={startPress}
            onMouseUp={endPress}
            onMouseLeave={endPress}
            onTouchStart={startPress}
            onTouchEnd={endPress}
          >
            <User size={20} className="text-[var(--muted-foreground)]" />
          </div>
        </div>
      </aside>

      {/* PIN Modal */}
      {showPinModal && (
        <div className="fixed inset-0 z-[100] bg-black/50 backdrop-blur-sm flex items-center justify-center">
          <div className="bg-[var(--card)] w-full max-w-sm p-6 rounded-2xl shadow-xl border border-[var(--border)] relative">
            <button 
              onClick={() => { setShowPinModal(false); setPinInput(''); setPinError(false); }}
              className="absolute top-4 right-4 text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            >
              <X size={20} />
            </button>
            <h2 className="text-xl font-bold mb-4">Enter PIN</h2>
            <input
              type="password"
              value={pinInput}
              onChange={(e) => { setPinInput(e.target.value); setPinError(false); }}
              onKeyDown={(e) => { if(e.key === 'Enter') handlePinSubmit(); }}
              className={cn(
                "w-full bg-[var(--background)] border p-3 rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] transition-all",
                pinError ? "border-red-500 text-red-500" : "border-[var(--border)]"
              )}
              placeholder="•••••"
              autoFocus
            />
            {pinError && <p className="text-red-500 text-sm mt-2">Invalid PIN</p>}
            <button
              onClick={handlePinSubmit}
              className="mt-4 w-full bg-[var(--primary)] text-[var(--primary-foreground)] p-3 rounded-xl font-medium hover:opacity-90 transition-opacity"
            >
              Submit
            </button>
          </div>
        </div>
      )}
    </>
  );
}
