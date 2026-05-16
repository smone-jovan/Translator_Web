import { useState, type ReactNode } from 'react';
import { Menu } from 'lucide-react';
import Sidebar, { type TabId } from './Sidebar';

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

      <main className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Header */}
        <header className="h-14 glass border-b border-white/10 flex items-center px-4 md:px-6 sticky top-0 z-30">
          <button
            className="md:hidden mr-4 p-2 rounded-lg hover:bg-[var(--secondary)]"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={20} />
          </button>
          <h1 className="font-semibold text-base capitalize">{activeTab}</h1>
        </header>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4 md:p-6">
          <div className="max-w-5xl mx-auto fade-in">
            {children(activeTab)}
          </div>
        </div>
      </main>
    </div>
  );
}

