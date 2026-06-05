import { useEffect, useState } from 'react';
import { Toaster } from 'sonner';
import { ConfirmProvider } from './hooks/use-confirm';
import Layout from './components/Layout';
import TranslatePage from './pages/TranslatePage';
import LibraryPage from './pages/LibraryPage';
import ContextLibraryPage from './pages/ContextLibraryPage';
import SettingsPage from './pages/SettingsPage';
import ReaderPage from './pages/ReaderPage';
import BookmarksPage from './pages/BookmarksPage';
import BulkStatusCenter from './components/BulkStatusCenter';
import type { TabId } from './components/Sidebar';

const APP_SESSION_KEY = 'readomni_app_session_v1';
const APP_SESSION_MAX_IDLE_MS = 6 * 60 * 60 * 1000;

interface AppSessionState {
  activeTab: TabId;
  openThreadId: number | null;
  lastActiveAt: number;
}

function readAppSession(): AppSessionState | null {
  try {
    const raw = localStorage.getItem(APP_SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AppSessionState>;
    if (
      typeof parsed.activeTab !== 'string' ||
      typeof parsed.lastActiveAt !== 'number' ||
      !['translate', 'library', 'context', 'settings', 'bookmarks'].includes(parsed.activeTab)
    ) {
      localStorage.removeItem(APP_SESSION_KEY);
      return null;
    }
    if (Date.now() - parsed.lastActiveAt > APP_SESSION_MAX_IDLE_MS) {
      localStorage.removeItem(APP_SESSION_KEY);
      return null;
    }
    return {
      activeTab: parsed.activeTab as TabId,
      openThreadId: typeof parsed.openThreadId === 'number' ? parsed.openThreadId : null,
      lastActiveAt: parsed.lastActiveAt,
    };
  } catch {
    localStorage.removeItem(APP_SESSION_KEY);
    return null;
  }
}

export default function App() {
  const initialSession = readAppSession();
  const [openThreadId, setOpenThreadId] = useState<number | null>(initialSession?.openThreadId ?? null);
  const [openChapterId, setOpenChapterId] = useState<number | null>(null);
  const [isReadingChapter, setIsReadingChapter] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>(initialSession?.activeTab ?? 'translate');

  useEffect(() => {
    const persistSession = () => {
      const payload: AppSessionState = {
        activeTab,
        openThreadId,
        lastActiveAt: Date.now(),
      };
      localStorage.setItem(APP_SESSION_KEY, JSON.stringify(payload));
    };

    persistSession();
    window.addEventListener('pagehide', persistSession);
    document.addEventListener('visibilitychange', persistSession);

    return () => {
      window.removeEventListener('pagehide', persistSession);
      document.removeEventListener('visibilitychange', persistSession);
    };
  }, [activeTab, openThreadId]);

  const openReaderFromLibrary = (threadId: number, chapterId?: number) => {
    setActiveTab('library');
    setOpenThreadId(threadId);
    if (chapterId) {
      setOpenChapterId(chapterId);
    } else {
      setOpenChapterId(null);
    }
  };

  if (openThreadId !== null) {
    return (
      <ConfirmProvider>
        <ReaderPage
          threadId={openThreadId}
          initialChapterId={openChapterId}
          onBack={() => {
            setIsReadingChapter(false);
            setOpenThreadId(null);
            setOpenChapterId(null);
          }}
          onReadingChapterChange={setIsReadingChapter}
        />
        {!isReadingChapter && <BulkStatusCenter />}
        <Toaster theme="system" position="bottom-center" richColors closeButton />
      </ConfirmProvider>
    );
  }

  return (
    <ConfirmProvider>
      <Layout
        activeTab={activeTab}
        onTabChange={(tab) => {
          setActiveTab(tab);
          setIsReadingChapter(false);
          setOpenThreadId(null);
          setOpenChapterId(null);
        }}
      >
        {(activeTab) => {
          switch (activeTab) {
            case 'translate': return <TranslatePage
              onOpenThread={openReaderFromLibrary}
              onNavigateToSettings={() => {
                setActiveTab('settings');
                setIsReadingChapter(false);
                setOpenThreadId(null);
              }}
              onNavigateToLibrary={() => {
                setActiveTab('library');
                setIsReadingChapter(false);
                setOpenThreadId(null);
              }}
            />;
            case 'library': return <LibraryPage onOpenThread={openReaderFromLibrary} />;
            case 'context': return <ContextLibraryPage />;
            case 'settings': return <SettingsPage />;
            case 'bookmarks': return <BookmarksPage onOpenChapter={(tid, cid) => openReaderFromLibrary(tid, cid)} onOpenLibrary={() => setActiveTab('library')} />;
          }
        }}
      </Layout>
      <BulkStatusCenter />
      <Toaster theme="system" position="bottom-center" richColors closeButton />
    </ConfirmProvider>
  );
}

