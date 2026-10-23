/* eslint-disable react-hooks/set-state-in-effect */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import {
  X,
  Plus,
  BookOpen,
  Globe,
  FileText,
  Sparkles,
  Loader2,
  Search,
  Filter,
  Trash2,
  Lock,
  Unlock,
  Settings2,
  Zap,
  Edit2,
  RefreshCw,
  Archive,
  ArchiveRestore,
  CheckSquare,
  Square,
  Download,
  Upload,
  ArrowUpDown,
  LayoutGrid,
  List,
  AlertTriangle,
  ShieldCheck,
  Check,
  Users,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getApiUrl, invalidateThreadCache } from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import RelationshipGraph, {
  type Relationship,
} from "@/components/RelationshipGraph";

export interface LorebookEntry {
  id: number;
  thread_id?: number;
  original_term: string;
  translated_term: string;
  notes?: string | null;
  gender?: "MALE" | "FEMALE" | null;
  auto_extracted?: boolean;
  is_locked?: boolean;
  is_archived?: boolean;
  usage_count?: number;
  last_used_at?: string | null;
  created_at?: string | null;
}

interface ThreadItem {
  id: number;
  title: string;
  author?: string;
  chapter_count?: number;
  translations_count?: number;
}

interface ExtractedTerm {
  original_term: string;
  translated_term?: string;
  notes?: string;
  gender?: "MALE" | "FEMALE" | null;
}

type StatusFilter = "all" | "active" | "locked" | "archived" | "auto";
type GenderFilter = "all" | "male" | "female" | "genderless";
type SortMode = "id" | "usage" | "orig_az" | "trans_az" | "locked_first";
type ViewMode = "grid" | "table";

const CONTEXT_LIMIT_OPTIONS = [20, 50, 100, 150, 200, 300, 500, 750, 1000];

const STYLE_TEMPLATES = [
  {
    title: "Pertahankan Honorifik Mandarin (Shixiong / Shizun)",
    category: "Style Guide",
    text: "Pertahankan sapaan kultivasi seperti Shixiong (Kakak Senior), Shijie, Shidi, Shimei, dan Shizun/Shifu secara konsisten. Gunakan Bahasa Indonesia sastra yang mengalir alami dan tidak kaku.",
  },
  {
    title: "Terjemahkan Nama Sekte & Jurus ke Bahasa Indonesia",
    category: "Style Guide",
    text: "Terjemahkan nama sekte, jurus bela diri, pil, dan pusaka ke Bahasa Indonesia yang epik (contoh: Sekte Awan Biru, Pil Pemurnian Roh), namun pertahankan nama tokoh dalam Pinyin asli.",
  },
  {
    title: "Gaya Bahasa Light Novel Modern (Santai & Ekspresif)",
    category: "Style Guide",
    text: 'Gunakan diksi novel ringan modern yang luwes. Gunakan "aku/kamu" untuk dialog sebaya dan "Anda/Beliau" untuk tokoh senior atau bangsawan.',
  },
  {
    title: "Strict Line-by-Line Paragraph Fidelity",
    category: "Global Rule",
    text: "Pertahankan struktur paragraf 1:1 sesuai teks asli. Jangan menggabungkan atau memecah paragraf dialog, dan jangan menambahkan catatan di tengah cerita.",
  },
];

const apiJson = (path: string, body?: any, method = "POST") =>
  fetch(getApiUrl(path), {
    method,
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

const pillCls = (
  active: boolean,
  activeExtra = "bg-[var(--primary)] text-white border-[var(--primary)] shadow-sm"
) =>
  cn(
    "px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border shrink-0 cursor-pointer",
    active
      ? activeExtra
      : "bg-[var(--card)] text-[var(--muted-foreground)] border-[var(--border)] hover:text-[var(--foreground)]"
  );

function getEntryGender(entry: LorebookEntry): "MALE" | "FEMALE" | null {
  if (entry.gender === "MALE" || entry.gender === "FEMALE") return entry.gender;
  if (!entry.notes) return null;
  const m = entry.notes.match(/\b(MALE|FEMALE)\b\s*[\u2014\u2013\-\ufffd—–-]/i);
  return m ? (m[1].toUpperCase() as "MALE" | "FEMALE") : null;
}

function TermGridCard({
  entry,
  isSelected,
  onSelect,
  onCycleGender,
  onToggleLock,
  onToggleArchive,
  onEdit,
  onDelete,
}: {
  entry: LorebookEntry;
  isSelected: boolean;
  onSelect: (id: number) => void;
  onCycleGender: (e: LorebookEntry) => void;
  onToggleLock: (e: LorebookEntry) => void;
  onToggleArchive: (e: LorebookEntry) => void;
  onEdit: (e: LorebookEntry) => void;
  onDelete: (id: number) => void;
}) {
  const g = getEntryGender(entry);
  const cardTone = entry.is_archived
    ? "opacity-70 bg-[var(--secondary)]/20 border-dashed border-[var(--border)]"
    : isSelected
      ? "border-[var(--primary)] bg-[var(--primary)]/5"
      : "hover:border-[var(--primary)]/50 border-[var(--border)]";
  const avatarTone =
    g === "MALE"
      ? "bg-blue-500/15 border-2 border-blue-500/40 text-blue-500"
      : g === "FEMALE"
        ? "bg-pink-500/15 border-2 border-pink-500/40 text-pink-500"
        : "bg-[var(--accent)] border border-[var(--border)] text-[var(--primary)]";

  return (
    <Card
      className={cn(
        "group transition-all duration-200 shadow-sm hover:shadow-md relative overflow-hidden border",
        cardTone
      )}
    >
      <CardContent className="p-5">
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => onSelect(entry.id)}
              className="text-[var(--muted-foreground)] hover:text-[var(--primary)] cursor-pointer"
              title="Pilih istilah"
            >
              {isSelected ? (
                <CheckSquare size={16} className="text-[var(--primary)]" />
              ) : (
                <Square size={16} />
              )}
            </button>
            <button
              type="button"
              onClick={() => onCycleGender(entry)}
              className="relative group/avatar cursor-pointer text-left focus:outline-none"
              title="Klik untuk ubah gender (♂ / ♀ / Netral)"
            >
              <div
                className={cn(
                  "w-10 h-10 rounded-xl flex items-center justify-center font-bold text-base transition-transform group-hover/avatar:scale-105",
                  avatarTone
                )}
              >
                {entry.original_term.charAt(0)}
              </div>
              {g && (
                <span
                  className={cn(
                    "absolute -bottom-1 -right-1 w-4 h-4 rounded-full text-white flex items-center justify-center text-[10px] font-black ring-2 ring-[var(--card)]",
                    g === "MALE" ? "bg-blue-600" : "bg-pink-600"
                  )}
                >
                  {g === "MALE" ? "♂" : "♀"}
                </span>
              )}
            </button>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => onToggleLock(entry)}
              className={cn(
                "p-1.5 rounded-lg transition-all cursor-pointer",
                entry.is_locked
                  ? "bg-amber-500/15 text-amber-500 border border-amber-500/30"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)]"
              )}
              title={
                entry.is_locked
                  ? "Terkunci. Klik untuk membuka."
                  : "Kunci istilah agar selalu aktif"
              }
            >
              <Lock size={13} />
            </button>
            <button
              onClick={() => onToggleArchive(entry)}
              className={cn(
                "p-1.5 rounded-lg transition-all cursor-pointer",
                entry.is_archived
                  ? "bg-emerald-500/15 text-emerald-500 border border-emerald-500/30"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)]"
              )}
              title={
                entry.is_archived
                  ? "Pulihkan ke glosarium aktif"
                  : "Arsipkan istilah (hemat kuota prompt)"
              }
            >
              {entry.is_archived ? (
                <ArchiveRestore size={13} />
              ) : (
                <Archive size={13} />
              )}
            </button>
            <button
              onClick={() => onEdit(entry)}
              className="p-1.5 text-amber-500 hover:bg-amber-500/15 rounded-lg cursor-pointer"
              title="Edit istilah"
            >
              <Edit2 size={13} />
            </button>
            <button
              onClick={() => onDelete(entry.id)}
              className="p-1.5 text-rose-500 hover:bg-rose-500/15 rounded-lg cursor-pointer"
              title="Hapus istilah"
            >
              <Trash2 size={13} />
            </button>
          </div>
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-bold text-base text-[var(--foreground)] leading-snug">
              {entry.translated_term}
            </h3>
            {entry.is_archived && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-500 border border-amber-500/30">
                📦 Archived
              </span>
            )}
          </div>
          <p className="text-xs font-mono text-[var(--muted-foreground)]">
            {entry.original_term}
          </p>
        </div>

        <div className="mt-3 pt-3 border-t border-[var(--border)] flex flex-col gap-2">
          <p className="text-xs text-[var(--muted-foreground)] line-clamp-2 italic">
            &ldquo;{entry.notes || "Tidak ada catatan konteks."}&rdquo;
          </p>
          <div className="flex items-center justify-between text-[10px] text-[var(--muted-foreground)] pt-1">
            <span className="font-mono">
              Dipakai: <strong>{entry.usage_count || 0}x</strong>
            </span>
            {entry.auto_extracted ? (
              <span className="text-blue-500 font-bold uppercase tracking-tighter flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />{" "}
                Auto-AI
              </span>
            ) : (
              <span className="opacity-70">Manual / Preset</span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function StyleAndRulesTab({
  threadTitle,
  styleGuide,
  setStyleGuide,
  threadContext,
  setThreadContext,
  globalContext,
  setGlobalContext,
  onSaveThread,
  onSaveGlobal,
  isSavingThread,
  isSavingGlobal,
}: {
  threadTitle: string;
  styleGuide: string;
  setStyleGuide: React.Dispatch<React.SetStateAction<string>>;
  threadContext: string;
  setThreadContext: React.Dispatch<React.SetStateAction<string>>;
  globalContext: string;
  setGlobalContext: React.Dispatch<React.SetStateAction<string>>;
  onSaveThread: () => void;
  onSaveGlobal: () => void;
  isSavingThread: boolean;
  isSavingGlobal: boolean;
}) {
  return (
    <div className="space-y-8 max-w-5xl mx-auto pb-10">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-[var(--border)] bg-[var(--card)]/60">
          <CardContent className="p-6 space-y-4">
            <div>
              <h3 className="text-base font-bold text-[var(--foreground)] flex items-center gap-2">
                <Sparkles size={16} className="text-purple-500" /> Novel Style
                Guide (Khusus Novel Ini)
              </h3>
              <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                Aturan nada bicara, POV, honorifik, dan gaya sastra khusus untuk{" "}
                <strong>{threadTitle}</strong>. Sinkron dengan menu Reader.
              </p>
            </div>
            <Textarea
              value={styleGuide}
              onChange={(e) => setStyleGuide(e.target.value)}
              placeholder="Contoh: Gunakan sapaan 'Kakak Senior' untuk Shixiong. Pertahankan suasana kelam dan puitis..."
              className="min-h-[150px] text-sm bg-[var(--background)] border-[var(--border)] rounded-xl"
            />
            <div className="flex items-center justify-between text-[11px] text-[var(--muted-foreground)]">
              <span className="font-mono">{styleGuide.length} karakter</span>
              <Button
                size="sm"
                onClick={onSaveThread}
                disabled={isSavingThread}
                className="rounded-xl gap-1.5 cursor-pointer"
              >
                {isSavingThread && (
                  <Loader2 size={13} className="animate-spin" />
                )}{" "}
                Simpan Style Guide & Lore
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="border-[var(--border)] bg-[var(--card)]/60">
          <CardContent className="p-6 space-y-4">
            <div>
              <h3 className="text-base font-bold text-[var(--foreground)] flex items-center gap-2">
                <BookOpen size={16} className="text-[var(--primary)]" />{" "}
                Ringkasan Lore & Konteks Cerita Novel
              </h3>
              <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                Ringkasan dunia, sistem kultivasi/sihir, dan latar belakang
                cerita yang disuntikkan ke AI saat menerjemahkan.
              </p>
            </div>
            <Textarea
              value={threadContext}
              onChange={(e) => setThreadContext(e.target.value)}
              placeholder="Contoh: Berlatar di Benua Tianxuan. Tokoh utama Lin Dong menemukan Batu Jimat Misterius..."
              className="min-h-[150px] text-sm bg-[var(--background)] border-[var(--border)] rounded-xl"
            />
            <div className="flex items-center justify-between text-[11px] text-[var(--muted-foreground)]">
              <span className="font-mono">{threadContext.length} karakter</span>
              <Button
                size="sm"
                variant="outline"
                onClick={onSaveThread}
                disabled={isSavingThread}
                className="rounded-xl gap-1.5 cursor-pointer"
              >
                {isSavingThread && (
                  <Loader2 size={13} className="animate-spin" />
                )}{" "}
                Simpan Ringkasan Lore
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <section className="space-y-3">
        <div>
          <h3 className="text-sm font-bold text-[var(--foreground)]">
            Template Aturan Cepat (Klik untuk Sisipkan)
          </h3>
          <p className="text-xs text-[var(--muted-foreground)]">
            Sisipkan konvensi terjemahan langsung ke Style Guide novel ini atau
            Instruksi Global.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {STYLE_TEMPLATES.map((tpl, idx) => (
            <div
              key={idx}
              className="p-4 rounded-2xl border border-[var(--border)] bg-[var(--card)]/40 hover:border-[var(--primary)]/40 transition-all flex flex-col justify-between gap-3"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="font-bold text-xs text-[var(--foreground)]">
                    {tpl.title}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--secondary)] text-[var(--muted-foreground)] font-semibold">
                    {tpl.category}
                  </span>
                </div>
                <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">
                  {tpl.text}
                </p>
              </div>
              <div className="flex items-center gap-2 pt-1">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setStyleGuide((prev) =>
                      prev.trim()
                        ? `${prev.trim()}\n- ${tpl.text}`
                        : `- ${tpl.text}`
                    );
                    toast.info(
                      "Disisipkan ke Novel Style Guide (klik Simpan untuk menerapkan)"
                    );
                  }}
                  className="h-7 text-[11px] rounded-lg gap-1 cursor-pointer"
                >
                  <Plus size={12} /> Ke Style Guide Novel
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setGlobalContext((prev) =>
                      prev.trim()
                        ? `${prev.trim()}\n- ${tpl.text}`
                        : `- ${tpl.text}`
                    );
                    toast.info(
                      "Disisipkan ke Instruksi Global (klik Simpan untuk menerapkan)"
                    );
                  }}
                  className="h-7 text-[11px] rounded-lg gap-1 cursor-pointer"
                >
                  <Globe size={12} /> Ke Instruksi Global
                </Button>
              </div>
            </div>
          ))}
        </div>
      </section>

      <Card className="border-[var(--border)] bg-[var(--card)]/40">
        <CardContent className="p-6 space-y-4">
          <div>
            <h3 className="text-base font-bold text-[var(--foreground)] flex items-center gap-2">
              <Globe size={16} className="text-[var(--primary)]" /> Global
              Translation Instructions (Berlaku untuk Semua Novel)
            </h3>
            <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
              Instruksi dasar yang selalu disertakan di seluruh novel pada
              workspace ini.
            </p>
          </div>
          <Textarea
            value={globalContext}
            onChange={(e) => setGlobalContext(e.target.value)}
            placeholder="Contoh: Terjemahkan secara akurat baris demi baris ke Bahasa Indonesia yang alami..."
            className="min-h-[120px] text-sm bg-[var(--background)] border-[var(--border)] rounded-xl"
          />
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono text-[var(--muted-foreground)]">
              {globalContext.length} karakter (Batas dinamis model: 1.500–12.000
              karakter)
            </span>
            <Button
              size="sm"
              onClick={onSaveGlobal}
              disabled={isSavingGlobal}
              className="rounded-xl gap-1.5 cursor-pointer"
            >
              {isSavingGlobal && <Loader2 size={13} className="animate-spin" />}{" "}
              Simpan Instruksi Global
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function ContextLibraryPage() {
  const [threads, setThreads] = useState<ThreadItem[]>([]);
  const [selectedThreadId, setSelectedThreadId] = useState<number | null>(null);
  const [activeSubTab, setActiveSubTab] = useState<
    "glossary" | "context" | "relationships"
  >("glossary");

  // Synchronized Global Settings State
  const [targetLanguage, setTargetLanguage] = useState<string>(
    () => localStorage.getItem("target_language") || "Indonesian"
  );
  const [translationMode, setTranslationMode] = useState<"quality" | "fast">(
    () =>
      (localStorage.getItem("translation_mode") as "quality" | "fast") ||
      "quality"
  );
  const [maxContextTerms, setMaxContextTerms] = useState<number>(
    () =>
      parseInt(localStorage.getItem("max_context_terms") || "150", 10) || 150
  );
  const [activeProvider, setActiveProvider] = useState<string>(
    () => localStorage.getItem("llm_provider") || "lm_studio"
  );

  // Contexts & Style Guide
  const [globalContext, setGlobalContext] = useState("");
  const [threadContext, setThreadContext] = useState("");
  const [styleGuide, setStyleGuide] = useState("");
  const [isSavingGlobal, setIsSavingGlobal] = useState(false);
  const [isSavingThreadCtx, setIsSavingThreadCtx] = useState(false);

  // Glossary State
  const [entries, setEntries] = useState<LorebookEntry[]>([]);
  const [isLoadingEntries, setIsLoadingEntries] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [genderFilter, setGenderFilter] = useState<GenderFilter>("all");
  const [sortMode, setSortMode] = useState<SortMode>("id");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [visibleCount, setVisibleCount] = useState(60);

  // Multi-select & Bulk Actions
  const [selectedEntryIds, setSelectedEntryIds] = useState<Set<number>>(
    new Set()
  );
  const [isBulkProcessing, setIsBulkProcessing] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importText, setImportText] = useState("");

  // Add / Edit Entry Form
  const [showAddForm, setShowAddForm] = useState(false);
  const [newEntry, setNewEntry] = useState({
    original: "",
    translated: "",
    notes: "",
    gender: "",
    is_locked: false,
  });
  const [editingEntryId, setEditingEntryId] = useState<number | null>(null);

  // AI Extract State
  const [isExtracting, setIsExtracting] = useState(false);
  const [suggestions, setSuggestions] = useState<ExtractedTerm[]>([]);
  const [aiReasoning, setAiReasoning] = useState<string>("");
  const [showAiReasoning, setShowAiReasoning] = useState(false);
  const [extractMode, setExtractMode] = useState<"easy" | "advanced">("easy");
  const [extractSettings, setExtractSettings] = useState({
    chapterCount: 25,
    sampleSize: 1000,
  });
  const [showExtractSettings, setShowExtractSettings] = useState(false);

  // Genre Presets State
  const [presets, setPresets] = useState<
    { key: string; name: string; description: string; entry_count: number }[]
  >([]);
  const [showPresetsModal, setShowPresetsModal] = useState(false);
  const [presetLanguage, setPresetLanguage] = useState<
    "Indonesian" | "English"
  >("Indonesian");
  const [presetLockEntries, setPresetLockEntries] = useState<boolean>(false);
  const [isApplyingPreset, setIsApplyingPreset] = useState<string | null>(null);
  const [isReapplyingAll, setIsReapplyingAll] = useState(false);

  // Relationships State
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [isScanningRels, setIsScanningRels] = useState(false);

  const formRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setVisibleCount(60);
    setSelectedEntryIds(new Set());
  }, [searchQuery, statusFilter, genderFilter, selectedThreadId]);

  useEffect(() => {
    if (showAddForm && formRef.current) {
      formRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [showAddForm]);

  // Thread whose data is on screen. Responses for any other thread are stale: switching A -> B
  // quickly must not show A's glossary under B, nor let "Save" write A's context into B.
  const activeThreadIdRef = useRef<number | null>(null);

  const fetchLorebook = useCallback(async (threadId: number) => {
    setIsLoadingEntries(true);
    try {
      const res = await fetch(
        getApiUrl(`/api/threads/${threadId}/lorebook?include_archived=true`)
      );
      if (!res.ok) throw new Error("Failed to load lorebook");
      const data = await res.json();
      if (activeThreadIdRef.current !== threadId) return;
      setEntries(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("Failed to fetch lorebook", e);
    } finally {
      if (activeThreadIdRef.current === threadId) setIsLoadingEntries(false);
    }
  }, []);

  const fetchThreadContextAndStyle = useCallback(async (threadId: number) => {
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/context`));
      if (!res.ok) return;
      const data = await res.json();
      if (activeThreadIdRef.current !== threadId) return;
      setThreadContext(data.thread_context || "");
      setStyleGuide(data.style_guide || "");
    } catch (e) {
      console.error("Failed to fetch thread context", e);
    }
  }, []);

  const fetchRelationships = useCallback(async (threadId: number) => {
    try {
      const res = await fetch(
        getApiUrl(`/api/threads/${threadId}/relationships`)
      );
      if (!res.ok) return;
      const data = await res.json();
      if (activeThreadIdRef.current !== threadId) return;
      setRelationships(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("Failed to fetch relationships", e);
    }
  }, []);

  useEffect(() => {
    fetch(getApiUrl("/api/threads"))
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setThreads(data);
          if (data.length > 0) setSelectedThreadId(data[0].id);
        }
      })
      .catch((e) => console.error("Failed to fetch threads", e));

    fetch(getApiUrl("/api/settings"))
      .then((res) => res.json())
      .then((data) => {
        setGlobalContext(data.global_context || "");
        if (data.target_language) {
          setTargetLanguage(data.target_language);
          setPresetLanguage(
            data.target_language === "English" ? "English" : "Indonesian"
          );
          localStorage.setItem("target_language", data.target_language);
        }
        if (data.translation_mode) {
          setTranslationMode(data.translation_mode);
          localStorage.setItem("translation_mode", data.translation_mode);
        }
        if (data.max_context_terms) {
          setMaxContextTerms(Number(data.max_context_terms));
          localStorage.setItem(
            "max_context_terms",
            String(data.max_context_terms)
          );
        }
        if (data.llm_provider) setActiveProvider(data.llm_provider);
        if (data.extract_chapter_count && data.extract_sample_size) {
          setExtractSettings({
            chapterCount: data.extract_chapter_count,
            sampleSize: data.extract_sample_size,
          });
        }
      })
      .catch((e) => console.error("Failed to fetch global settings", e));

    fetch(getApiUrl("/api/presets"))
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data)) setPresets(data);
      })
      .catch((e) => console.error("Failed to fetch presets", e));
  }, []);

  useEffect(() => {
    activeThreadIdRef.current = selectedThreadId;
    // Drop the previous thread's data at once, so nothing of it can be shown or saved under
    // the new thread while its own data loads.
    setEntries([]);
    setThreadContext("");
    setStyleGuide("");
    setSuggestions([]);
    setRelationships([]);
    setEditingEntryId(null);
    setShowAddForm(false);
    if (!selectedThreadId) {
      setIsLoadingEntries(false);
      return;
    }
    fetchLorebook(selectedThreadId);
    fetchThreadContextAndStyle(selectedThreadId);
    fetchRelationships(selectedThreadId);
  }, [
    selectedThreadId,
    fetchLorebook,
    fetchThreadContextAndStyle,
    fetchRelationships,
  ]);

  const handleUpdateGlobalSetting = async (updates: Record<string, any>) => {
    try {
      const res = await apiJson("/api/settings", updates);
      if (!res.ok) throw new Error("Gagal menyimpan pengaturan");
      if (updates.translation_mode) {
        setTranslationMode(updates.translation_mode);
        localStorage.setItem("translation_mode", updates.translation_mode);
        toast.success(
          `Mode terjemahan diubah ke ${updates.translation_mode === "quality" ? "Quality Mode" : "Fast Mode"}`
        );
      }
      if (updates.max_context_terms) {
        const lim = Number(updates.max_context_terms);
        setMaxContextTerms(lim);
        localStorage.setItem("max_context_terms", String(lim));
        if (selectedThreadId) await fetchLorebook(selectedThreadId);
        toast.success(
          `Batas kuota glosarium aktif disinkronkan ke ${lim} istilah!`
        );
      }
      if (updates.target_language) {
        setTargetLanguage(updates.target_language);
        setPresetLanguage(
          updates.target_language === "English" ? "English" : "Indonesian"
        );
        localStorage.setItem("target_language", updates.target_language);
        toast.success(`Bahasa target diubah ke ${updates.target_language}`);
      }
    } catch (e: any) {
      toast.error(e.message || "Gagal memperbarui pengaturan");
    }
  };

  const handleReapplyGlossaryAll = async () => {
    if (!selectedThreadId) return;
    setIsReapplyingAll(true);
    try {
      const res = await apiJson(
        `/api/threads/${selectedThreadId}/reapply-glossary`
      );
      if (!res.ok) throw new Error("Gagal menyinkronkan glosarium");
      const data = await res.json();
      invalidateThreadCache(selectedThreadId);
      toast.success(
        `Glosarium berhasil disinkronkan ke ${data.chapters_updated} dari ${data.total_chapters} bab & judul! (0 token)`
      );
    } catch (err) {
      console.error(err);
      toast.error("Gagal menerapkan glosarium ke bab");
    } finally {
      setIsReapplyingAll(false);
    }
  };

  const saveGlobalInstructions = async () => {
    setIsSavingGlobal(true);
    try {
      const res = await apiJson("/api/global-context", {
        context: globalContext,
      });
      if (!res.ok) throw new Error("Gagal menyimpan instruksi global");
      toast.success("Instruksi terjemahan global berhasil disimpan!");
    } catch (e: any) {
      toast.error(e.message || "Gagal menyimpan instruksi global");
    } finally {
      setIsSavingGlobal(false);
    }
  };

  const saveThreadRulesAndStyle = async () => {
    if (!selectedThreadId) return;
    setIsSavingThreadCtx(true);
    try {
      const res = await apiJson(`/api/threads/${selectedThreadId}/context`, {
        context: threadContext,
        thread_context: threadContext,
        style_guide: styleGuide,
      });
      if (!res.ok) throw new Error("Gagal menyimpan konteks novel");
      invalidateThreadCache(selectedThreadId);
      toast.success("Style Guide & Lore Context novel berhasil disimpan!");
    } catch (e: any) {
      toast.error(e.message || "Gagal menyimpan konteks novel");
    } finally {
      setIsSavingThreadCtx(false);
    }
  };

  const addOrUpdateEntry = async () => {
    if (
      !newEntry.original.trim() ||
      !newEntry.translated.trim() ||
      !selectedThreadId
    ) {
      toast.error("Istilah asli dan terjemahan wajib diisi!");
      return;
    }
    try {
      const isEdit = editingEntryId !== null;
      const path = isEdit
        ? `/api/lorebook/${editingEntryId}`
        : `/api/threads/${selectedThreadId}/lorebook`;
      const res = await apiJson(
        path,
        {
          original_term: newEntry.original.trim(),
          translated_term: newEntry.translated.trim(),
          notes: newEntry.notes.trim() || undefined,
          gender: newEntry.gender || undefined,
          is_locked: newEntry.is_locked,
          is_archived: false,
        },
        isEdit ? "PUT" : "POST"
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal menyimpan istilah");

      await fetchLorebook(selectedThreadId);
      if (!isEdit) {
        setSuggestions((prev) =>
          prev.filter(
            (sug) =>
              sug.original_term.trim().toLowerCase() !==
              newEntry.original.trim().toLowerCase()
          )
        );
      }
      setNewEntry({
        original: "",
        translated: "",
        notes: "",
        gender: "",
        is_locked: false,
      });
      setEditingEntryId(null);
      setShowAddForm(false);
      toast.success(
        isEdit ? "Istilah diperbarui!" : "Istilah ditambahkan ke glosarium!"
      );
    } catch (e: any) {
      toast.error(e.message || "Gagal menyimpan istilah");
    }
  };

  const quickAddEntry = async (
    sug: ExtractedTerm,
    isLocked: boolean = false
  ) => {
    if (!sug.original_term.trim() || !selectedThreadId) return;
    try {
      const res = await apiJson(`/api/threads/${selectedThreadId}/lorebook`, {
        original_term: sug.original_term.trim(),
        translated_term: (sug.translated_term || "").trim(),
        notes: sug.notes || undefined,
        gender: sug.gender || undefined,
        is_locked: isLocked,
      });
      if (!res.ok) throw new Error("Gagal menambahkan saran");
      await fetchLorebook(selectedThreadId);
      setSuggestions((prev) =>
        prev.filter(
          (s) =>
            s.original_term.toLowerCase() !== sug.original_term.toLowerCase()
        )
      );
      toast.success(
        `"${sug.translated_term || sug.original_term}" ditambahkan${isLocked ? " & dikunci" : ""}!`
      );
    } catch (e: any) {
      toast.error(e.message || "Gagal menambahkan saran");
    }
  };

  const handleBulkAcceptSuggestions = async (lockAll: boolean = false) => {
    if (!selectedThreadId || suggestions.length === 0) return;
    setIsBulkProcessing(true);
    try {
      const payload = suggestions
        .filter((s) => s.original_term && s.translated_term)
        .map((s) => ({
          original_term: s.original_term.trim(),
          translated_term: (s.translated_term || "").trim(),
          notes: s.notes || undefined,
          gender: s.gender || undefined,
          is_locked: lockAll,
          is_archived: false,
        }));
      const res = await apiJson(
        `/api/threads/${selectedThreadId}/lorebook/bulk`,
        { action: "import", entries: payload }
      );
      if (!res.ok) throw new Error("Gagal menyimpan semua saran");
      const data = await res.json();
      setSuggestions([]);
      await fetchLorebook(selectedThreadId);
      toast.success(
        `Berhasil menerima ${data.affected || payload.length} saran AI ke glosarium!`
      );
    } catch (e: any) {
      toast.error(e.message || "Gagal menerima saran secara massal");
    } finally {
      setIsBulkProcessing(false);
    }
  };

  const toggleLock = async (entry: LorebookEntry) => {
    try {
      const res = await apiJson(`/api/lorebook/${entry.id}/lock`, {
        is_locked: !entry.is_locked,
      });
      if (!res.ok) throw new Error("Gagal mengubah status kunci");
      const data = await res.json();
      setEntries((prev) =>
        prev.map((e) =>
          e.id === entry.id
            ? { ...e, is_locked: data.is_locked, is_archived: data.is_archived }
            : e
        )
      );
    } catch (e) {
      console.error("Failed to toggle lock", e);
      toast.error("Gagal mengubah status kunci");
    }
  };

  const toggleArchive = async (entry: LorebookEntry) => {
    try {
      const nextArchived = !entry.is_archived;
      const res = await apiJson(`/api/lorebook/${entry.id}/archive`, {
        is_archived: nextArchived,
      });
      if (!res.ok) throw new Error("Gagal mengubah status arsip");
      const data = await res.json();
      setEntries((prev) =>
        prev.map((e) =>
          e.id === entry.id
            ? { ...e, is_archived: data.is_archived, is_locked: data.is_locked }
            : e
        )
      );
      toast.success(
        nextArchived
          ? `"${entry.translated_term}" diarsipkan (tidak memakan kuota prompt)`
          : `"${entry.translated_term}" dipulihkan ke glosarium aktif!`
      );
    } catch (e) {
      console.error("Failed to toggle archive", e);
      toast.error("Gagal mengubah status arsip");
    }
  };

  const handleCycleGender = async (entry: LorebookEntry) => {
    const current = getEntryGender(entry);
    const nextGender: "MALE" | "FEMALE" | null =
      current === null ? "MALE" : current === "MALE" ? "FEMALE" : null;
    try {
      const res = await apiJson(
        `/api/lorebook/${entry.id}`,
        {
          original_term: entry.original_term,
          translated_term: entry.translated_term,
          notes: entry.notes || undefined,
          gender: nextGender === null ? "" : nextGender,
          is_locked: entry.is_locked,
          is_archived: entry.is_archived,
        },
        "PUT"
      );
      if (!res.ok) throw new Error("Failed to update gender");
      const data = await res.json();
      setEntries((prev) =>
        prev.map((e) => (e.id === entry.id ? { ...e, gender: data.gender } : e))
      );
      toast.success(
        nextGender === "MALE"
          ? `"${entry.translated_term}" diset ke ♂ Laki-laki`
          : nextGender === "FEMALE"
            ? `"${entry.translated_term}" diset ke ♀ Perempuan`
            : `"${entry.translated_term}" diset ke Netral/Benda`
      );
    } catch (err) {
      console.error("Failed to cycle gender", err);
      toast.error("Gagal mengubah gender");
    }
  };

  const startEditing = (entry: LorebookEntry) => {
    setNewEntry({
      original: entry.original_term,
      translated: entry.translated_term,
      notes: entry.notes || "",
      gender: entry.gender || "",
      is_locked: Boolean(entry.is_locked),
    });
    setEditingEntryId(entry.id);
    setShowAddForm(true);
  };

  const removeEntry = async (id: number) => {
    if (!selectedThreadId) return;
    try {
      await fetch(getApiUrl(`/api/lorebook/${id}`), { method: "DELETE" });
      await fetchLorebook(selectedThreadId);
      setSelectedEntryIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      toast.success("Istilah dihapus");
    } catch (e) {
      console.error("Failed to remove entry", e);
      toast.error("Gagal menghapus istilah");
    }
  };

  const executeBulkAction = async (
    action:
      | "lock"
      | "unlock"
      | "archive"
      | "restore"
      | "delete"
      | "clean_garbage"
  ) => {
    if (!selectedThreadId) return;
    const ids = Array.from(selectedEntryIds);
    if (action !== "clean_garbage" && ids.length === 0) {
      toast.error("Pilih minimal 1 istilah terlebih dahulu!");
      return;
    }
    setIsBulkProcessing(true);
    try {
      const res = await apiJson(
        `/api/threads/${selectedThreadId}/lorebook/bulk`,
        {
          action,
          entry_ids: action === "clean_garbage" ? undefined : ids,
        }
      );
      if (!res.ok) throw new Error("Gagal menjalankan aksi massal");
      const data = await res.json();
      await fetchLorebook(selectedThreadId);
      setSelectedEntryIds(new Set());
      if (action === "clean_garbage") {
        toast.success(
          data.affected > 0
            ? `Berhasil membersihkan ${data.affected} entri sampah/rusak!`
            : "Glosarium bersih! Tidak ditemukan entri sampah."
        );
      } else {
        toast.success(
          `Aksi "${action}" berhasil diterapkan ke ${data.affected} istilah!`
        );
      }
    } catch (e: any) {
      toast.error(e.message || "Gagal menjalankan aksi massal");
    } finally {
      setIsBulkProcessing(false);
    }
  };

  const handleExportGlossary = () => {
    if (entries.length === 0) {
      toast.error("Belum ada istilah untuk diekspor.");
      return;
    }
    const exportPayload = entries.map((e) => ({
      original_term: e.original_term,
      translated_term: e.translated_term,
      notes: e.notes || "",
      gender: e.gender || null,
      is_locked: Boolean(e.is_locked),
      is_archived: Boolean(e.is_archived),
    }));
    const blob = new Blob([JSON.stringify(exportPayload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `glossary_thread_${selectedThreadId || "export"}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(
      `Berhasil mengekspor ${exportPayload.length} istilah ke JSON!`
    );
  };

  const handleImportGlossary = async () => {
    if (!selectedThreadId || !importText.trim()) return;
    setIsBulkProcessing(true);
    try {
      let parsedEntries: any[] = [];
      const raw = importText.trim();
      if (raw.startsWith("[") || raw.startsWith("{")) {
        const json = JSON.parse(raw);
        parsedEntries = Array.isArray(json) ? json : json.entries || [];
      } else {
        parsedEntries = raw
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean)
          .map((line) => {
            const arrowParts = line.split(/\s*(?:->|→|\t|=)\s*/);
            if (arrowParts.length >= 2) {
              const orig = arrowParts[0].trim();
              const rest = arrowParts
                .slice(1)
                .join(" ")
                .split(/\s*\|\s*/);
              return {
                original_term: orig,
                translated_term: rest[0].trim(),
                notes: rest[1]?.trim() || undefined,
              };
            }
            return null;
          })
          .filter(Boolean);
      }
      if (parsedEntries.length === 0)
        throw new Error("Format tidak dikenali atau kosong.");

      const res = await apiJson(
        `/api/threads/${selectedThreadId}/lorebook/bulk`,
        { action: "import", entries: parsedEntries }
      );
      if (!res.ok) throw new Error("Gagal mengimpor istilah");
      const data = await res.json();
      await fetchLorebook(selectedThreadId);
      setShowImportModal(false);
      setImportText("");
      toast.success(
        `Berhasil mengimpor ${data.affected} istilah ke glosarium!`
      );
    } catch (e: any) {
      toast.error(`Gagal impor: ${e.message || "Periksa format JSON/teks"}`);
    } finally {
      setIsBulkProcessing(false);
    }
  };

  const handleApplyPreset = async (presetKey: string) => {
    if (!selectedThreadId) return;
    setIsApplyingPreset(presetKey);
    try {
      const res = await apiJson(
        `/api/threads/${selectedThreadId}/presets/${presetKey}`,
        {
          target_language: presetLanguage,
          lock_entries: presetLockEntries,
        }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal menerapkan preset");
      toast.success(
        `Preset "${data.preset}" (${data.language || presetLanguage}) diterapkan! +${data.added} istilah baru (${data.skipped} dilewati).`
      );
      await fetchLorebook(selectedThreadId);
      setShowPresetsModal(false);
    } catch (e: any) {
      toast.error(e.message || "Gagal menerapkan preset");
    } finally {
      setIsApplyingPreset(null);
    }
  };

  const handleExtractContext = async () => {
    if (!selectedThreadId) return;
    setIsExtracting(true);
    setAiReasoning("");
    setShowAiReasoning(false);
    const lmUrl = localStorage.getItem("lm_url") || "http://localhost:1234";
    const lmModel = localStorage.getItem("lm_model") || "";
    try {
      const res = await apiJson(
        `/api/threads/${selectedThreadId}/extract-context`,
        {
          lm_url: lmUrl,
          model: lmModel || undefined,
          chapter_count: extractSettings.chapterCount,
          sample_size: extractSettings.sampleSize,
        }
      );
      let data: any = {};
      try {
        data = await res.json();
      } catch (err) {
        throw new Error("Server mengembalikan format teks tidak terduga.", {
          cause: err,
        });
      }
      if (!res.ok) throw new Error(data.detail || "Ekstraksi gagal.");
      if (data.metadata?.reasoning) setAiReasoning(data.metadata.reasoning);

      const existingOriginals = new Set(
        entries.map((e) => e.original_term.trim().toLowerCase())
      );
      const filteredSuggestions = (data.terms || []).filter(
        (sug: ExtractedTerm) =>
          !existingOriginals.has(sug.original_term.trim().toLowerCase())
      );
      setSuggestions(filteredSuggestions);
      if (filteredSuggestions.length > 0) {
        toast.success(
          `Ditemukan ${filteredSuggestions.length} saran istilah baru dari AI!`
        );
      } else {
        toast.info(
          "Semua istilah yang terdeteksi sudah ada di dalam glosarium."
        );
      }
    } catch (e: any) {
      toast.error(`Ekstraksi Gagal: ${e.message || "Unknown error"}`);
    } finally {
      setIsExtracting(false);
    }
  };

  const saveExtractSettings = async (
    chapterCount: number,
    sampleSize: number
  ) => {
    try {
      await apiJson("/api/settings", {
        extract_chapter_count: chapterCount,
        extract_sample_size: sampleSize,
      });
    } catch (e) {
      console.error("Failed to save extract settings", e);
    }
  };

  const setPresetScope = (type: "quick" | "normal" | "deep") => {
    const cc = type === "quick" ? 5 : type === "normal" ? 15 : 25;
    setExtractSettings({ chapterCount: cc, sampleSize: 1000 });
    saveExtractSettings(cc, 1000);
  };

  const scanRelationships = async () => {
    if (!selectedThreadId) return;
    setIsScanningRels(true);
    try {
      const res = await apiJson(
        `/api/threads/${selectedThreadId}/extract-relationships`,
        {
          chapter_count: extractSettings.chapterCount,
          sample_size: extractSettings.sampleSize,
        }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Scan failed");
      toast.success(
        `Scan selesai! Ditemukan ${data.new_count} relasi karakter baru.`
      );
      fetchRelationships(selectedThreadId);
    } catch (e: any) {
      toast.error(e.message || "Gagal memindai relasi karakter");
    } finally {
      setIsScanningRels(false);
    }
  };

  const handleSaveRelationship = async (payload: {
    id?: number | null;
    source_term: string;
    target_term: string;
    relationship_type: string;
    notes?: string;
  }) => {
    if (!selectedThreadId) return;
    if (
      !payload.source_term.trim() ||
      !payload.target_term.trim() ||
      !payload.relationship_type.trim()
    ) {
      toast.error("Tokoh asal, tokoh tujuan, dan jenis relasi wajib diisi!");
      return;
    }
    try {
      const isEdit = Boolean(payload.id);
      const path = isEdit
        ? `/api/relationships/${payload.id}`
        : `/api/threads/${selectedThreadId}/relationships`;
      const res = await apiJson(
        path,
        {
          source_term: payload.source_term.trim(),
          target_term: payload.target_term.trim(),
          relationship_type: payload.relationship_type.trim(),
          notes: payload.notes?.trim() || undefined,
        },
        isEdit ? "PUT" : "POST"
      );
      if (!res.ok) throw new Error("Gagal menyimpan relasi");
      await fetchRelationships(selectedThreadId);
      toast.success(
        isEdit ? "Relasi diperbarui!" : "Relasi karakter ditambahkan!"
      );
    } catch (e: any) {
      toast.error(e.message || "Gagal menyimpan relasi");
    }
  };

  const handleDeleteRelationship = async (relId: number) => {
    if (!selectedThreadId) return;
    try {
      const res = await fetch(getApiUrl(`/api/relationships/${relId}`), {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Gagal menghapus relasi");
      setRelationships((prev) => prev.filter((r) => r.id !== relId));
      toast.success("Relasi karakter dihapus");
    } catch (e: any) {
      toast.error(e.message || "Gagal menghapus relasi");
    }
  };

  const handleClearAllRelationships = async () => {
    if (!selectedThreadId || relationships.length === 0) return;
    try {
      const res = await fetch(
        getApiUrl(`/api/threads/${selectedThreadId}/relationships`),
        { method: "DELETE" }
      );
      if (!res.ok) throw new Error("Gagal membersihkan relasi");
      setRelationships([]);
      toast.success(
        "Seluruh relasi karakter pada novel ini telah dibersihkan."
      );
    } catch (e: any) {
      toast.error(e.message || "Gagal membersihkan relasi");
    }
  };

  const activeEntriesCount = useMemo(
    () => entries.filter((e) => !e.is_archived).length,
    [entries]
  );
  const archivedEntriesCount = useMemo(
    () => entries.filter((e) => e.is_archived).length,
    [entries]
  );
  const lockedEntriesCount = useMemo(
    () => entries.filter((e) => e.is_locked && !e.is_archived).length,
    [entries]
  );
  const autoExtractedCount = useMemo(
    () => entries.filter((e) => e.auto_extracted).length,
    [entries]
  );
  const maleCount = useMemo(
    () => entries.filter((e) => getEntryGender(e) === "MALE").length,
    [entries]
  );
  const femaleCount = useMemo(
    () => entries.filter((e) => getEntryGender(e) === "FEMALE").length,
    [entries]
  );
  const genderlessCount = useMemo(
    () => entries.filter((e) => getEntryGender(e) === null).length,
    [entries]
  );

  const filteredEntries = useMemo(() => {
    const list = entries.filter((e) => {
      if (statusFilter === "active" && e.is_archived) return false;
      if (statusFilter === "archived" && !e.is_archived) return false;
      if (statusFilter === "locked" && !e.is_locked) return false;
      if (statusFilter === "auto" && !e.auto_extracted) return false;

      const g = getEntryGender(e);
      if (genderFilter === "male" && g !== "MALE") return false;
      if (genderFilter === "female" && g !== "FEMALE") return false;
      if (genderFilter === "genderless" && g !== null) return false;

      const q = searchQuery.trim().toLowerCase();
      if (!q) return true;
      return (
        e.original_term.toLowerCase().includes(q) ||
        e.translated_term.toLowerCase().includes(q) ||
        (e.notes || "").toLowerCase().includes(q)
      );
    });

    const sorted = [...list];
    if (sortMode === "usage") {
      sorted.sort(
        (a, b) => (b.usage_count || 0) - (a.usage_count || 0) || b.id - a.id
      );
    } else if (sortMode === "orig_az") {
      sorted.sort((a, b) => a.original_term.localeCompare(b.original_term));
    } else if (sortMode === "trans_az") {
      sorted.sort((a, b) => a.translated_term.localeCompare(b.translated_term));
    } else if (sortMode === "locked_first") {
      sorted.sort(
        (a, b) =>
          Number(Boolean(b.is_locked)) - Number(Boolean(a.is_locked)) ||
          Number(Boolean(a.is_archived)) - Number(Boolean(b.is_archived)) ||
          (b.usage_count || 0) - (a.usage_count || 0)
      );
    } else {
      sorted.sort((a, b) => a.id - b.id);
    }
    return sorted;
  }, [entries, statusFilter, genderFilter, searchQuery, sortMode]);

  const displayedEntries = useMemo(
    () => filteredEntries.slice(0, visibleCount),
    [filteredEntries, visibleCount]
  );
  const estInputTokens = Math.ceil(
    150 +
      globalContext.length / 4 +
      extractSettings.chapterCount * extractSettings.sampleSize * 1.5
  );
  const estTotalTokens = estInputTokens + 1500;
  const selectedThread = threads.find((t) => t.id === selectedThreadId);
  const effectivePromptLimit =
    translationMode === "fast"
      ? Math.min(maxContextTerms, 10)
      : maxContextTerms;
  const capacityPct = Math.min(
    100,
    Math.round((activeEntriesCount / Math.max(maxContextTerms, 1)) * 100)
  );

  const toggleSelectEntry = (id: number) => {
    setSelectedEntryIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAllFiltered = () => {
    if (
      selectedEntryIds.size === filteredEntries.length &&
      filteredEntries.length > 0
    ) {
      setSelectedEntryIds(new Set());
    } else {
      setSelectedEntryIds(new Set(filteredEntries.map((e) => e.id)));
    }
  };

  return (
    <div className="flex flex-col md:flex-row min-h-[calc(100vh-100px)] w-full bg-[var(--background)] gap-6">
      {/* Left Sidebar: Global Hub & Series Selector */}
      <aside className="w-full md:w-72 md:sticky md:top-8 md:h-[calc(100vh-8rem)] rounded-3xl flex flex-col bg-[var(--card)]/50 border border-[var(--border)] overflow-hidden shadow-xl">
        <div className="p-4 border-b border-[var(--border)] bg-[var(--card)] flex-shrink-0">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <BookOpen size={18} className="text-[var(--primary)]" />
              <h2 className="font-bold text-[var(--foreground)] tracking-tight">
                Glossary Studio
              </h2>
            </div>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20">
              {threads.length} Novel
            </span>
          </div>
          <button
            onClick={() => setSelectedThreadId(null)}
            className={cn(
              "w-full flex items-center justify-between px-3 py-2.5 rounded-xl transition-all font-semibold text-xs border cursor-pointer",
              selectedThreadId === null
                ? "bg-[var(--primary)]/15 text-[var(--primary)] border-[var(--primary)]/40 shadow-sm"
                : "bg-[var(--secondary)] text-[var(--foreground)] border-transparent hover:border-[var(--border)]"
            )}
          >
            <div className="flex items-center gap-2">
              <Globe size={15} />
              <span>All Threads (Global Hub)</span>
            </div>
            {selectedThreadId === null && (
              <div className="w-2 h-2 rounded-full bg-[var(--primary)]" />
            )}
          </button>
        </div>

        <div className="md:hidden p-4 border-b border-[var(--border)]">
          <select
            value={selectedThreadId ?? ""}
            onChange={(e) =>
              setSelectedThreadId(
                e.target.value ? parseInt(e.target.value, 10) : null
              )
            }
            className="w-full rounded-xl border border-[var(--border)] bg-[var(--card)] text-[var(--foreground)] px-4 py-3 text-sm outline-none cursor-pointer"
          >
            <option value="">🌐 All Threads (Global Context Hub)</option>
            {threads.map((thread) => (
              <option key={thread.id} value={thread.id}>
                📖 {thread.title}
              </option>
            ))}
          </select>
        </div>

        <div className="hidden md:block flex-1 overflow-auto py-3 px-3 space-y-1 custom-scrollbar">
          {threads.map((thread) => (
            <button
              key={thread.id}
              onClick={() => setSelectedThreadId(thread.id)}
              className={cn(
                "w-full text-left px-3.5 py-3 rounded-xl transition-all duration-200 group cursor-pointer border",
                selectedThreadId === thread.id
                  ? "bg-[var(--accent)] text-[var(--primary)] border-[var(--primary)]/30 shadow-sm"
                  : "text-[var(--muted-foreground)] border-transparent hover:bg-[var(--secondary)] hover:text-[var(--foreground)]"
              )}
            >
              <div className="font-semibold text-sm truncate">
                {thread.title}
              </div>
              <div className="flex items-center justify-between text-[10px] opacity-75 mt-0.5">
                <span className="truncate">
                  {thread.author || "Unknown Author"}
                </span>
                {thread.chapter_count !== undefined && (
                  <span className="font-mono shrink-0 ml-2">
                    {thread.chapter_count} Bab
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>

        <div className="p-4 border-t border-[var(--border)] bg-[var(--card)]">
          <button
            onClick={() => {
              window.location.hash = "#translate";
              toast.info(
                "Impor novel atau masukkan URL baru untuk membuat profil context otomatis."
              );
            }}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-[var(--border)] text-xs font-semibold text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)] transition-all cursor-pointer shadow-sm"
          >
            <Plus size={15} /> Impor Novel Baru
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 rounded-3xl bg-[var(--card)]/30 border border-[var(--border)] shadow-xl overflow-hidden">
        {selectedThread ? (
          <>
            {/* Sticky Novel Header + Capacity Sync Bar */}
            <header className="sticky top-0 px-4 md:px-8 pt-5 pb-0 border-b border-[var(--border)] bg-[var(--card)]/90 backdrop-blur-md z-[50]">
              <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h1 className="text-xl md:text-2xl font-bold text-[var(--foreground)] tracking-tight truncate">
                      {selectedThread.title}
                    </h1>
                    <span
                      className={cn(
                        "text-[10px] font-bold px-2.5 py-0.5 rounded-full border uppercase tracking-wider",
                        translationMode === "quality"
                          ? "bg-purple-500/10 text-purple-500 border-purple-500/30"
                          : "bg-orange-500/10 text-orange-500 border-orange-500/30"
                      )}
                      title="Mode terjemahan saat ini (sinkron dengan Settings)"
                    >
                      {translationMode === "quality"
                        ? "✨ Quality Mode"
                        : "⚡ Fast Mode"}
                    </span>
                    <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-[var(--secondary)] text-[var(--muted-foreground)] border border-[var(--border)]">
                      🎯 {targetLanguage}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--muted-foreground)] mt-1">
                    Kelola glosarium terkunci, arsip istilah, panduan gaya
                    bahasa (Style Guide), dan jejaring karakter.
                  </p>
                </div>

                {/* Action Toolbar */}
                <div className="flex flex-wrap items-center gap-2 relative self-start lg:self-auto">
                  <div className="flex items-center bg-[var(--card)] border border-[var(--border)] rounded-xl p-1 shadow-sm">
                    <Button
                      variant="ghost"
                      size="sm"
                      className={cn(
                        "rounded-lg gap-1.5 h-8 px-2.5 sm:px-3 text-xs font-semibold transition-all cursor-pointer",
                        isExtracting
                          ? "opacity-50"
                          : "hover:bg-[var(--accent)] hover:text-[var(--primary)]"
                      )}
                      onClick={handleExtractContext}
                      disabled={isExtracting}
                      title="Ekstrak istilah penting dari bab novel menggunakan AI"
                    >
                      {isExtracting ? (
                        <Loader2 size={14} className="animate-spin" />
                      ) : (
                        <Sparkles size={14} className="text-yellow-500" />
                      )}
                      <span>AI Extract</span>
                    </Button>
                    <div className="w-[1px] h-4 bg-[var(--border)] mx-0.5" />
                    <button
                      onClick={() =>
                        setShowExtractSettings(!showExtractSettings)
                      }
                      className={cn(
                        "p-1.5 rounded-lg transition-colors hover:bg-[var(--secondary)] cursor-pointer",
                        showExtractSettings
                          ? "text-[var(--primary)] bg-[var(--accent)]"
                          : "text-[var(--muted-foreground)]"
                      )}
                      aria-label="Extraction Settings"
                      title="Pengaturan Jangkauan Ekstraksi AI"
                    >
                      <Settings2 size={14} />
                    </button>
                  </div>

                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-xl gap-1.5 h-9 px-3 text-xs font-semibold border-emerald-500/30 text-emerald-500 hover:bg-emerald-500/10 hover:text-emerald-400 cursor-pointer"
                    onClick={handleReapplyGlossaryAll}
                    disabled={isReapplyingAll}
                    title="Terapkan seluruh aturan glosarium terbaru ke semua bab & judul yang sudah diterjemahkan (0 token, instan)"
                  >
                    <RefreshCw
                      size={13}
                      className={cn(
                        "text-emerald-500",
                        isReapplyingAll ? "animate-spin" : ""
                      )}
                    />
                    <span className="hidden sm:inline">Sync to Chapters</span>
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-xl gap-1.5 h-9 px-3 text-xs font-semibold cursor-pointer"
                    onClick={() => setShowPresetsModal(true)}
                    title="Terapkan Preset Glosarium Genre (Indonesia / Inggris)"
                  >
                    <Sparkles size={13} className="text-[var(--primary)]" />
                    <span className="hidden sm:inline">Presets</span>
                  </Button>

                  <Button
                    size="sm"
                    className="rounded-xl gap-1.5 h-9 px-3.5 text-xs font-bold shadow-lg shadow-[var(--primary)]/20 cursor-pointer"
                    onClick={() => {
                      setEditingEntryId(null);
                      setNewEntry({
                        original: "",
                        translated: "",
                        notes: "",
                        gender: "",
                        is_locked: false,
                      });
                      setShowAddForm(true);
                      setActiveSubTab("glossary");
                    }}
                    title="Tambah Istilah Baru"
                  >
                    <Plus size={14} /> <span>Add Term</span>
                  </Button>
                </div>
              </div>

              {/* Live Capacity & Settings Sync Meter */}
              <div className="mb-4 p-3 rounded-2xl bg-[var(--secondary)]/40 border border-[var(--border)] flex flex-col lg:flex-row lg:items-center justify-between gap-3">
                <div className="flex-1 space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-[var(--foreground)] flex items-center gap-1.5">
                      <ShieldCheck
                        size={14}
                        className="text-[var(--primary)]"
                      />
                      Kuota Glosarium Aktif:{" "}
                      <span className="font-mono text-[var(--primary)]">
                        {activeEntriesCount} / {maxContextTerms}
                      </span>{" "}
                      istilah ({capacityPct}%)
                    </span>
                    <div className="flex items-center gap-3 text-[11px] text-[var(--muted-foreground)] font-medium">
                      <span>🔒 {lockedEntriesCount} Terkunci</span>
                      <span>📦 {archivedEntriesCount} Diarsipkan</span>
                      <span>✨ {autoExtractedCount} Auto-AI</span>
                    </div>
                  </div>
                  <div className="w-full h-2 rounded-full bg-[var(--secondary)] overflow-hidden">
                    <div
                      className={cn(
                        "h-full transition-all duration-300 rounded-full",
                        capacityPct >= 95
                          ? "bg-amber-500"
                          : "bg-[var(--primary)]"
                      )}
                      style={{ width: `${capacityPct}%` }}
                    />
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2 shrink-0">
                  <div className="flex items-center gap-1.5 bg-[var(--card)] px-2.5 py-1.5 rounded-xl border border-[var(--border)] text-xs">
                    <span className="text-[10px] font-bold uppercase text-[var(--muted-foreground)]">
                      Limit:
                    </span>
                    <select
                      value={maxContextTerms}
                      onChange={(e) =>
                        handleUpdateGlobalSetting({
                          max_context_terms: parseInt(e.target.value, 10),
                        })
                      }
                      className="bg-transparent font-mono font-bold text-[var(--foreground)] outline-none cursor-pointer text-xs"
                      title="Ubah batas maksimum istilah aktif (sinkron langsung dengan Settings)"
                    >
                      {CONTEXT_LIMIT_OPTIONS.map((lim) => (
                        <option
                          key={lim}
                          value={lim}
                          className="bg-[var(--card)]"
                        >
                          {lim} terms
                        </option>
                      ))}
                    </select>
                  </div>

                  {archivedEntriesCount > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        setActiveSubTab("glossary");
                        setStatusFilter(
                          statusFilter === "archived" ? "all" : "archived"
                        );
                      }}
                      className={cn(
                        "px-2.5 py-1.5 rounded-xl text-xs font-bold border transition-all cursor-pointer flex items-center gap-1.5",
                        statusFilter === "archived"
                          ? "bg-amber-500 text-white border-amber-500"
                          : "bg-amber-500/10 text-amber-500 border-amber-500/30 hover:bg-amber-500/20"
                      )}
                    >
                      <Archive size={13} />
                      <span>Lihat {archivedEntriesCount} Arsip</span>
                    </button>
                  )}
                </div>
              </div>

              {translationMode === "fast" && (
                <div className="mb-4 p-3 rounded-xl bg-orange-500/10 border border-orange-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-2 text-orange-600 dark:text-orange-400">
                    <AlertTriangle size={15} className="shrink-0" />
                    <span>
                      <strong>Fast Mode Aktif:</strong> Hanya maksimal{" "}
                      <strong>{effectivePromptLimit} istilah</strong> per bab
                      yang disuntikkan ke prompt AI, dan{" "}
                      <em>Style Guide / Relasi Karakter</em> dilewati demi
                      menghemat VRAM.
                    </span>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      handleUpdateGlobalSetting({ translation_mode: "quality" })
                    }
                    className="h-7 text-[11px] rounded-lg border-orange-500/40 text-orange-600 dark:text-orange-300 hover:bg-orange-500/20 shrink-0 cursor-pointer"
                  >
                    Alihkan ke Quality Mode
                  </Button>
                </div>
              )}

              {/* Sub-Tabs */}
              <div className="flex gap-4 sm:gap-8 overflow-x-auto no-scrollbar">
                <button
                  onClick={() => setActiveSubTab("glossary")}
                  className={cn(
                    "pb-3.5 text-sm font-semibold transition-all relative flex items-center gap-2 shrink-0 cursor-pointer",
                    activeSubTab === "glossary"
                      ? "text-[var(--primary)]"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  )}
                >
                  <BookOpen size={16} />
                  <span>Glossary ({entries.length})</span>
                  {activeSubTab === "glossary" && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />
                  )}
                </button>
                <button
                  onClick={() => setActiveSubTab("context")}
                  className={cn(
                    "pb-3.5 text-sm font-semibold transition-all relative flex items-center gap-2 shrink-0 cursor-pointer",
                    activeSubTab === "context"
                      ? "text-[var(--primary)]"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  )}
                >
                  <Filter size={16} className="rotate-90" />
                  <span>Style Guide & Rules</span>
                  {(styleGuide.trim() || threadContext.trim()) && (
                    <span className="w-2 h-2 rounded-full bg-emerald-500" />
                  )}
                  {activeSubTab === "context" && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />
                  )}
                </button>
                <button
                  onClick={() => setActiveSubTab("relationships")}
                  className={cn(
                    "pb-3.5 text-sm font-semibold transition-all relative flex items-center gap-2 shrink-0 cursor-pointer",
                    activeSubTab === "relationships"
                      ? "text-[var(--primary)]"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  )}
                >
                  <Users size={16} />
                  <span>Character Network ({relationships.length})</span>
                  {activeSubTab === "relationships" && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--primary)]" />
                  )}
                </button>
              </div>
            </header>

            {/* Tab Body */}
            <div className="flex-1 p-4 md:p-8">
              {/* TAB 1: GLOSSARY STUDIO */}
              {activeSubTab === "glossary" && (
                <div className="space-y-6">
                  {/* Status Tabs + Tools */}
                  <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-3">
                    <div className="flex items-center gap-1.5 overflow-x-auto pb-1 xl:pb-0 no-scrollbar">
                      {[
                        { id: "all", label: `Semua (${entries.length})` },
                        {
                          id: "active",
                          label: `Aktif (${activeEntriesCount})`,
                        },
                        {
                          id: "locked",
                          label: `🔒 Terkunci (${lockedEntriesCount})`,
                        },
                        {
                          id: "archived",
                          label: `📦 Diarsipkan (${archivedEntriesCount})`,
                        },
                        {
                          id: "auto",
                          label: `✨ Auto-AI (${autoExtractedCount})`,
                        },
                      ].map((tab) => (
                        <button
                          key={tab.id}
                          onClick={() =>
                            setStatusFilter(tab.id as StatusFilter)
                          }
                          className={pillCls(statusFilter === tab.id)}
                        >
                          {tab.label}
                        </button>
                      ))}
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => executeBulkAction("clean_garbage")}
                        disabled={isBulkProcessing}
                        className="h-8 rounded-xl text-xs gap-1.5 cursor-pointer"
                        title="Bersihkan istilah sampah/angka/header catatan yang tidak valid"
                      >
                        <Sparkles size={13} className="text-amber-500" />{" "}
                        <span>Clean Junk</span>
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowImportModal(true)}
                        className="h-8 rounded-xl text-xs gap-1.5 cursor-pointer"
                        title="Impor glosarium dari JSON atau teks daftar istilah"
                      >
                        <Upload size={13} /> <span>Import</span>
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleExportGlossary}
                        className="h-8 rounded-xl text-xs gap-1.5 cursor-pointer"
                        title="Ekspor glosarium novel ini ke file JSON"
                      >
                        <Download size={13} /> <span>Export</span>
                      </Button>
                      <div className="flex items-center bg-[var(--card)] border border-[var(--border)] rounded-xl p-0.5">
                        <button
                          onClick={() => setViewMode("grid")}
                          className={cn(
                            "p-1.5 rounded-lg transition-colors cursor-pointer",
                            viewMode === "grid"
                              ? "bg-[var(--primary)] text-white"
                              : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                          )}
                          title="Tampilan Kartu (Grid)"
                        >
                          <LayoutGrid size={14} />
                        </button>
                        <button
                          onClick={() => setViewMode("table")}
                          className={cn(
                            "p-1.5 rounded-lg transition-colors cursor-pointer",
                            viewMode === "table"
                              ? "bg-[var(--primary)] text-white"
                              : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                          )}
                          title="Tampilan Tabel Ringkas"
                        >
                          <List size={14} />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Search + Gender Filters + Sort */}
                  <div className="flex flex-col lg:flex-row gap-3">
                    <div className="flex-1 relative">
                      <Search
                        className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]"
                        size={17}
                      />
                      <input
                        type="text"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Cari istilah asli (Hanzi/Hangul/Kanji), terjemahan, atau catatan tokoh..."
                        className="w-full pl-10 pr-9 py-2.5 rounded-xl bg-[var(--card)] border border-[var(--border)] text-sm focus:outline-none focus:border-[var(--primary)] transition-all"
                      />
                      {searchQuery && (
                        <button
                          onClick={() => setSearchQuery("")}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] hover:text-[var(--foreground)] cursor-pointer"
                        >
                          <X size={15} />
                        </button>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 overflow-x-auto pb-1 lg:pb-0 shrink-0">
                      <button
                        onClick={() => setGenderFilter("all")}
                        className={cn(
                          "px-3 py-2 rounded-xl text-xs font-semibold transition-all border cursor-pointer",
                          genderFilter === "all"
                            ? "bg-[var(--accent)] text-[var(--primary)] border-[var(--primary)]/40 shadow-sm"
                            : "bg-[var(--card)] text-[var(--muted-foreground)] border-[var(--border)] hover:text-[var(--foreground)]"
                        )}
                      >
                        Semua Gender
                      </button>
                      <button
                        onClick={() => setGenderFilter("male")}
                        className={cn(
                          "px-3 py-2 rounded-xl text-xs font-semibold transition-all border flex items-center gap-1.5 cursor-pointer",
                          genderFilter === "male"
                            ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                            : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20 hover:bg-blue-500/20"
                        )}
                      >
                        <span>♂ Male</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-black/10 font-bold">
                          {maleCount}
                        </span>
                      </button>
                      <button
                        onClick={() => setGenderFilter("female")}
                        className={cn(
                          "px-3 py-2 rounded-xl text-xs font-semibold transition-all border flex items-center gap-1.5 cursor-pointer",
                          genderFilter === "female"
                            ? "bg-pink-600 text-white border-pink-600 shadow-sm"
                            : "bg-pink-500/10 text-pink-600 dark:text-pink-400 border-pink-500/20 hover:bg-pink-500/20"
                        )}
                      >
                        <span>♀ Female</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-black/10 font-bold">
                          {femaleCount}
                        </span>
                      </button>
                      <button
                        onClick={() => setGenderFilter("genderless")}
                        className={cn(
                          "px-3 py-2 rounded-xl text-xs font-semibold transition-all border flex items-center gap-1.5 cursor-pointer",
                          genderFilter === "genderless"
                            ? "bg-slate-700 text-white border-slate-700 shadow-sm"
                            : "bg-[var(--card)] text-[var(--muted-foreground)] border-[var(--border)] hover:text-[var(--foreground)]"
                        )}
                      >
                        <span>Benda/Netral</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--secondary)] font-bold">
                          {genderlessCount}
                        </span>
                      </button>
                    </div>

                    <div className="flex items-center gap-1.5 bg-[var(--card)] border border-[var(--border)] rounded-xl px-3 py-2 shrink-0">
                      <ArrowUpDown
                        size={14}
                        className="text-[var(--muted-foreground)]"
                      />
                      <select
                        value={sortMode}
                        onChange={(e) =>
                          setSortMode(e.target.value as SortMode)
                        }
                        className="bg-transparent text-xs font-semibold text-[var(--foreground)] outline-none cursor-pointer"
                      >
                        <option value="id" className="bg-[var(--card)]">
                          Urutan Ditambahkan
                        </option>
                        <option value="usage" className="bg-[var(--card)]">
                          Paling Sering Dipakai (Usage ↓)
                        </option>
                        <option
                          value="locked_first"
                          className="bg-[var(--card)]"
                        >
                          Terkunci Lebih Dulu (🔒)
                        </option>
                        <option value="trans_az" className="bg-[var(--card)]">
                          Terjemahan (A–Z)
                        </option>
                        <option value="orig_az" className="bg-[var(--card)]">
                          Istilah Asli (A–Z)
                        </option>
                      </select>
                    </div>
                  </div>

                  {/* Multi-Select Bulk Action Bar */}
                  {filteredEntries.length > 0 && (
                    <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2 rounded-xl bg-[var(--secondary)]/30 border border-[var(--border)] text-xs">
                      <button
                        type="button"
                        onClick={toggleSelectAllFiltered}
                        className="flex items-center gap-1.5 font-semibold text-[var(--foreground)] hover:text-[var(--primary)] cursor-pointer"
                      >
                        {selectedEntryIds.size === filteredEntries.length &&
                        filteredEntries.length > 0 ? (
                          <CheckSquare
                            size={15}
                            className="text-[var(--primary)]"
                          />
                        ) : (
                          <Square
                            size={15}
                            className="text-[var(--muted-foreground)]"
                          />
                        )}
                        <span>
                          {selectedEntryIds.size > 0
                            ? `${selectedEntryIds.size} dipilih`
                            : `Pilih Semua (${filteredEntries.length})`}
                        </span>
                      </button>
                      {selectedEntryIds.size > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isBulkProcessing}
                            onClick={() => executeBulkAction("lock")}
                            className="h-7 px-2.5 text-[11px] rounded-lg gap-1 cursor-pointer"
                          >
                            <Lock size={12} /> Lock
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isBulkProcessing}
                            onClick={() => executeBulkAction("unlock")}
                            className="h-7 px-2.5 text-[11px] rounded-lg gap-1 cursor-pointer"
                          >
                            <Unlock size={12} /> Unlock
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isBulkProcessing}
                            onClick={() => executeBulkAction("archive")}
                            className="h-7 px-2.5 text-[11px] rounded-lg gap-1 cursor-pointer"
                          >
                            <Archive size={12} /> Archive
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isBulkProcessing}
                            onClick={() => executeBulkAction("restore")}
                            className="h-7 px-2.5 text-[11px] rounded-lg gap-1 cursor-pointer"
                          >
                            <ArchiveRestore size={12} /> Restore
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={isBulkProcessing}
                            onClick={() => executeBulkAction("delete")}
                            className="h-7 px-2.5 text-[11px] rounded-lg gap-1 border-rose-500/30 text-rose-500 hover:bg-rose-500/10 cursor-pointer"
                          >
                            <Trash2 size={12} /> Hapus ({selectedEntryIds.size})
                          </Button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Add / Edit Term Form */}
                  {showAddForm && (
                    <div ref={formRef} className="scroll-mt-24">
                      <Card className="border-[var(--primary)] bg-[var(--accent)]/5 shadow-xl">
                        <CardContent className="p-6 space-y-5">
                          <div className="flex justify-between items-center pb-3 border-b border-[var(--border)]">
                            <div className="flex items-center gap-2.5">
                              <div className="w-8 h-8 rounded-lg bg-[var(--primary)] text-white flex items-center justify-center">
                                {editingEntryId ? (
                                  <FileText size={16} />
                                ) : (
                                  <Plus size={16} />
                                )}
                              </div>
                              <div>
                                <h3 className="font-bold text-base">
                                  {editingEntryId
                                    ? "Edit Istilah Glosarium"
                                    : "Tambah Istilah Baru"}
                                </h3>
                                <p className="text-[11px] text-[var(--muted-foreground)]">
                                  Istilah aktif akan disuntikkan ke prompt AI
                                  dan dikunci secara deterministik.
                                </p>
                              </div>
                            </div>
                            <button
                              onClick={() => {
                                setShowAddForm(false);
                                setEditingEntryId(null);
                                setNewEntry({
                                  original: "",
                                  translated: "",
                                  notes: "",
                                  gender: "",
                                  is_locked: false,
                                });
                              }}
                              className="p-2 hover:bg-[var(--secondary)] rounded-full transition-colors cursor-pointer"
                            >
                              <X size={18} />
                            </button>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                            <div className="space-y-1.5">
                              <label className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)]">
                                Istilah Asli (Hanzi / Kanji / Hangul)
                              </label>
                              <input
                                value={newEntry.original}
                                onChange={(e) =>
                                  setNewEntry({
                                    ...newEntry,
                                    original: e.target.value,
                                  })
                                }
                                placeholder="Contoh: 林动 atau 青阳镇"
                                className="w-full bg-[var(--card)] border border-[var(--border)] focus:border-[var(--primary)] rounded-xl px-4 py-2.5 text-sm outline-none"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <label className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)]">
                                Terjemahan Baku ({targetLanguage})
                              </label>
                              <input
                                value={newEntry.translated}
                                onChange={(e) =>
                                  setNewEntry({
                                    ...newEntry,
                                    translated: e.target.value,
                                  })
                                }
                                placeholder="Contoh: Lin Dong atau Kota Qingyang"
                                className="w-full bg-[var(--card)] border border-[var(--border)] focus:border-[var(--primary)] rounded-xl px-4 py-2.5 text-sm outline-none"
                              />
                            </div>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                            <div className="space-y-1.5">
                              <label className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)]">
                                Catatan Konteks / Peran
                              </label>
                              <input
                                value={newEntry.notes}
                                onChange={(e) =>
                                  setNewEntry({
                                    ...newEntry,
                                    notes: e.target.value,
                                  })
                                }
                                placeholder="Contoh: Tokoh utama dari Keluarga Lin"
                                className="w-full bg-[var(--card)] border border-[var(--border)] focus:border-[var(--primary)] rounded-xl px-4 py-2.5 text-sm outline-none"
                              />
                            </div>
                            <div className="space-y-1.5">
                              <label className="text-[10px] font-bold uppercase tracking-widest text-[var(--muted-foreground)]">
                                Gender Tokoh & Pin Kunci
                              </label>
                              <div className="flex items-center gap-2">
                                <select
                                  value={newEntry.gender}
                                  onChange={(e) =>
                                    setNewEntry({
                                      ...newEntry,
                                      gender: e.target.value,
                                    })
                                  }
                                  className="flex-1 bg-[var(--card)] border border-[var(--border)] focus:border-[var(--primary)] rounded-xl px-3 py-2.5 text-sm outline-none cursor-pointer"
                                >
                                  <option value="">
                                    Netral / Benda / Lokasi / Sekte
                                  </option>
                                  <option value="MALE">
                                    ♂ Laki-laki (MALE)
                                  </option>
                                  <option value="FEMALE">
                                    ♀ Perempuan (FEMALE)
                                  </option>
                                </select>
                                <button
                                  type="button"
                                  onClick={() =>
                                    setNewEntry((prev) => ({
                                      ...prev,
                                      is_locked: !prev.is_locked,
                                    }))
                                  }
                                  className={cn(
                                    "px-3 py-2.5 rounded-xl border text-xs font-bold flex items-center gap-1.5 cursor-pointer transition-all",
                                    newEntry.is_locked
                                      ? "bg-amber-500/15 text-amber-500 border-amber-500/40"
                                      : "bg-[var(--card)] text-[var(--muted-foreground)] border-[var(--border)]"
                                  )}
                                  title="Kunci istilah agar tidak pernah diarsipkan otomatis"
                                >
                                  <Lock size={14} />{" "}
                                  <span>
                                    {newEntry.is_locked ? "Locked" : "Pin"}
                                  </span>
                                </button>
                              </div>
                            </div>
                          </div>

                          <div className="flex justify-end gap-3 pt-3 border-t border-[var(--border)]">
                            <Button
                              variant="ghost"
                              className="rounded-xl px-5"
                              onClick={() => {
                                setShowAddForm(false);
                                setEditingEntryId(null);
                              }}
                            >
                              Batal
                            </Button>
                            <Button
                              className="rounded-xl px-7 shadow-lg shadow-[var(--primary)]/20"
                              onClick={addOrUpdateEntry}
                            >
                              {editingEntryId
                                ? "Simpan Perubahan"
                                : "Tambahkan Istilah"}
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  )}

                  {/* AI Detected Suggestions Tray */}
                  {(suggestions.length > 0 || aiReasoning) && (
                    <div className="space-y-4 p-4 rounded-2xl border border-amber-500/30 bg-amber-500/5">
                      {aiReasoning && (
                        <div className="rounded-xl border border-[var(--primary)]/20 bg-[var(--card)] overflow-hidden">
                          <button
                            onClick={() => setShowAiReasoning(!showAiReasoning)}
                            className="w-full flex items-center justify-between p-3.5 text-left hover:bg-[var(--primary)]/5 transition-colors cursor-pointer"
                          >
                            <div className="flex items-center gap-2">
                              <Sparkles
                                size={15}
                                className="text-[var(--primary)]"
                              />
                              <span className="text-xs font-bold text-[var(--foreground)]">
                                AI Reasoning & Analisis Lore
                              </span>
                            </div>
                            <span className="text-[10px] text-[var(--primary)] font-bold uppercase tracking-wider">
                              {showAiReasoning
                                ? "Sembunyikan"
                                : "Baca Analisis"}
                            </span>
                          </button>
                          {showAiReasoning && (
                            <div className="p-4 border-t border-[var(--border)] text-xs text-[var(--muted-foreground)] leading-relaxed whitespace-pre-wrap">
                              {aiReasoning}
                            </div>
                          )}
                        </div>
                      )}

                      {suggestions.length > 0 && (
                        <>
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <h3 className="text-xs font-bold uppercase tracking-widest text-amber-600 dark:text-amber-400 flex items-center gap-2">
                              <Sparkles size={14} /> Saran Istilah Baru dari AI
                              ({suggestions.length})
                            </h3>
                            <div className="flex flex-wrap items-center gap-2">
                              <Button
                                size="sm"
                                onClick={() =>
                                  handleBulkAcceptSuggestions(false)
                                }
                                disabled={isBulkProcessing}
                                className="h-7 px-3 text-[11px] rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white gap-1 cursor-pointer"
                              >
                                <Check size={12} /> Terima Semua (
                                {suggestions.length})
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() =>
                                  handleBulkAcceptSuggestions(true)
                                }
                                disabled={isBulkProcessing}
                                className="h-7 px-3 text-[11px] rounded-lg border-blue-500/40 text-blue-500 hover:bg-blue-500/10 gap-1 cursor-pointer"
                              >
                                <Lock size={12} /> Terima & Kunci Semua
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setSuggestions([])}
                                className="h-7 px-2.5 text-[11px] rounded-lg text-rose-500 hover:bg-rose-500/10 cursor-pointer"
                              >
                                Abaikan Semua
                              </Button>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {suggestions.map((sug, i) => (
                              <Card
                                key={`${sug.original_term}-${i}`}
                                className="border-amber-500/30 bg-[var(--card)]"
                              >
                                <CardContent className="p-3.5 flex items-start justify-between gap-3">
                                  <div className="min-w-0">
                                    <div className="font-bold text-sm truncate">
                                      {sug.original_term}
                                    </div>
                                    <div className="flex items-center gap-1.5 flex-wrap my-0.5">
                                      {sug.translated_term && (
                                        <span className="text-xs font-semibold text-[var(--primary)]">
                                          → {sug.translated_term}
                                        </span>
                                      )}
                                      {sug.gender === "MALE" && (
                                        <span className="px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-blue-500/10 text-blue-500 border border-blue-500/20">
                                          ♂ Male
                                        </span>
                                      )}
                                      {sug.gender === "FEMALE" && (
                                        <span className="px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-pink-500/10 text-pink-500 border border-pink-500/20">
                                          ♀ Female
                                        </span>
                                      )}
                                    </div>
                                    <div className="text-[11px] text-[var(--muted-foreground)] mt-1 line-clamp-2">
                                      {sug.notes}
                                    </div>
                                  </div>
                                  <div className="flex flex-col gap-1 shrink-0">
                                    <button
                                      onClick={() => quickAddEntry(sug, false)}
                                      title="Terima ke Glosarium"
                                      className="p-1.5 bg-emerald-500/15 rounded-lg text-emerald-500 hover:bg-emerald-500/25 cursor-pointer"
                                    >
                                      <Plus size={13} />
                                    </button>
                                    <button
                                      onClick={() => quickAddEntry(sug, true)}
                                      title="Terima & Kunci"
                                      className="p-1.5 bg-blue-500/15 rounded-lg text-blue-500 hover:bg-blue-500/25 cursor-pointer"
                                    >
                                      <Lock size={13} />
                                    </button>
                                    <button
                                      onClick={() => {
                                        setNewEntry({
                                          original: sug.original_term,
                                          translated: sug.translated_term || "",
                                          notes: sug.notes || "",
                                          gender: sug.gender || "",
                                          is_locked: false,
                                        });
                                        setShowAddForm(true);
                                        setEditingEntryId(null);
                                      }}
                                      title="Edit sebelum tambah"
                                      className="p-1.5 bg-amber-500/15 rounded-lg text-amber-500 hover:bg-amber-500/25 cursor-pointer"
                                    >
                                      <Edit2 size={13} />
                                    </button>
                                    <button
                                      onClick={() =>
                                        setSuggestions((prev) =>
                                          prev.filter(
                                            (s) =>
                                              s.original_term.toLowerCase() !==
                                              sug.original_term.toLowerCase()
                                          )
                                        )
                                      }
                                      title="Abaikan"
                                      className="p-1.5 bg-rose-500/15 rounded-lg text-rose-500 hover:bg-rose-500/25 cursor-pointer"
                                    >
                                      <X size={13} />
                                    </button>
                                  </div>
                                </CardContent>
                              </Card>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  )}

                  {/* GLOSSARY VIEW: CARD GRID vs COMPACT TABLE */}
                  {isLoadingEntries ? (
                    <div className="py-16 flex flex-col items-center justify-center gap-3 text-[var(--muted-foreground)]">
                      <Loader2 className="w-7 h-7 animate-spin text-[var(--primary)]" />
                      <span className="text-xs font-semibold">
                        Memuat istilah glosarium...
                      </span>
                    </div>
                  ) : viewMode === "grid" ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                      {displayedEntries.map((entry) => (
                        <TermGridCard
                          key={entry.id}
                          entry={entry}
                          isSelected={selectedEntryIds.has(entry.id)}
                          onSelect={toggleSelectEntry}
                          onCycleGender={handleCycleGender}
                          onToggleLock={toggleLock}
                          onToggleArchive={toggleArchive}
                          onEdit={startEditing}
                          onDelete={removeEntry}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-x-auto">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead>
                          <tr className="border-b border-[var(--border)] bg-[var(--secondary)]/40 text-[10px] font-bold uppercase text-[var(--muted-foreground)]">
                            <th className="p-3 w-8"></th>
                            <th className="p-3">Istilah Asli</th>
                            <th className="p-3">Terjemahan</th>
                            <th className="p-3">Gender</th>
                            <th className="p-3">Catatan Konteks</th>
                            <th className="p-3 text-center">Dipakai</th>
                            <th className="p-3 text-center">Status</th>
                            <th className="p-3 text-right">Aksi</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--border)]">
                          {displayedEntries.map((entry) => {
                            const g = getEntryGender(entry);
                            const isSelected = selectedEntryIds.has(entry.id);
                            return (
                              <tr
                                key={entry.id}
                                className={cn(
                                  "hover:bg-[var(--secondary)]/30 transition-colors",
                                  entry.is_archived && "opacity-65"
                                )}
                              >
                                <td className="p-3">
                                  <button
                                    type="button"
                                    onClick={() => toggleSelectEntry(entry.id)}
                                    className="cursor-pointer"
                                  >
                                    {isSelected ? (
                                      <CheckSquare
                                        size={14}
                                        className="text-[var(--primary)]"
                                      />
                                    ) : (
                                      <Square
                                        size={14}
                                        className="text-[var(--muted-foreground)]"
                                      />
                                    )}
                                  </button>
                                </td>
                                <td className="p-3 font-mono font-bold text-[var(--foreground)]">
                                  {entry.original_term}
                                </td>
                                <td className="p-3 font-semibold text-[var(--primary)]">
                                  {entry.translated_term}
                                </td>
                                <td className="p-3">
                                  <button
                                    type="button"
                                    onClick={() => handleCycleGender(entry)}
                                    className="px-2 py-0.5 rounded-full text-[10px] font-bold border cursor-pointer"
                                  >
                                    {g === "MALE"
                                      ? "♂ Male"
                                      : g === "FEMALE"
                                        ? "♀ Female"
                                        : "Netral"}
                                  </button>
                                </td>
                                <td className="p-3 max-w-xs truncate text-[var(--muted-foreground)]">
                                  {entry.notes || "—"}
                                </td>
                                <td className="p-3 text-center font-mono">
                                  {entry.usage_count || 0}x
                                </td>
                                <td className="p-3 text-center">
                                  {entry.is_archived ? (
                                    <span className="px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-500 text-[10px] font-bold">
                                      Archived
                                    </span>
                                  ) : entry.is_locked ? (
                                    <span className="px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-500 text-[10px] font-bold">
                                      🔒 Locked
                                    </span>
                                  ) : (
                                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-500 text-[10px] font-bold">
                                      Active
                                    </span>
                                  )}
                                </td>
                                <td className="p-3 text-right">
                                  <div className="inline-flex items-center gap-1">
                                    <button
                                      onClick={() => toggleLock(entry)}
                                      className="p-1 hover:bg-[var(--secondary)] rounded cursor-pointer"
                                      title="Toggle Lock"
                                    >
                                      <Lock size={13} />
                                    </button>
                                    <button
                                      onClick={() => toggleArchive(entry)}
                                      className="p-1 hover:bg-[var(--secondary)] rounded cursor-pointer"
                                      title="Toggle Archive"
                                    >
                                      {entry.is_archived ? (
                                        <ArchiveRestore size={13} />
                                      ) : (
                                        <Archive size={13} />
                                      )}
                                    </button>
                                    <button
                                      onClick={() => startEditing(entry)}
                                      className="p-1 text-amber-500 hover:bg-amber-500/15 rounded cursor-pointer"
                                      title="Edit"
                                    >
                                      <Edit2 size={13} />
                                    </button>
                                    <button
                                      onClick={() => removeEntry(entry.id)}
                                      className="p-1 text-rose-500 hover:bg-rose-500/15 rounded cursor-pointer"
                                      title="Delete"
                                    >
                                      <Trash2 size={13} />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {!isLoadingEntries && filteredEntries.length === 0 && (
                    <div className="py-16 text-center border-2 border-dashed border-[var(--border)] rounded-3xl">
                      <BookOpen className="mx-auto w-10 h-10 text-[var(--muted-foreground)] mb-3 opacity-30" />
                      <h3 className="text-base font-bold text-[var(--foreground)]">
                        Tidak ada istilah yang cocok
                      </h3>
                      <p className="text-xs text-[var(--muted-foreground)] mt-1">
                        Tambahkan istilah baru, jalankan AI Extract, atau ubah
                        filter pencarian di atas.
                      </p>
                    </div>
                  )}

                  {filteredEntries.length > visibleCount && (
                    <div className="flex justify-center py-4">
                      <Button
                        variant="outline"
                        onClick={() => setVisibleCount((v) => v + 60)}
                        className="rounded-xl bg-[var(--card)] hover:bg-[var(--accent)] text-xs font-bold cursor-pointer"
                      >
                        Tampilkan Lebih Banyak (
                        {filteredEntries.length - visibleCount} tersisa)
                      </Button>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: STYLE GUIDE & CONTEXT RULES */}
              {activeSubTab === "context" && (
                <StyleAndRulesTab
                  threadTitle={selectedThread.title}
                  styleGuide={styleGuide}
                  setStyleGuide={setStyleGuide}
                  threadContext={threadContext}
                  setThreadContext={setThreadContext}
                  globalContext={globalContext}
                  setGlobalContext={setGlobalContext}
                  onSaveThread={saveThreadRulesAndStyle}
                  onSaveGlobal={saveGlobalInstructions}
                  isSavingThread={isSavingThreadCtx}
                  isSavingGlobal={isSavingGlobal}
                />
              )}

              {/* TAB 3: CHARACTER NETWORK (RELATIONSHIPS) */}
              {activeSubTab === "relationships" && (
                <RelationshipGraph
                  relationships={relationships}
                  isScanning={isScanningRels}
                  onScan={scanRelationships}
                  onSaveRelationship={handleSaveRelationship}
                  onDeleteRelationship={handleDeleteRelationship}
                  onClearAll={handleClearAllRelationships}
                />
              )}
            </div>
          </>
        ) : (
          /* GLOBAL CONTEXT & CROSS-SERIES STUDIO (when "All Threads" is selected) */
          <div className="flex-1 p-6 md:p-10 space-y-8 overflow-y-auto">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-6 border-b border-[var(--border)]">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-2xl bg-[var(--primary)]/15 text-[var(--primary)] flex items-center justify-center">
                  <Globe size={22} />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-[var(--foreground)] tracking-tight">
                    Global Context & Settings Sync Hub
                  </h1>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Kelola instruksi terjemahan lintas-novel dan sinkronisasi
                    kuota glosarium global.
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2.5">
                <div className="flex items-center gap-2 bg-[var(--card)] border border-[var(--border)] px-3 py-2 rounded-xl text-xs">
                  <span className="text-[10px] font-bold uppercase text-[var(--muted-foreground)]">
                    Target:
                  </span>
                  <select
                    value={targetLanguage}
                    onChange={(e) =>
                      handleUpdateGlobalSetting({
                        target_language: e.target.value,
                      })
                    }
                    className="bg-transparent font-bold text-[var(--foreground)] outline-none cursor-pointer"
                  >
                    <option value="Indonesian" className="bg-[var(--card)]">
                      Indonesian
                    </option>
                    <option value="English" className="bg-[var(--card)]">
                      English
                    </option>
                  </select>
                </div>
                <div className="flex items-center gap-2 bg-[var(--card)] border border-[var(--border)] px-3 py-2 rounded-xl text-xs">
                  <span className="text-[10px] font-bold uppercase text-[var(--muted-foreground)]">
                    Mode:
                  </span>
                  <select
                    value={translationMode}
                    onChange={(e) =>
                      handleUpdateGlobalSetting({
                        translation_mode: e.target.value as "quality" | "fast",
                      })
                    }
                    className="bg-transparent font-bold text-[var(--foreground)] outline-none cursor-pointer"
                  >
                    <option value="quality" className="bg-[var(--card)]">
                      ✨ Quality Mode
                    </option>
                    <option value="fast" className="bg-[var(--card)]">
                      ⚡ Fast Mode (10 terms)
                    </option>
                  </select>
                </div>
                <div className="flex items-center gap-2 bg-[var(--card)] border border-[var(--border)] px-3 py-2 rounded-xl text-xs">
                  <span className="text-[10px] font-bold uppercase text-[var(--muted-foreground)]">
                    Max Terms:
                  </span>
                  <select
                    value={maxContextTerms}
                    onChange={(e) =>
                      handleUpdateGlobalSetting({
                        max_context_terms: parseInt(e.target.value, 10),
                      })
                    }
                    className="bg-transparent font-mono font-bold text-[var(--primary)] outline-none cursor-pointer"
                  >
                    {CONTEXT_LIMIT_OPTIONS.map((lim) => (
                      <option
                        key={lim}
                        value={lim}
                        className="bg-[var(--card)]"
                      >
                        {lim} terms
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <Card className="border-[var(--border)] bg-[var(--card)]/60 shadow-sm">
              <CardContent className="p-6 space-y-4">
                <div>
                  <h3 className="text-base font-bold text-[var(--foreground)]">
                    Global Translation Instructions
                  </h3>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Instruksi ini otomatis disuntikkan ke seluruh novel saat
                    menerjemahkan dalam Quality Mode (Provider aktif:{" "}
                    <span className="font-mono font-semibold uppercase">
                      {activeProvider}
                    </span>
                    ).
                  </p>
                </div>
                <Textarea
                  value={globalContext}
                  onChange={(e) => setGlobalContext(e.target.value)}
                  placeholder="Contoh: Terjemahkan baris demi baris secara akurat. Gunakan Bahasa Indonesia sastra yang mengalir alami..."
                  className="min-h-[150px] text-sm bg-[var(--background)] border-[var(--border)] rounded-xl"
                />
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono text-[var(--muted-foreground)]">
                    {globalContext.length} karakter
                  </span>
                  <Button
                    onClick={saveGlobalInstructions}
                    disabled={isSavingGlobal}
                    className="rounded-xl gap-2 cursor-pointer"
                  >
                    {isSavingGlobal && (
                      <Loader2 size={14} className="animate-spin" />
                    )}{" "}
                    Simpan Instruksi Global
                  </Button>
                </div>
              </CardContent>
            </Card>

            <div className="space-y-4">
              <h3 className="text-base font-bold text-[var(--foreground)]">
                Pilih Novel untuk Mengelola Glosarium & Style Guide (
                {threads.length})
              </h3>
              {threads.length === 0 ? (
                <div className="py-12 text-center border-2 border-dashed border-[var(--border)] rounded-3xl text-sm text-[var(--muted-foreground)]">
                  Belum ada novel di Library. Impor EPUB atau URL terlebih
                  dahulu.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {threads.map((t) => (
                    <Card
                      key={t.id}
                      className="border-[var(--border)] bg-[var(--card)]/50 hover:border-[var(--primary)]/50 transition-all"
                    >
                      <CardContent className="p-5 flex flex-col justify-between gap-4 h-full">
                        <div>
                          <h4 className="font-bold text-base text-[var(--foreground)] line-clamp-1">
                            {t.title}
                          </h4>
                          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
                            {t.author || "Unknown Author"} •{" "}
                            {t.chapter_count ?? 0} Bab
                          </p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-[var(--border)]">
                          <Button
                            size="sm"
                            onClick={() => {
                              setSelectedThreadId(t.id);
                              setActiveSubTab("glossary");
                            }}
                            className="h-8 text-xs rounded-xl flex-1 cursor-pointer"
                          >
                            Buka Glosarium
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setSelectedThreadId(t.id);
                              setActiveSubTab("context");
                            }}
                            className="h-8 text-xs rounded-xl cursor-pointer"
                          >
                            Style Guide
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setSelectedThreadId(t.id);
                              setActiveSubTab("relationships");
                            }}
                            className="h-8 text-xs rounded-xl cursor-pointer"
                          >
                            Relasi
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* MODAL 1: AI Extraction Scope Settings */}
      {showExtractSettings && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowExtractSettings(false);
          }}
        >
          <div className="w-full max-w-md bg-[var(--card)] border border-[var(--border)] rounded-2xl shadow-2xl p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-yellow-500/10 text-yellow-500 flex items-center justify-center">
                  <Zap size={18} />
                </div>
                <div>
                  <h3 className="text-base font-bold text-[var(--foreground)]">
                    Extraction Scope
                  </h3>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    Pengaturan jangkauan ekstraksi AI
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() =>
                    setExtractMode((prev) =>
                      prev === "easy" ? "advanced" : "easy"
                    )
                  }
                  className="px-2.5 py-1 text-[10px] font-bold rounded-lg border border-[var(--border)] bg-[var(--secondary)] cursor-pointer"
                >
                  {extractMode === "advanced" ? "FINE-TUNED" : "ADVANCED"}
                </button>
                <button
                  onClick={() => setShowExtractSettings(false)}
                  className="p-1.5 rounded-lg text-[var(--muted-foreground)] hover:bg-[var(--secondary)] cursor-pointer"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2.5 mb-5">
              {[
                { id: "quick", label: "Quick", ch: 5, size: 1000 },
                { id: "normal", label: "Normal", ch: 15, size: 1000 },
                { id: "deep", label: "Deep", ch: 25, size: 1000 },
              ].map((p) => {
                const active =
                  extractSettings.chapterCount === p.ch &&
                  extractSettings.sampleSize === p.size;
                return (
                  <button
                    key={p.id}
                    onClick={() => {
                      setPresetScope(p.id as any);
                      setExtractMode("easy");
                    }}
                    className={cn(
                      "flex flex-col items-center py-2.5 px-2 rounded-xl border-2 transition-all cursor-pointer",
                      active
                        ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)] font-bold"
                        : "border-[var(--border)] text-[var(--muted-foreground)]"
                    )}
                  >
                    <span className="text-xs font-bold uppercase">
                      {p.label}
                    </span>
                    <span className="text-[10px] opacity-75 mt-0.5">
                      {p.ch} Bab
                    </span>
                  </button>
                );
              })}
            </div>

            {extractMode === "advanced" && (
              <div className="space-y-4 mb-5 pt-3 border-t border-dashed border-[var(--border)]">
                <div>
                  <div className="flex justify-between mb-1.5 text-xs font-bold">
                    <span>Jumlah Bab</span>
                    <span className="font-mono text-[var(--primary)]">
                      {extractSettings.chapterCount} Bab
                    </span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="50"
                    step="1"
                    value={extractSettings.chapterCount}
                    onChange={(e) => {
                      const val = parseInt(e.target.value, 10);
                      setExtractSettings((prev) => {
                        const next = { ...prev, chapterCount: val };
                        saveExtractSettings(next.chapterCount, next.sampleSize);
                        return next;
                      });
                    }}
                    className="w-full accent-[var(--primary)] cursor-pointer"
                  />
                </div>
                <div>
                  <div className="flex justify-between mb-1.5 text-xs font-bold">
                    <span>Sampel Karakter per Bab</span>
                    <span className="font-mono text-[var(--primary)]">
                      {extractSettings.sampleSize} Chars
                    </span>
                  </div>
                  <input
                    type="range"
                    min="200"
                    max="20000"
                    step="100"
                    value={extractSettings.sampleSize}
                    onChange={(e) => {
                      const val = parseInt(e.target.value, 10);
                      setExtractSettings((prev) => {
                        const next = { ...prev, sampleSize: val };
                        saveExtractSettings(next.chapterCount, next.sampleSize);
                        return next;
                      });
                    }}
                    className="w-full accent-[var(--primary)] cursor-pointer"
                  />
                </div>
              </div>
            )}

            <div className="pt-4 border-t border-[var(--border)] flex items-center justify-between">
              <div>
                <span className="text-[10px] font-bold uppercase text-[var(--primary)] block">
                  Estimasi Konteks
                </span>
                <span className="text-sm font-mono font-bold text-[var(--primary)]">
                  ~{estTotalTokens.toLocaleString()} tokens
                </span>
              </div>
              <Button
                size="sm"
                className="rounded-xl px-5 cursor-pointer"
                onClick={() => setShowExtractSettings(false)}
              >
                Selesai
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: Bilingual Genre Presets */}
      {showPresetsModal && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowPresetsModal(false);
          }}
        >
          <Card className="w-full max-w-lg overflow-hidden shadow-2xl border border-[var(--border)] bg-[var(--card)] rounded-2xl flex flex-col">
            <div className="p-5 border-b border-[var(--border)] flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-[var(--primary)]" />
                <h2 className="text-base font-bold text-[var(--foreground)]">
                  Terapkan Preset Glosarium Genre
                </h2>
              </div>
              <button
                onClick={() => setShowPresetsModal(false)}
                className="p-1.5 hover:bg-[var(--secondary)] rounded-full text-[var(--muted-foreground)] cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto custom-scrollbar">
              <div className="p-3.5 rounded-xl bg-[var(--secondary)]/40 border border-[var(--border)] flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-[var(--foreground)]">
                    Bahasa Preset:
                  </span>
                  <div className="flex bg-[var(--card)] rounded-lg p-0.5 border border-[var(--border)]">
                    <button
                      type="button"
                      onClick={() => setPresetLanguage("Indonesian")}
                      className={cn(
                        "px-2.5 py-1 rounded-md text-xs font-bold cursor-pointer transition-colors",
                        presetLanguage === "Indonesian"
                          ? "bg-[var(--primary)] text-white"
                          : "text-[var(--muted-foreground)]"
                      )}
                    >
                      🇮🇩 Indonesia
                    </button>
                    <button
                      type="button"
                      onClick={() => setPresetLanguage("English")}
                      className={cn(
                        "px-2.5 py-1 rounded-md text-xs font-bold cursor-pointer transition-colors",
                        presetLanguage === "English"
                          ? "bg-[var(--primary)] text-white"
                          : "text-[var(--muted-foreground)]"
                      )}
                    >
                      🇬🇧 English
                    </button>
                  </div>
                </div>
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={presetLockEntries}
                    onChange={(e) => setPresetLockEntries(e.target.checked)}
                    className="rounded accent-[var(--primary)]"
                  />
                  <span className="font-semibold text-[var(--muted-foreground)]">
                    Kunci semua istilah preset (🔒)
                  </span>
                </label>
              </div>

              {presets.map((preset) => (
                <div
                  key={preset.key}
                  className="p-4 rounded-xl border border-[var(--border)] bg-[var(--secondary)]/10 hover:border-[var(--primary)]/30 transition-all flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-sm text-[var(--foreground)]">
                      {preset.name}
                    </span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-[var(--primary)]/10 text-[var(--primary)]">
                      {preset.entry_count} istilah
                    </span>
                  </div>
                  <p className="text-xs text-[var(--muted-foreground)]">
                    {preset.description}
                  </p>
                  <Button
                    size="sm"
                    className="mt-1 w-full rounded-xl text-xs cursor-pointer"
                    onClick={() => handleApplyPreset(preset.key)}
                    disabled={isApplyingPreset !== null}
                  >
                    {isApplyingPreset === preset.key ? (
                      <>
                        <Loader2 size={12} className="animate-spin mr-1.5" />{" "}
                        Menerapkan...
                      </>
                    ) : (
                      `Terapkan Preset (${presetLanguage})`
                    )}
                  </Button>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* MODAL 3: Bulk Import Glossary (JSON / Text) */}
      {showImportModal && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
          onClick={(e) => {
            if (e.target === e.currentTarget) setShowImportModal(false);
          }}
        >
          <Card className="w-full max-w-lg overflow-hidden shadow-2xl border border-[var(--border)] bg-[var(--card)] rounded-2xl">
            <div className="p-5 border-b border-[var(--border)] flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Upload className="w-5 h-5 text-[var(--primary)]" />
                <h2 className="text-base font-bold text-[var(--foreground)]">
                  Impor Glosarium (JSON atau Daftar Teks)
                </h2>
              </div>
              <button
                onClick={() => setShowImportModal(false)}
                className="p-1.5 hover:bg-[var(--secondary)] rounded-full text-[var(--muted-foreground)] cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <CardContent className="p-5 space-y-4">
              <p className="text-xs text-[var(--muted-foreground)]">
                Tempelkan array JSON hasil Export, atau daftar baris dengan
                format{" "}
                <code className="px-1.5 py-0.5 rounded bg-[var(--secondary)] font-mono">
                  IstilahAsli -&gt; Terjemahan | Catatan
                </code>
                .
              </p>
              <Textarea
                value={importText}
                onChange={(e) => setImportText(e.target.value)}
                placeholder={
                  "林动 -> Lin Dong | Tokoh utama\n青檀 -> Qingtan | Adik perempuan"
                }
                className="min-h-[180px] font-mono text-xs bg-[var(--background)] border-[var(--border)] rounded-xl"
              />
              <div className="flex justify-end gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowImportModal(false)}
                  className="rounded-xl"
                >
                  Batal
                </Button>
                <Button
                  size="sm"
                  onClick={handleImportGlossary}
                  disabled={isBulkProcessing || !importText.trim()}
                  className="rounded-xl px-5 cursor-pointer"
                >
                  {isBulkProcessing ? (
                    <Loader2 size={13} className="animate-spin mr-1.5" />
                  ) : null}{" "}
                  Impor Sekarang
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
