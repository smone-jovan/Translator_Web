import { cn } from '@/lib/utils';
import { navItems, type TabId } from './Sidebar';
import { Star } from 'lucide-react';

interface BottomNavProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  visible?: boolean;
}

export default function BottomNav({ activeTab, onTabChange, visible = true }: BottomNavProps) {
  return (
    <div 
      className={cn(
        "fixed bottom-0 left-0 right-0 z-50 md:hidden px-4 pb-4 pt-2 transition-all duration-300 ease-in-out pointer-events-none flex justify-center",
        visible ? "translate-y-0 opacity-100" : "translate-y-28 opacity-0"
      )}
    >
      <div className="pointer-events-auto w-full max-w-lg bg-[var(--card)]/85 backdrop-blur-xl border border-[var(--border)] rounded-2xl shadow-2xl flex items-center justify-around p-2">
        {[...navItems, { id: 'bookmarks' as TabId, icon: <Star size={24} />, label: 'Favs' }].map((item) => (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id)}
            className={cn(
              "flex flex-col items-center gap-1.5 p-3 rounded-xl transition-all duration-300 relative min-w-[70px]",
              activeTab === item.id
                ? "text-[var(--primary)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            )}
          >
            <div className={cn(
              "transition-all duration-300",
              activeTab === item.id ? "scale-110 -translate-y-0.5" : "scale-100"
            )}>
              {item.icon}
            </div>
            <span className={cn(
              "text-[10px] font-bold uppercase tracking-widest transition-all",
              activeTab === item.id ? "opacity-100" : "opacity-60"
            )}>
              {item.label}
            </span>
            
            {/* Active Indicator Dot */}
            {activeTab === item.id && (
              <div className="absolute -top-1 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-[var(--primary)] shadow-[0_0_8px_rgba(var(--primary-rgb),0.6)]" />
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
