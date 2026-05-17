import { cn } from '@/lib/utils';
import { navItems, type TabId } from './Sidebar';

interface BottomNavProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

export default function BottomNav({ activeTab, onTabChange }: BottomNavProps) {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 md:hidden px-4 pb-4 pt-2">
      <div className="bg-[var(--card)]/80 backdrop-blur-xl border border-[var(--border)] rounded-2xl shadow-2xl flex items-center justify-around p-2">
        {navItems.map((item) => (
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
