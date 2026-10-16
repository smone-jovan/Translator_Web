import { useEffect, useState } from "react";
import { Toaster } from "sonner";
import { ConfirmProvider } from "./hooks/use-confirm";
import Layout from "./components/Layout";
import TranslatePage from "./pages/TranslatePage";
import LibraryPage from "./pages/LibraryPage";
import ContextLibraryPage from "./pages/ContextLibraryPage";
import SettingsPage from "./pages/SettingsPage";
import ReaderPage from "./pages/ReaderPage";
import BookmarksPage from "./pages/BookmarksPage";
import BulkStatusCenter from "./components/BulkStatusCenter";
import type { TabId } from "./components/Sidebar";
import { getWorkspaceStorageKey } from "./lib/api";

function getAppSessionKey(): string {
  return getWorkspaceStorageKey("readomni_app_session_v1");
}

const APP_SESSION_MAX_IDLE_MS = 6 * 60 * 60 * 1000;

interface AppSessionState {
  activeTab: TabId;
  openThreadId: number | null;
  openChapterId: number | null;
  lastActiveAt: number;
}

function readAppSession(): AppSessionState | null {
  try {
    const key = getAppSessionKey();
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AppSessionState>;
    if (
      typeof parsed.activeTab !== "string" ||
      typeof parsed.lastActiveAt !== "number" ||
      !["translate", "library", "context", "settings", "bookmarks"].includes(
        parsed.activeTab
      )
    ) {
      localStorage.removeItem(key);
      return null;
    }
    if (Date.now() - parsed.lastActiveAt > APP_SESSION_MAX_IDLE_MS) {
      localStorage.removeItem(key);
      return null;
    }
    return {
      activeTab: parsed.activeTab as TabId,
      openThreadId:
        typeof parsed.openThreadId === "number" ? parsed.openThreadId : null,
      openChapterId:
        typeof parsed.openChapterId === "number" ? parsed.openChapterId : null,
      lastActiveAt: parsed.lastActiveAt,
    };
  } catch {
    try {
      localStorage.removeItem(getAppSessionKey());
    } catch {
      // ignore
    }
    return null;
  }
}

export default function App() {
  const initialSession = readAppSession();
  const [openThreadId, setOpenThreadId] = useState<number | null>(
    initialSession?.openThreadId ?? null
  );
  const [openChapterId, setOpenChapterId] = useState<number | null>(
    initialSession?.openChapterId ?? null
  );
  const [isReadingChapter, setIsReadingChapter] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>(
    initialSession?.activeTab ?? "translate"
  );

  useEffect(() => {
    const persistSession = () => {
      try {
        const payload: AppSessionState = {
          activeTab,
          openThreadId,
          openChapterId,
          lastActiveAt: Date.now(),
        };
        localStorage.setItem(getAppSessionKey(), JSON.stringify(payload));
      } catch {
        // ignore storage errors
      }
    };

    persistSession();
    window.addEventListener("pagehide", persistSession);
    document.addEventListener("visibilitychange", persistSession);

    return () => {
      window.removeEventListener("pagehide", persistSession);
      document.removeEventListener("visibilitychange", persistSession);
    };
  }, [activeTab, openThreadId, openChapterId]);

  useEffect(() => {
    const handleHash = () => {
      const raw = window.location.hash.replace("#", "").toLowerCase();
      const validTabs: TabId[] = [
        "translate",
        "library",
        "context",
        "settings",
        "bookmarks",
      ];
      if (validTabs.includes(raw as TabId)) {
        setActiveTab(raw as TabId);
        setIsReadingChapter(false);
        setOpenThreadId(null);
      }
    };
    window.addEventListener("hashchange", handleHash);
    if (window.location.hash) {
      handleHash();
    }
    return () => window.removeEventListener("hashchange", handleHash);
  }, []);

  const openReader = (threadId: number, chapterId?: number) => {
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
          onActiveChapterChange={setOpenChapterId}
        />
        {!isReadingChapter && <BulkStatusCenter />}
        {/* While reading, the bottom of the screen holds the thumb toolbar and the settings
            sheet; toasts there covered Prev/List/Settings/Next and the sheet's own buttons.
            At the top they sit below the reader's three control rows (page header 4rem + reader
            nav 3.5rem + pane header 2.5rem = 10rem), over text only. */}
        <Toaster
          theme="system"
          position={isReadingChapter ? "top-center" : "bottom-center"}
          offset={isReadingChapter ? { top: "10.5rem" } : undefined}
          mobileOffset={isReadingChapter ? { top: "10.5rem" } : undefined}
          richColors
          closeButton
        />
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
            case "translate":
              return (
                <TranslatePage
                  onOpenThread={openReader}
                  onNavigateToSettings={() => {
                    setActiveTab("settings");
                    setIsReadingChapter(false);
                    setOpenThreadId(null);
                  }}
                  onNavigateToLibrary={() => {
                    setActiveTab("library");
                    setIsReadingChapter(false);
                    setOpenThreadId(null);
                  }}
                />
              );
            case "library":
              return <LibraryPage onOpenThread={openReader} />;
            case "context":
              return <ContextLibraryPage />;
            case "settings":
              return <SettingsPage />;
            case "bookmarks":
              return (
                <BookmarksPage
                  onOpenChapter={(tid, cid) => openReader(tid, cid)}
                  onOpenLibrary={() => setActiveTab("library")}
                />
              );
          }
        }}
      </Layout>
      <BulkStatusCenter />
      <Toaster theme="system" position="bottom-center" richColors closeButton />
    </ConfirmProvider>
  );
}
