import { useState, useRef, useEffect, type ReactNode } from 'react';
import Sidebar, { type TabId } from './Sidebar';
import BottomNav from './BottomNav';

interface LayoutProps {
  children: (activeTab: TabId) => ReactNode;
  activeTab: TabId;
  onTabChange?: (tab: TabId) => void;
}

export default function Layout({ children, activeTab, onTabChange }: LayoutProps) {
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [controlsVisible, setControlsVisible] = useState(true);
  const lastScrollTop = useRef(0);
  const scrollRafId = useRef<number | null>(null);

  const handleTabChange = (tab: TabId) => {
    setControlsVisible(true);
    onTabChange?.(tab);
  };

  useEffect(() => {
    const handleWindowScroll = () => {
      if (scrollRafId.current !== null) return;
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      
      scrollRafId.current = requestAnimationFrame(() => {
        const delta = scrollTop - lastScrollTop.current;
        
        if (scrollTop < 20) {
          setControlsVisible(true);
        } else if (delta > 30) {
          setSidebarOpen(false);
          setControlsVisible(false);
        } else if (delta < -15) {
          setControlsVisible(true);
        }
        
        lastScrollTop.current = scrollTop;
        scrollRafId.current = null;
      });
    };

    window.addEventListener('scroll', handleWindowScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleWindowScroll);
  }, []);

  const handleContentClick = (e: React.MouseEvent) => {
    if (window.getSelection()?.toString()) return;
    const target = e.target as HTMLElement;
    if (target.closest('button, input, select, textarea, a, label, [role="button"]')) {
      return;
    }
    setControlsVisible(prev => !prev);
  };

  return (
    <div className="flex min-h-screen w-full bg-[var(--background)]">
      <Sidebar
        isOpen={isSidebarOpen}
        activeTab={activeTab}
        onTabChange={handleTabChange}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="flex-1 flex flex-col min-w-0 relative" onClick={handleContentClick}>
        {/* Content */}
        <div className="flex-1 p-4 md:p-8 pb-28 md:pb-8 w-full max-w-6xl mx-auto">
          {children(activeTab)}
        </div>

        {/* Mobile Bottom Nav */}
        <BottomNav 
          activeTab={activeTab} 
          onTabChange={handleTabChange} 
          visible={controlsVisible}
        />
      </main>
    </div>
  );
}

