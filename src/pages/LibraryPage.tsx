import {
  BookOpen,
  FileText,
  Trash2,
  MoreVertical,
  Play,
  Clock,
  Search,
  Sparkles,
  Globe,
  ScanSearch,
  AlertTriangle,
  Loader2,
  CheckCircle2,
  X,
  Wand2,
  Eraser,
  RotateCcw,
  Pencil,
  Flame,
  ArrowUpDown,
} from "lucide-react";
import React, { useState, useEffect, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  getApiUrl,
  getActiveWorkspace,
  getWorkspaceStorageKey,
  invalidateThreadCache,
} from "@/lib/api";
import { coverImageSrc } from "@/lib/utils";
import BulkTranslateModal from "@/components/BulkTranslateModal";
import AutoAwesome from "@mui/icons-material/AutoAwesome";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import IconButton from "@mui/material/IconButton";
import EditCoverModal, { getTitleGradient } from "@/components/EditCoverModal";
import ScrapeNUModal from "@/components/ScrapeNUModal";
import { useConfirm } from "@/hooks/use-confirm";
import { toast } from "sonner";
import { syncEngineLoadMode } from "@/lib/settingsSync";
import { clearOfflineThread } from "@/lib/offlineStorage";

type FilterTab = "all" | "reading" | "unread" | "completed";
type SortOption = "last_read" | "recent_added" | "progress" | "title";

interface ThreadItem {
  id: number;
  title: string;
  author?: string;
  source_type: "url" | "epub";
  chapter_count: number;
  created_at: string;
  last_read?: string;
  last_read_id?: number | null;
  last_read_at?: string | null;
  progress?: number;
  cover_image?: string | null;
  original_title?: string | null;
  genres?: string | null;
  tags?: string | null;
  status?: string | null;
  status_coo?: string | null;
  synopsis?: string | null;
}

interface HallucinationMatch {
  token: string;
  count: number;
  start_index: number;
  end_index: number;
  snippet: string;
}

interface ChapterHallucinationAudit {
  chapter_id: number;
  chapter_order: number;
  chapter_title?: string | null;
  status: "clean" | "flagged" | "no_translation";
  has_repetition: boolean;
  match_count: number;
  repetition_matches: HallucinationMatch[];
}

interface ThreadHallucinationAudit {
  thread_id: number;
  checked_chapters: number;
  flagged_chapters: number;
  repetition_threshold: number;
  chapters: ChapterHallucinationAudit[];
}

interface LibraryPageProps {
  onOpenThread?: (threadId: number, chapterId?: number) => void;
}

interface LibraryBookCardProps {
  thread: ThreadItem;
  actions: {
    onOpen: (chapterId?: number) => void;
    onDelete: () => void;
    onBatchTranslate: () => void;
    onEditCover: () => void;
    onScrapeNU: () => void;
    onCheckHallucinate: () => void;
    onRunTxtCleaner: () => void;
    onRunEpubCleaner: () => void;
    onDeleteTranslations: () => void;
    onFixTruncated: () => void;
    onEditInfo: () => void;
  };
}

const LibraryBookCard = ({ thread, actions }: LibraryBookCardProps) => {
  const {
    onOpen,
    onDelete,
    onBatchTranslate,
    onEditCover,
    onScrapeNU,
    onCheckHallucinate,
    onRunTxtCleaner,
    onRunEpubCleaner,
    onDeleteTranslations,
    onFixTruncated,
    onEditInfo,
  } = actions;
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };
  const handleClose = () => {
    setAnchorEl(null);
  };

  return (
    <Card className="overflow-hidden group hover:shadow-xl hover:border-[var(--primary)]/30 transition-all duration-300 bg-[var(--card)] border-[var(--border)]">
      <CardContent className="p-0 flex flex-col h-full">
        {/* Poster Area - Click image box to open thread */}
        <div
          className="relative aspect-[3/4] bg-[var(--secondary)] overflow-hidden cursor-pointer"
          onClick={() => onOpen()}
        >
          {thread.cover_image ? (
            <img
              src={coverImageSrc(thread.cover_image)}
              alt={thread.title}
              className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
            />
          ) : (
            <div
              className="absolute inset-0 p-4 flex flex-col justify-between items-center text-center select-none transition-transform duration-500 group-hover:scale-105"
              style={{ background: getTitleGradient(thread.title) }}
            >
              {/* Visual Accent */}
              <div className="w-8 h-1 bg-white/20 rounded-full mt-2" />

              {/* Stylized initials in middle */}
              <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-md font-black text-white tracking-widest">
                {(() => {
                  const cleanText = thread.title
                    .replace(/[^\w\s\u4e00-\u9fa5]/g, "")
                    .trim();
                  const parts = cleanText.split(/\s+/);
                  if (parts.length >= 2)
                    return (parts[0][0] + parts[1][0]).toUpperCase();
                  return thread.title.substring(0, 2).toUpperCase();
                })()}
              </div>

              {/* Mini Title below */}
              <div className="w-full mb-1">
                <p className="text-[9px] font-black text-white/90 uppercase tracking-widest line-clamp-2 px-1 leading-tight">
                  {thread.title}
                </p>
              </div>
            </div>
          )}

          {/* Badge */}
          <div className="absolute top-3 left-3 px-2 py-1 rounded-md bg-black/40 backdrop-blur-md text-[10px] font-bold text-white uppercase tracking-wider">
            {thread.source_type}
          </div>

          {/* Hover Actions */}
          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
            <Button
              size="icon"
              className="w-12 h-12 rounded-full bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 shadow-lg transform scale-90 group-hover:scale-100 transition-all duration-300 flex items-center justify-center"
              onClick={(e) => {
                e.stopPropagation();
                onOpen();
              }}
            >
              <Play size={24} className="fill-current ml-0.5" />
            </Button>
          </div>
        </div>

        {/* Info Area */}
        <div className="p-5 flex-1 flex flex-col">
          <div className="flex justify-between items-start mb-1">
            <div className="flex flex-col gap-0.5 max-w-[85%]">
              <h3 className="font-bold text-sm text-[var(--foreground)] line-clamp-1 leading-tight group-hover:text-[var(--primary)] transition-colors">
                {thread.title}
              </h3>
              {thread.original_title && (
                <p className="text-[10px] text-[var(--muted-foreground)]/80 italic font-medium line-clamp-1">
                  {thread.original_title}
                </p>
              )}
            </div>
            <IconButton
              size="small"
              onClick={handleClick}
              sx={{
                color: "var(--muted-foreground)",
                "&:hover": { color: "var(--foreground)" },
              }}
            >
              <MoreVertical size={16} />
            </IconButton>
            <Menu
              anchorEl={anchorEl}
              open={open}
              onClose={handleClose}
              slotProps={{
                paper: {
                  sx: {
                    background: "var(--card)",
                    border: "1px solid var(--border)",
                    color: "var(--foreground)",
                    borderRadius: "12px",
                    mt: 0.5,
                    "& .MuiMenuItem-root": {
                      fontSize: "0.75rem",
                      gap: 1.5,
                      px: 2,
                      py: 1,
                      "&:hover": { background: "rgba(255,255,255,0.05)" },
                    },
                  },
                },
              }}
            >
              <MenuItem
                onClick={() => {
                  onBatchTranslate();
                  handleClose();
                }}
              >
                <AutoAwesome sx={{ fontSize: 16, color: "var(--primary)" }} />
                Translate All (Batch)
              </MenuItem>
              <MenuItem
                onClick={() => {
                  onEditCover();
                  handleClose();
                }}
              >
                <Sparkles size={16} className="text-[var(--primary)]" />
                Customize Cover
              </MenuItem>
              <MenuItem
                onClick={() => {
                  onEditInfo();
                  handleClose();
                }}
              >
                <Pencil size={16} className="text-[var(--primary)]" />
                Edit Info
              </MenuItem>
              <MenuItem
                onClick={() => {
                  onScrapeNU();
                  handleClose();
                }}
              >
                <Globe size={16} className="text-[var(--primary)]" />
                Scrape from NU
              </MenuItem>
              <MenuItem
                onClick={() => {
                  onCheckHallucinate();
                  handleClose();
                }}
              >
                <ScanSearch size={16} className="text-[var(--primary)]" />
                Check Hallucinate
              </MenuItem>
              <MenuItem
                onClick={() => {
                  onRunTxtCleaner();
                  handleClose();
                }}
              >
                <Eraser size={16} className="text-[var(--primary)]" />
                TXT Cleaner
              </MenuItem>
              <MenuItem
                onClick={() => {
                  onRunEpubCleaner();
                  handleClose();
                }}
              >
                <Wand2 size={16} className="text-[var(--primary)]" />
                EPUB Cleaner
              </MenuItem>
              <MenuItem
                onClick={() => {
                  onDeleteTranslations();
                  handleClose();
                }}
                sx={{ color: "#f59e0b" }}
              >
                <RotateCcw size={16} />
                Delete All Translations
              </MenuItem>
              <MenuItem
                onClick={() => {
                  onFixTruncated();
                  handleClose();
                }}
                sx={{ color: "#3b82f6" }}
              >
                <Wand2 size={16} />
                Fix Truncated
              </MenuItem>
              <MenuItem
                onClick={() => {
                  onDelete();
                  handleClose();
                }}
                sx={{ color: "#ef4444" }}
              >
                <Trash2 size={16} />
                Delete Book
              </MenuItem>
            </Menu>
          </div>
          <div className="flex justify-between items-center mb-2">
            <p className="text-[10px] text-[var(--muted-foreground)] line-clamp-1">
              {thread.author || "Unknown Author"}
            </p>
            {thread.status && (
              <span className="text-[8px] font-black px-1.5 py-0.5 rounded-full bg-green-500/10 text-green-400 border border-green-500/20 shadow-sm uppercase tracking-wide">
                {thread.status}
              </span>
            )}
          </div>
          {thread.genres && (
            <div className="flex flex-wrap gap-1 mb-3">
              {thread.genres
                .split(",")
                .slice(0, 2)
                .map((genre, i) => (
                  <span
                    key={i}
                    className="text-[8px] font-extrabold px-1.5 py-0.5 rounded bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20 uppercase tracking-wide"
                  >
                    {genre.trim()}
                  </span>
                ))}
            </div>
          )}

          <div className="mt-auto space-y-3">
            {/* Resume / Start Reading Action Button */}
            <div>
              {thread.last_read ? (
                <Button
                  size="sm"
                  className="w-full rounded-xl bg-[var(--primary)] text-[var(--primary-foreground)] font-bold hover:opacity-90 transition-all flex items-center justify-center gap-1.5 py-2 text-[11px] shadow-md shadow-[var(--primary)]/20"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpen(thread.last_read_id ?? undefined);
                  }}
                >
                  <Play size={13} className="fill-current" />
                  <span className="truncate">Resume: {thread.last_read}</span>
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full rounded-xl border-[var(--primary)]/30 text-[var(--primary)] font-bold hover:bg-[var(--primary)]/10 transition-all flex items-center justify-center gap-1.5 py-2 text-[11px]"
                  onClick={(e) => {
                    e.stopPropagation();
                    onOpen();
                  }}
                >
                  <BookOpen size={13} />
                  <span>Start Reading</span>
                </Button>
              )}
            </div>

            {/* Progress */}
            <div className="space-y-1">
              <div className="flex justify-between text-[9px] font-bold text-[var(--muted-foreground)] uppercase tracking-tighter">
                <span>Progress</span>
                <span>{thread.progress || 0}%</span>
              </div>
              <div className="h-1 w-full bg-[var(--secondary)] rounded-full overflow-hidden">
                <div
                  className="h-full bg-[var(--primary)] transition-all duration-500"
                  style={{ width: `${thread.progress || 0}%` }}
                />
              </div>
            </div>

            {/* Stats */}
            <div className="flex items-center justify-between pt-2 border-t border-[var(--border)]">
              <div className="flex items-center gap-1.5 text-[10px] text-[var(--muted-foreground)]">
                <FileText size={12} />
                <span>{thread.chapter_count} Chapters</span>
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-[var(--muted-foreground)]">
                <Clock size={12} />
                <span>{new Date(thread.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

function getLibraryCacheKey(): string {
  return getWorkspaceStorageKey("readomni_library_cache_v1");
}

function getLibraryScrollKey(): string {
  return getWorkspaceStorageKey("readomni_library_scroll_v1");
}

interface LibraryCacheData {
  threads: ThreadItem[];
  searchQuery: string;
  activeTab: FilterTab;
  sortBy: SortOption;
  lastOpenedThreadId: number | null;
  savedAt: number;
}

const memoryLibraryCacheByWs: Record<string, LibraryCacheData | null> = {};
const memoryScrollYByWs: Record<string, number> = {};

function readLibrarySessionCache(): LibraryCacheData | null {
  const ws = getActiveWorkspace();
  try {
    const raw = sessionStorage.getItem(getLibraryCacheKey());
    if (!raw) {
      memoryLibraryCacheByWs[ws] = null;
      return null;
    }
    if (memoryLibraryCacheByWs[ws]) return memoryLibraryCacheByWs[ws];
    const parsed = JSON.parse(raw) as Partial<LibraryCacheData>;
    if (parsed && Array.isArray(parsed.threads)) {
      memoryLibraryCacheByWs[ws] = {
        threads: parsed.threads,
        searchQuery:
          typeof parsed.searchQuery === "string" ? parsed.searchQuery : "",
        activeTab: parsed.activeTab || "all",
        sortBy: parsed.sortBy || "last_read",
        lastOpenedThreadId:
          typeof parsed.lastOpenedThreadId === "number"
            ? parsed.lastOpenedThreadId
            : null,
        savedAt:
          typeof parsed.savedAt === "number" ? parsed.savedAt : Date.now(),
      };
      return memoryLibraryCacheByWs[ws];
    }
  } catch {
    // ignore
  }
  return null;
}

function readSavedScrollY(): number {
  const ws = getActiveWorkspace();
  if ((memoryScrollYByWs[ws] ?? 0) > 0) return memoryScrollYByWs[ws];
  try {
    const raw = sessionStorage.getItem(getLibraryScrollKey());
    if (raw) {
      const num = parseInt(raw, 10);
      if (!isNaN(num) && num > 0) {
        memoryScrollYByWs[ws] = num;
        return num;
      }
    }
  } catch {
    // ignore
  }
  return 0;
}

function saveLibrarySessionCache(data: Partial<LibraryCacheData>) {
  const ws = getActiveWorkspace();
  const prev = readLibrarySessionCache() || {
    threads: [],
    searchQuery: "",
    activeTab: "all" as FilterTab,
    sortBy: "last_read" as SortOption,
    lastOpenedThreadId: null,
    savedAt: Date.now(),
  };
  const updated: LibraryCacheData = {
    ...prev,
    ...data,
    savedAt: Date.now(),
  };
  memoryLibraryCacheByWs[ws] = updated;
  try {
    sessionStorage.setItem(getLibraryCacheKey(), JSON.stringify(updated));
  } catch {
    // ignore
  }
}

function saveScrollY(scrollY: number) {
  const ws = getActiveWorkspace();
  memoryScrollYByWs[ws] = scrollY;
  try {
    sessionStorage.setItem(getLibraryScrollKey(), String(scrollY));
  } catch {
    // ignore
  }
}

export default function LibraryPage({ onOpenThread }: LibraryPageProps) {
  const initialCache = readLibrarySessionCache();
  const [threads, setThreads] = useState<ThreadItem[]>(
    () => initialCache?.threads ?? []
  );
  const [loading, setLoading] = useState(
    () => (initialCache?.threads?.length ?? 0) === 0
  );
  const [searchQuery, setSearchQuery] = useState(
    () => initialCache?.searchQuery ?? ""
  );
  const [activeTab, setActiveTab] = useState<FilterTab>(
    () => initialCache?.activeTab ?? "all"
  );
  const [sortBy, setSortBy] = useState<SortOption>(
    () => initialCache?.sortBy ?? "last_read"
  );
  const [selectedBatchThread, setSelectedBatchThread] = useState<
    | (ThreadItem & {
        chapters?: Array<{
          id: number;
          order: number;
          title_original: string | null;
          title_translated?: string | null;
          has_translation: boolean;
          translation_status?: string;
        }>;
      })
    | null
  >(null);
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);
  const [selectedCoverThread, setSelectedCoverThread] =
    useState<ThreadItem | null>(null);
  const [isCoverModalOpen, setIsCoverModalOpen] = useState(false);
  const [selectedScrapeThread, setSelectedScrapeThread] =
    useState<ThreadItem | null>(null);
  const [isScrapeModalOpen, setIsScrapeModalOpen] = useState(false);
  const [auditThread, setAuditThread] = useState<ThreadItem | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditResult, setAuditResult] =
    useState<ThreadHallucinationAudit | null>(null);
  const [auditError, setAuditError] = useState("");
  const [editThread, setEditThread] = useState<ThreadItem | null>(null);
  const [editForm, setEditForm] = useState({
    title: "",
    genres: "",
    author: "",
  });
  const [editSaving, setEditSaving] = useState(false);
  const { confirm } = useConfirm();

  const handleOpenThread = useCallback(
    (threadId: number, chapterId?: number) => {
      saveScrollY(window.scrollY);
      saveLibrarySessionCache({ lastOpenedThreadId: threadId });
      onOpenThread?.(threadId, chapterId);
    },
    [onOpenThread]
  );

  // Persist filter and search states
  useEffect(() => {
    saveLibrarySessionCache({ searchQuery, activeTab, sortBy });
  }, [searchQuery, activeTab, sortBy]);

  // Track window scroll
  useEffect(() => {
    let animId: number | null = null;
    const handleScroll = () => {
      if (animId) cancelAnimationFrame(animId);
      animId = requestAnimationFrame(() => {
        if (window.scrollY > 0) {
          saveScrollY(window.scrollY);
        }
      });
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      if (window.scrollY > 0) {
        saveScrollY(window.scrollY);
      }
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  // Restore scroll position upon mounting
  useEffect(() => {
    const targetScroll = readSavedScrollY();
    if (targetScroll > 0) {
      window.scrollTo({ top: targetScroll, behavior: "instant" });
      const raf = requestAnimationFrame(() => {
        window.scrollTo({ top: targetScroll, behavior: "instant" });
      });
      return () => cancelAnimationFrame(raf);
    }
  }, []);

  const handleSaveCover = async (coverValue: string | null) => {
    if (!selectedCoverThread) return;
    try {
      const res = await fetch(
        getApiUrl(`/api/threads/${selectedCoverThread.id}/cover`),
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ cover_image: coverValue }),
        }
      );
      if (!res.ok) throw new Error("Failed to update cover");

      fetchThreads(true);
    } catch (e) {
      console.error("Error saving cover:", e);
      throw e;
    }
  };

  const fetchThreads = useCallback(async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      const res = await fetch(getApiUrl("/api/threads"));
      const data = await res.json();
      setThreads(data);
      saveLibrarySessionCache({ threads: data });
    } catch {
      console.error("Failed to fetch threads");
    } finally {
      setLoading(false);
    }
  }, []);

  const initialCacheRef = React.useRef(initialCache);

  useEffect(() => {
    const hasCache = (initialCacheRef.current?.threads?.length ?? 0) > 0;
    fetchThreads(hasCache);
  }, [fetchThreads]);

  // Silently refresh when batch translation is in progress or completes
  useEffect(() => {
    let lastCompletedCount = -1;

    const handleBatchProgress = (e: Event) => {
      const customEv = e as CustomEvent;
      const detail = customEv.detail;
      if (detail && detail.completed !== lastCompletedCount) {
        lastCompletedCount = detail.completed;
        fetch(getApiUrl(`/api/threads?t=${Date.now()}`), { cache: "no-store" })
          .then((res) => res.json())
          .then((data) => {
            setThreads(data);
            saveLibrarySessionCache({ threads: data });
          })
          .catch(() => {});
      }
    };

    const handleBatchCompleted = () => {
      fetch(getApiUrl(`/api/threads?t=${Date.now()}`), { cache: "no-store" })
        .then((res) => res.json())
        .then((data) => {
          setThreads(data);
          saveLibrarySessionCache({ threads: data });
        })
        .catch(() => {});
    };

    window.addEventListener("batch-progress", handleBatchProgress);
    window.addEventListener("batch-completed", handleBatchCompleted);

    return () => {
      window.removeEventListener("batch-progress", handleBatchProgress);
      window.removeEventListener("batch-completed", handleBatchCompleted);
    };
  }, []);

  const handleDelete = async (id: number) => {
    const isConfirmed = await confirm({
      title: "Delete Book?",
      description:
        "Are you sure you want to delete this book? All translations will be lost permanently.",
      confirmText: "Delete",
      variant: "destructive",
    });

    if (!isConfirmed) return;

    try {
      const res = await fetch(getApiUrl(`/api/threads/${id}`), { method: "DELETE" });
      invalidateThreadCache(id);
      // The id may be reused by the next import; drop this device's offline copy too
      if (res.ok) clearOfflineThread(id).catch(() => {});
      fetchThreads();
      toast.success("Book deleted successfully");
    } catch {
      toast.error("Failed to delete book");
    }
  };

  const handleDeleteTranslations = async (thread: ThreadItem) => {
    const isConfirmed = await confirm({
      title: "Delete All Translations?",
      description: `This will clear all translated content for "${thread.title}". Original text will be preserved. This cannot be undone.`,
      confirmText: "Delete Translations",
      variant: "destructive",
    });

    if (!isConfirmed) return;

    try {
      const res = await fetch(
        getApiUrl(`/api/threads/${thread.id}/translations`),
        { method: "DELETE" }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed");
      invalidateThreadCache(thread.id);
      fetchThreads();
      toast.success(
        `Translations cleared for ${data.chapters_affected} chapters`
      );
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : "Failed to delete translations";
      toast.error(msg);
    }
  };

  const handleFixTruncated = async (thread: ThreadItem) => {
    try {
      const res = await fetch(
        getApiUrl(`/api/threads/${thread.id}/fix-truncated`),
        { method: "POST" }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed");
      invalidateThreadCache(thread.id);
      fetchThreads();
      if (data.reset > 0) {
        toast.success(
          `Reset ${data.reset} truncated chapters. Run batch translate to re-translate.`
        );
      } else {
        toast.info("No truncated translations found");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to fix truncated";
      toast.error(msg);
    }
  };

  const handleOpenBatchModal = async (thread: ThreadItem) => {
    try {
      const res = await fetch(getApiUrl(`/api/threads/${thread.id}`));
      const data = await res.json();
      setSelectedBatchThread(data);
      setIsBatchModalOpen(true);
    } catch {
      console.error("Failed to fetch thread details for batch");
    }
  };

  const handleStartBatch = async (
    chapterIds: number[],
    aiExtract: boolean,
    loadMode: "soft" | "hard",
    targetLang: string,
    overwrite: boolean,
    translationMode: "quality" | "fast" = "quality"
  ) => {
    if (!selectedBatchThread) return;

    syncEngineLoadMode(loadMode);

    try {
      const res = await fetch(
        getApiUrl(`/api/threads/${selectedBatchThread.id}/batch-translate`),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chapter_ids: chapterIds,
            ai_extract: aiExtract,
            overwrite: overwrite,
            target_lang: targetLang,
            translation_mode: translationMode,
            load_mode: loadMode,
          }),
        }
      );

      if (!res.ok) throw new Error("Failed to start batch");

      fetchThreads();
    } catch (e) {
      console.error(e);
    }
  };

  const handleCheckHallucinate = async (thread: ThreadItem) => {
    setAuditThread(thread);
    setAuditLoading(true);
    setAuditResult(null);
    setAuditError("");

    try {
      const res = await fetch(
        getApiUrl(`/api/threads/${thread.id}/hallucination-check`)
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed to audit thread");
      setAuditResult(data);
    } catch (e: unknown) {
      setAuditError(e instanceof Error ? e.message : "Failed to audit thread");
    } finally {
      setAuditLoading(false);
    }
  };

  const runCleanerTool = async (
    thread: ThreadItem,
    tool: "txt-cleaner" | "epub-cleaner"
  ) => {
    const label = tool === "txt-cleaner" ? "TXT Cleaner" : "EPUB Cleaner";
    try {
      const res = await fetch(getApiUrl(`/api/threads/${thread.id}/${tool}`), {
        method: "POST",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `${label} failed`);
      invalidateThreadCache(thread.id);
      await fetchThreads();

      const message = `${label} finished. Scanned: ${data.chapters_scanned}, Updated: ${data.chapters_updated}, Deleted: ${data.chapters_deleted}, Removed lines: ${data.lines_removed}`;

      if (data.chapters_updated > 0 || data.chapters_deleted > 0) {
        toast.success(message);
      } else {
        toast.info(message);
      }
    } catch (e: unknown) {
      toast.error(
        `${label} failed: ${e instanceof Error ? e.message : "Unknown error"}`
      );
    }
  };

  // Counts for tabs
  const allCount = threads.length;
  const readingCount = threads.filter(
    (t) => (t.progress ?? 0) > 0 && (t.progress ?? 0) < 100
  ).length;
  const unreadCount = threads.filter((t) => (t.progress ?? 0) === 0).length;
  const completedCount = threads.filter((t) => (t.progress ?? 0) >= 100).length;

  // Find all books with reading progress, sorted by most recently read (last_read_at)
  const activeReads = threads
    .filter(
      (t) => t.progress !== undefined && t.progress > 0 && t.progress < 100
    )
    .sort((a, b) => {
      const timeA = a.last_read_at
        ? new Date(a.last_read_at).getTime()
        : a.created_at
          ? new Date(a.created_at).getTime()
          : 0;
      const timeB = b.last_read_at
        ? new Date(b.last_read_at).getTime()
        : b.created_at
          ? new Date(b.created_at).getTime()
          : 0;
      return timeB - timeA;
    });

  // Filter and sort for the main grid
  const filteredThreads = threads
    .filter((t) => {
      const query = searchQuery.trim().toLowerCase();
      if (query) {
        const matchTitle = t.title.toLowerCase().includes(query);
        const matchAuthor = t.author
          ? t.author.toLowerCase().includes(query)
          : false;
        const matchOrig = t.original_title
          ? t.original_title.toLowerCase().includes(query)
          : false;
        if (!matchTitle && !matchAuthor && !matchOrig) return false;
      }

      const prog = t.progress ?? 0;
      if (activeTab === "reading") return prog > 0 && prog < 100;
      if (activeTab === "unread") return prog === 0;
      if (activeTab === "completed") return prog >= 100;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === "last_read") {
        const timeA = a.last_read_at
          ? new Date(a.last_read_at).getTime()
          : a.created_at
            ? new Date(a.created_at).getTime()
            : 0;
        const timeB = b.last_read_at
          ? new Date(b.last_read_at).getTime()
          : b.created_at
            ? new Date(b.created_at).getTime()
            : 0;
        return timeB - timeA;
      }
      if (sortBy === "recent_added") {
        const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
        const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
        return timeB - timeA;
      }
      if (sortBy === "progress") {
        return (b.progress ?? 0) - (a.progress ?? 0);
      }
      if (sortBy === "title") {
        return a.title.localeCompare(b.title, undefined, {
          numeric: true,
          sensitivity: "base",
        });
      }
      return 0;
    });

  return (
    <div className="w-full max-w-6xl mx-auto space-y-10 py-8 px-4 sm:px-6 animate-in fade-in duration-700">
      {/* Continue Reading Carousel */}
      {activeReads.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between px-2">
            <h2 className="text-xs font-black uppercase tracking-[0.2em] text-[var(--muted-foreground)] flex items-center gap-2">
              <Clock size={14} /> Continue Reading
            </h2>
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--primary)]" />
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--primary)]/30" />
              <div className="w-1.5 h-1.5 rounded-full bg-[var(--primary)]/10" />
            </div>
          </div>

          <div className="flex gap-6 overflow-x-auto pb-6 pt-2 px-2 no-scrollbar snap-x snap-mandatory">
            {activeReads.map((book) => (
              <section
                key={book.id}
                className="relative flex-shrink-0 w-[90%] md:w-[600px] snap-center overflow-hidden rounded-[2.5rem] bg-gradient-to-br from-[var(--primary)]/10 to-[var(--accent)]/5 border border-[var(--border)] shadow-xl hover:shadow-2xl hover:border-[var(--primary)]/30 transition-all duration-500 group"
              >
                <div className="absolute top-0 right-0 p-6 opacity-5 pointer-events-none group-hover:scale-110 transition-transform duration-700">
                  <BookOpen size={140} />
                </div>

                <div className="relative p-6 md:p-10 flex flex-row items-center gap-6 md:gap-10">
                  {/* Compact Cover */}
                  <div className="w-24 md:w-32 aspect-[3/4] bg-[var(--card)] rounded-2xl shadow-xl flex-shrink-0 overflow-hidden border border-[var(--primary)]/10 rotate-[-2deg] group-hover:rotate-0 transition-transform duration-500 relative">
                    {book.cover_image ? (
                      <img
                        src={coverImageSrc(book.cover_image)}
                        alt={book.title}
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div
                        className="w-full h-full p-2 flex flex-col justify-between items-center text-center select-none"
                        style={{ background: getTitleGradient(book.title) }}
                      >
                        {/* Visual Accent */}
                        <div className="w-4 h-0.5 bg-white/20 rounded-full mt-1" />

                        {/* Stylized initials in middle */}
                        <div className="w-8 h-8 rounded-full bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-[10px] font-black text-white tracking-wider">
                          {(() => {
                            const cleanText = book.title
                              .replace(/[^\w\s\u4e00-\u9fa5]/g, "")
                              .trim();
                            const parts = cleanText.split(/\s+/);
                            if (parts.length >= 2)
                              return (parts[0][0] + parts[1][0]).toUpperCase();
                            return book.title.substring(0, 2).toUpperCase();
                          })()}
                        </div>

                        {/* Mini Title below */}
                        <div className="w-full mb-1">
                          <p className="text-[7px] font-black text-white/80 uppercase tracking-wider line-clamp-1 px-0.5 leading-tight">
                            {book.title}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex-1 space-y-4 min-w-0">
                    <div className="space-y-1">
                      <h2 className="text-xl md:text-2xl font-black tracking-tight leading-tight truncate">
                        {book.title}
                      </h2>
                      <p className="text-[10px] md:text-xs text-[var(--muted-foreground)] font-medium truncate">
                        Last:{" "}
                        <span className="text-[var(--foreground)]">
                          {book.last_read || "Chapter 1"}
                        </span>
                      </p>
                    </div>

                    <div className="space-y-2 max-w-xs">
                      <div className="flex justify-between items-end">
                        <span className="text-[9px] font-bold text-[var(--muted-foreground)] uppercase tracking-wider">
                          {book.progress}% Done
                        </span>
                      </div>
                      <div className="h-1.5 w-full bg-[var(--secondary)] rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-[var(--primary)] to-[var(--accent)] transition-all duration-1000 ease-out"
                          style={{ width: `${book.progress}%` }}
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-3 pt-1">
                      <Button
                        size="sm"
                        className="rounded-xl px-5 font-bold shadow-lg shadow-[var(--primary)]/20 text-[10px] h-9 cursor-pointer"
                        onClick={() =>
                          handleOpenThread(
                            book.id,
                            book.last_read_id ?? undefined
                          )
                        }
                      >
                        <Play size={14} className="fill-current mr-2" /> RESUME
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="rounded-xl text-[var(--muted-foreground)] hover:text-[var(--foreground)] text-[10px] h-9 cursor-pointer"
                        onClick={() => handleOpenThread(book.id)}
                      >
                        DETAILS
                      </Button>
                    </div>
                  </div>
                </div>
              </section>
            ))}
          </div>
        </div>
      )}

      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-6 pt-2">
        <div className="space-y-1.5">
          <h1 className="text-3xl md:text-4xl font-black text-[var(--foreground)] tracking-tighter">
            Your Library
          </h1>
          <p className="text-[var(--muted-foreground)] font-medium text-sm md:text-base">
            Kelola proyek terjemahan dan pantau progres membaca novel Anda.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative group">
            <Search
              className="absolute left-4 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] group-focus-within:text-[var(--primary)] transition-colors"
              size={18}
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cari judul, pengarang..."
              aria-label="Cari judul atau pengarang"
              className="pl-12 pr-6 py-3 rounded-2xl bg-[var(--card)] border border-[var(--border)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/20 focus:border-[var(--primary)] transition-all min-w-[280px] sm:min-w-[320px] shadow-sm"
            />
          </div>
        </div>
      </header>

      {/* Status Filter Tabs & Sort Controls Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[var(--border)]/60 pb-5">
        {/* Status Filter Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0 no-scrollbar">
          <button
            onClick={() => setActiveTab("all")}
            className={`px-4 py-2.5 rounded-2xl text-xs font-bold transition-all duration-200 flex items-center gap-2 whitespace-nowrap cursor-pointer ${
              activeTab === "all"
                ? "bg-[var(--primary)] text-white shadow-lg shadow-[var(--primary)]/25 ring-2 ring-[var(--primary)]/30"
                : "bg-[var(--secondary)]/70 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)]"
            }`}
          >
            <BookOpen size={14} />
            <span>Semua</span>
            <span
              className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold ${activeTab === "all" ? "bg-white/20 text-white" : "bg-[var(--card)] text-[var(--muted-foreground)]"}`}
            >
              {allCount}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("reading")}
            className={`px-4 py-2.5 rounded-2xl text-xs font-bold transition-all duration-200 flex items-center gap-2 whitespace-nowrap cursor-pointer ${
              activeTab === "reading"
                ? "bg-[var(--primary)] text-white shadow-lg shadow-[var(--primary)]/25 ring-2 ring-[var(--primary)]/30"
                : "bg-[var(--secondary)]/70 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)]"
            }`}
          >
            <Flame
              size={14}
              className={
                activeTab === "reading"
                  ? "text-amber-300 fill-amber-300"
                  : "text-amber-500"
              }
            />
            <span>Sedang Dibaca</span>
            {readingCount > 0 && (
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold ${activeTab === "reading" ? "bg-white/20 text-white" : "bg-amber-500/15 text-amber-500"}`}
              >
                {readingCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("unread")}
            className={`px-4 py-2.5 rounded-2xl text-xs font-bold transition-all duration-200 flex items-center gap-2 whitespace-nowrap cursor-pointer ${
              activeTab === "unread"
                ? "bg-[var(--primary)] text-white shadow-lg shadow-[var(--primary)]/25 ring-2 ring-[var(--primary)]/30"
                : "bg-[var(--secondary)]/70 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)]"
            }`}
          >
            <Sparkles
              size={14}
              className={
                activeTab === "unread" ? "text-cyan-300" : "text-cyan-500"
              }
            />
            <span>Belum Dibaca</span>
            {unreadCount > 0 && (
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold ${activeTab === "unread" ? "bg-white/20 text-white" : "bg-[var(--card)] text-[var(--muted-foreground)]"}`}
              >
                {unreadCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("completed")}
            className={`px-4 py-2.5 rounded-2xl text-xs font-bold transition-all duration-200 flex items-center gap-2 whitespace-nowrap cursor-pointer ${
              activeTab === "completed"
                ? "bg-[var(--primary)] text-white shadow-lg shadow-[var(--primary)]/25 ring-2 ring-[var(--primary)]/30"
                : "bg-[var(--secondary)]/70 text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)]"
            }`}
          >
            <CheckCircle2
              size={14}
              className={
                activeTab === "completed"
                  ? "text-emerald-300"
                  : "text-emerald-500"
              }
            />
            <span>Selesai</span>
            {completedCount > 0 && (
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold ${activeTab === "completed" ? "bg-white/20 text-white" : "bg-emerald-500/15 text-emerald-500"}`}
              >
                {completedCount}
              </span>
            )}
          </button>
        </div>

        {/* Sort Selector */}
        <div className="flex items-center gap-2 self-end sm:self-auto flex-shrink-0">
          <div className="flex items-center gap-2.5 px-3.5 py-2 rounded-2xl bg-[var(--card)] border border-[var(--border)] shadow-sm text-xs font-medium text-[var(--muted-foreground)]">
            <ArrowUpDown size={14} className="text-[var(--primary)]" />
            <span className="text-[10px] font-black uppercase tracking-wider text-[var(--muted-foreground)] hidden md:inline">
              Urutkan:
            </span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortOption)}
              aria-label="Urutkan novel"
              className="bg-transparent text-[var(--foreground)] font-bold text-xs focus:outline-none cursor-pointer pr-1"
            >
              <option
                value="last_read"
                className="bg-[var(--card)] text-[var(--foreground)]"
              >
                Terakhir Dibaca (Default)
              </option>
              <option
                value="recent_added"
                className="bg-[var(--card)] text-[var(--foreground)]"
              >
                Baru Ditambahkan
              </option>
              <option
                value="progress"
                className="bg-[var(--card)] text-[var(--foreground)]"
              >
                Progres Baca (%)
              </option>
              <option
                value="title"
                className="bg-[var(--card)] text-[var(--foreground)]"
              >
                Judul (A-Z)
              </option>
            </select>
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-x-8 gap-y-12">
        {loading
          ? Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="aspect-[3/4] rounded-3xl bg-[var(--secondary)]/50 animate-pulse"
              />
            ))
          : filteredThreads.map((thread) => (
              <LibraryBookCard
                key={thread.id}
                thread={thread}
                actions={{
                  onOpen: (chapterId?: number) =>
                    handleOpenThread(thread.id, chapterId),
                  onDelete: () => handleDelete(thread.id),
                  onBatchTranslate: () => handleOpenBatchModal(thread),
                  onEditCover: () => {
                    setSelectedCoverThread(thread);
                    setIsCoverModalOpen(true);
                  },
                  onScrapeNU: () => {
                    setSelectedScrapeThread(thread);
                    setIsScrapeModalOpen(true);
                  },
                  onCheckHallucinate: () => handleCheckHallucinate(thread),
                  onRunTxtCleaner: () => runCleanerTool(thread, "txt-cleaner"),
                  onRunEpubCleaner: () =>
                    runCleanerTool(thread, "epub-cleaner"),
                  onDeleteTranslations: () => handleDeleteTranslations(thread),
                  onFixTruncated: () => handleFixTruncated(thread),
                  onEditInfo: () => {
                    setEditThread(thread);
                    setEditForm({
                      title: thread.title,
                      genres: thread.genres || "",
                      author: thread.author || "",
                    });
                  },
                }}
              />
            ))}

        {!loading && filteredThreads.length === 0 && (
          <div className="col-span-full py-28 text-center bg-[var(--card)]/50 border-2 border-dashed border-[var(--border)] rounded-[3rem] animate-in zoom-in-95 duration-500">
            <div className="inline-flex p-6 rounded-full bg-[var(--secondary)]/50 mb-6">
              {activeTab === "reading" ? (
                <Flame className="w-12 h-12 text-amber-500 opacity-60" />
              ) : activeTab === "completed" ? (
                <CheckCircle2 className="w-12 h-12 text-emerald-500 opacity-60" />
              ) : activeTab === "unread" ? (
                <Sparkles className="w-12 h-12 text-cyan-500 opacity-60" />
              ) : (
                <BookOpen className="w-12 h-12 text-[var(--muted-foreground)] opacity-30" />
              )}
            </div>
            <h2 className="text-2xl md:text-3xl font-black text-[var(--foreground)] mb-3">
              {searchQuery
                ? `Tidak ada novel yang cocok dengan "${searchQuery}"`
                : activeTab === "reading"
                  ? "Belum Ada Novel yang Sedang Dibaca"
                  : activeTab === "unread"
                    ? "Semua Novel Sudah Pernah Dibuka"
                    : activeTab === "completed"
                      ? "Belum Ada Novel yang Selesai"
                      : "Library is Empty"}
            </h2>
            <p className="text-[var(--muted-foreground)] font-medium max-w-md mx-auto mb-8 leading-relaxed text-sm">
              {searchQuery
                ? "Coba gunakan kata kunci pencarian yang lain atau periksa kembali ejaan judul."
                : activeTab === "reading"
                  ? 'Pilih dan buka novel dari tab "Belum Dibaca" atau "Semua" untuk mulai membaca.'
                  : activeTab === "unread"
                    ? "Semua novel di perpustakaan memiliki progres baca aktif atau telah selesai."
                    : activeTab === "completed"
                      ? "Novel dengan progres 100% akan otomatis terkumpul di sini."
                      : "Start by translating a URL or uploading an EPUB to build your personal collection."}
            </p>
            {activeTab !== "all" || searchQuery ? (
              <Button
                variant="outline"
                size="lg"
                className="rounded-2xl px-8 font-bold shadow-sm"
                onClick={() => {
                  setActiveTab("all");
                  setSearchQuery("");
                }}
              >
                Reset Filter
              </Button>
            ) : (
              <Button
                size="lg"
                className="rounded-2xl px-12 font-bold shadow-lg"
                onClick={() => (window.location.hash = "#translate")}
              >
                Go to Translate
              </Button>
            )}
          </div>
        )}
      </div>
      {selectedBatchThread && (
        <BulkTranslateModal
          isOpen={isBatchModalOpen}
          onClose={() => setIsBatchModalOpen(false)}
          threadId={selectedBatchThread.id}
          threadTitle={selectedBatchThread.title}
          chapters={selectedBatchThread.chapters || []}
          onStartBatch={handleStartBatch}
        />
      )}

      {selectedCoverThread && (
        <EditCoverModal
          isOpen={isCoverModalOpen}
          onClose={() => {
            setIsCoverModalOpen(false);
            setSelectedCoverThread(null);
          }}
          threadId={selectedCoverThread.id}
          threadTitle={selectedCoverThread.title}
          currentCover={selectedCoverThread.cover_image || null}
          onSave={handleSaveCover}
        />
      )}

      {selectedScrapeThread && (
        <ScrapeNUModal
          isOpen={isScrapeModalOpen}
          onClose={() => {
            setIsScrapeModalOpen(false);
            setSelectedScrapeThread(null);
          }}
          threadId={selectedScrapeThread.id}
          threadTitle={selectedScrapeThread.title}
          threadOriginalTitle={selectedScrapeThread.original_title || null}
          onScrapeSuccess={fetchThreads}
        />
      )}

      {auditThread && (
        <div className="fixed inset-0 z-[120] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-4xl max-h-[85vh] overflow-hidden rounded-[2rem] border border-[var(--border)] bg-[var(--card)] shadow-2xl">
            <div className="flex items-start justify-between gap-4 p-6 border-b border-[var(--border)]">
              <div>
                <h2 className="text-2xl font-black tracking-tight text-[var(--foreground)]">
                  Hallucination Audit
                </h2>
                <p className="text-sm text-[var(--muted-foreground)] mt-1">
                  {auditThread.title}
                </p>
              </div>
              <button
                onClick={() => {
                  setAuditThread(null);
                  setAuditResult(null);
                  setAuditError("");
                }}
                className="p-2 rounded-xl text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)] transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-6 overflow-y-auto max-h-[calc(85vh-96px)] space-y-5">
              {auditLoading && (
                <div className="py-16 text-center">
                  <Loader2
                    size={28}
                    className="animate-spin mx-auto text-[var(--primary)] mb-4"
                  />
                  <p className="text-sm text-[var(--muted-foreground)]">
                    Scanning repeated-word hallucination across thread
                    chapters...
                  </p>
                </div>
              )}

              {!auditLoading && auditError && (
                <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-300">
                  {auditError}
                </div>
              )}

              {!auditLoading && auditResult && (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="rounded-2xl border border-[var(--border)] bg-[var(--secondary)]/40 p-4">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted-foreground)] font-black">
                        Checked
                      </div>
                      <div className="text-3xl font-black mt-2">
                        {auditResult.checked_chapters}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-[var(--border)] bg-[var(--secondary)]/40 p-4">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted-foreground)] font-black">
                        Flagged
                      </div>
                      <div className="text-3xl font-black mt-2 text-amber-400">
                        {auditResult.flagged_chapters}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-[var(--border)] bg-[var(--secondary)]/40 p-4">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-[var(--muted-foreground)] font-black">
                        Threshold
                      </div>
                      <div className="text-3xl font-black mt-2">
                        {auditResult.repetition_threshold}x
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {auditResult.chapters.map((chapter) => (
                      <div
                        key={chapter.chapter_id}
                        className="rounded-2xl border border-[var(--border)] bg-[var(--background)]/70 p-4"
                      >
                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                          <div>
                            <h3 className="font-bold text-[var(--foreground)]">
                              Ch {chapter.chapter_order}:{" "}
                              {chapter.chapter_title || "Untitled"}
                            </h3>
                            <p className="text-xs text-[var(--muted-foreground)] mt-1">
                              {chapter.status === "no_translation"
                                ? "No translated text to audit."
                                : chapter.has_repetition
                                  ? `${chapter.match_count} repetition pattern detected.`
                                  : "No repeated-word hallucination found."}
                            </p>
                          </div>
                          <div className="shrink-0">
                            {chapter.status === "flagged" && (
                              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20 text-xs font-black uppercase tracking-wider">
                                <AlertTriangle size={14} /> Flagged
                              </span>
                            )}
                            {chapter.status === "clean" && (
                              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 text-xs font-black uppercase tracking-wider">
                                <CheckCircle2 size={14} /> Clean
                              </span>
                            )}
                            {chapter.status === "no_translation" && (
                              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-500/10 text-slate-300 border border-slate-500/20 text-xs font-black uppercase tracking-wider">
                                <FileText size={14} /> Empty
                              </span>
                            )}
                          </div>
                        </div>

                        {chapter.repetition_matches.length > 0 && (
                          <div className="mt-4 space-y-3">
                            {chapter.repetition_matches.map((match, index) => (
                              <div
                                key={`${chapter.chapter_id}-${index}`}
                                className="rounded-xl border border-amber-500/15 bg-amber-500/5 p-3"
                              >
                                <div className="text-xs font-black text-amber-300 uppercase tracking-wider">
                                  "{match.token}" repeated {match.count}x
                                </div>
                                <div className="mt-2 text-xs text-[var(--muted-foreground)] whitespace-pre-wrap break-words">
                                  {match.snippet}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit Info Modal */}
      {editThread && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setEditThread(null)}
        >
          <div
            className="bg-[var(--card)] border border-[var(--border)] rounded-3xl p-6 w-full max-w-md shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-black text-[var(--foreground)]">
                Edit Book Info
              </h2>
              <button
                onClick={() => setEditThread(null)}
                className="text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              >
                <X size={20} />
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider mb-1.5">
                  Title
                </label>
                <input
                  type="text"
                  value={editForm.title}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, title: e.target.value }))
                  }
                  className="w-full px-3 py-2 rounded-xl bg-[var(--secondary)] border border-[var(--border)] text-[var(--foreground)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/50"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider mb-1.5">
                  Genres (comma separated)
                </label>
                <input
                  type="text"
                  value={editForm.genres}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, genres: e.target.value }))
                  }
                  placeholder="e.g. romance, cultivation, urban"
                  className="w-full px-3 py-2 rounded-xl bg-[var(--secondary)] border border-[var(--border)] text-[var(--foreground)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/50"
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-[var(--muted-foreground)] uppercase tracking-wider mb-1.5">
                  Author
                </label>
                <input
                  type="text"
                  value={editForm.author}
                  onChange={(e) =>
                    setEditForm((f) => ({ ...f, author: e.target.value }))
                  }
                  className="w-full px-3 py-2 rounded-xl bg-[var(--secondary)] border border-[var(--border)] text-[var(--foreground)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]/50"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-6">
              <Button
                variant="outline"
                className="rounded-xl"
                onClick={() => setEditThread(null)}
              >
                Cancel
              </Button>
              <Button
                className="rounded-xl"
                disabled={editSaving || !editForm.title.trim()}
                onClick={async () => {
                  setEditSaving(true);
                  try {
                    const res = await fetch(
                      getApiUrl(`/api/threads/${editThread.id}`),
                      {
                        method: "PATCH",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          title: editForm.title.trim(),
                          genres: editForm.genres.trim() || null,
                          author: editForm.author.trim() || null,
                        }),
                      }
                    );
                    if (!res.ok) throw new Error("Failed");
                    toast.success("Book info updated!");
                    setEditThread(null);
                    fetchThreads();
                  } catch {
                    toast.error("Failed to update book info");
                  } finally {
                    setEditSaving(false);
                  }
                }}
              >
                {editSaving ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  "Save"
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
