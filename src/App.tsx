import { useState } from 'react';
import Layout from './components/Layout';
import TranslatePage from './pages/TranslatePage';
import LibraryPage from './pages/LibraryPage';
import ContextLibraryPage from './pages/ContextLibraryPage';
import SettingsPage from './pages/SettingsPage';
import ReaderPage from './pages/ReaderPage';

export default function App() {
  const [openThreadId, setOpenThreadId] = useState<number | null>(null);

  return (
    <Layout onTabChange={() => setOpenThreadId(null)}>
      {(activeTab) => {
        // Global Reader Overlay
        if (openThreadId !== null) {
          return (
            <ReaderPage
              threadId={openThreadId}
              onBack={() => setOpenThreadId(null)}
            />
          );
        }

        switch (activeTab) {
          case 'translate': return <TranslatePage onOpenThread={(id) => setOpenThreadId(id)} />;
          case 'library': return <LibraryPage onOpenThread={(id) => setOpenThreadId(id)} />;
          case 'context': return <ContextLibraryPage />;
          case 'settings': return <SettingsPage />;
        }
      }}
    </Layout>
  );
}

