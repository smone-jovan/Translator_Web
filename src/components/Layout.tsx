import { type ReactNode } from 'react';
import Sidebar, { type TabId } from './Sidebar';
import BottomNav from './BottomNav';

interface LayoutProps {
  children: (activeTab: TabId) => ReactNode;
  activeTab: TabId;
  onTabChange?: (tab: TabId) => void;
}

export default function Layout({ children, activeTab, onTabChange }: LayoutProps) {
  const handleTabChange = (tab: TabId) => {
    onTabChange?.(tab);
  };

  return (
    <div className="flex min-h-screen w-full bg-[var(--background)]">
      <Sidebar
        activeTab={activeTab}
        onTabChange={handleTabChange}
        onClose={() => {}}
      />

      <main className="flex-1 flex flex-col min-w-0 relative md:pl-20">
        {/* Content */}
        <div className="flex-1 p-4 md:p-8 pb-28 md:pb-8 w-full max-w-6xl mx-auto">
          {children(activeTab)}
        </div>

        {/* Mobile Bottom Nav */}
        <BottomNav 
          activeTab={activeTab} 
          onTabChange={handleTabChange} 
          visible={true}
        />
      </main>
    </div>
  );
}

