import { useState, type ReactNode } from 'react';
import Sidebar, { type TabId } from './Sidebar';
import BottomNav from './BottomNav';

interface LayoutProps {
  children: (activeTab: TabId) => ReactNode;
  onTabChange?: (tab: TabId) => void;
}

export default function Layout({ children, onTabChange }: LayoutProps) {
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>('translate');

  const handleTabChange = (tab: TabId) => {
    setActiveTab(tab);
    onTabChange?.(tab);
  };

  return (
    <div className="flex h-screen w-full overflow-hidden">
      <Sidebar
        isOpen={isSidebarOpen}
        activeTab={activeTab}
        onTabChange={handleTabChange}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="flex-1 flex flex-col h-full overflow-hidden relative bg-[var(--background)]">
        {/* Mobile Menu Button - Optional, keeping hidden if BottomNav is enough, or move to top-right if needed */}
        {/* <div className="md:hidden absolute top-4 right-4 z-50">
          <button
            className="p-3 rounded-2xl bg-[var(--card)]/80 backdrop-blur-md border border-[var(--border)] shadow-xl text-[var(--foreground)]"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={20} />
          </button>
        </div> */}

        {/* Content */}
        <div className="flex-1 overflow-auto p-4 md:p-8 pb-28 md:pb-8">
          <div className="max-w-6xl mx-auto h-full">
            {children(activeTab)}
          </div>
        </div>

        {/* Mobile Bottom Nav */}
        <BottomNav 
          activeTab={activeTab} 
          onTabChange={handleTabChange} 
        />
      </main>
    </div>
  );
}

