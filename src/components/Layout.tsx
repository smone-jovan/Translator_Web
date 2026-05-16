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
        {/* Mobile Menu Button (Only visible on mobile) */}
        <div className="md:hidden absolute top-4 left-4 z-50">
          <button
            className="p-2 rounded-lg bg-[var(--card)] border border-[var(--border)] shadow-md text-[var(--foreground)]"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4 md:p-8">
          <div className="max-w-6xl mx-auto h-full fade-in">
            {children(activeTab)}
          </div>
        </div>
      </main>
    </div>
  );
}

