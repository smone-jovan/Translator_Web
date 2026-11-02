/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect } from "react";
import {
  X,
  FileText,
  ChevronRight,
  ArrowLeft,
  Download,
  AlertTriangle,
  Loader2,
  BookPlus,
  Library,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getApiUrl, invalidateThreadCache } from "@/lib/api";
import { toast } from "sonner";

export interface TxtDraftItem {
  id: string;
  title: string;
  body: string;
  source_chapter_ordinal: number;
  split_ordinal: number;
  split_total: number;
  word_count: number;
  is_oversized: boolean;
}

interface EditableDraft extends TxtDraftItem {
  isIncluded: boolean;
}

interface ThreadSummary {
  id: number;
  title: string;
}

interface TxtImportModalProps {
  open: boolean;
  onClose: () => void;
  initialTitle: string;
  initialDrafts: TxtDraftItem[];
  onSuccess?: (threadId: number) => void;
}

export function TxtImportModal({
  open,
  onClose,
  initialTitle,
  initialDrafts,
  onSuccess,
}: TxtImportModalProps) {
  const [step, setStep] = useState<1 | 2>(1);
  const [bookTitle, setBookTitle] = useState(initialTitle);
  const [author, setAuthor] = useState("");
  const [drafts, setDrafts] = useState<EditableDraft[]>([]);
  const [expandedDrafts, setExpandedDrafts] = useState<Record<string, boolean>>({});

  // Step 2 target state
  const [targetMode, setTargetMode] = useState<"new" | "existing">("new");
  const [selectedThreadId, setSelectedThreadId] = useState<number | null>(null);
  const [existingThreads, setExistingThreads] = useState<ThreadSummary[]>([]);
  const [isLoadingThreads, setIsLoadingThreads] = useState(false);

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Initialize draft states when opening modal or receiving new initial drafts
  useEffect(() => {
    if (!open) return;
    setStep(1);
    setBookTitle(initialTitle);
    setAuthor("");
    const initialEditable = initialDrafts.map((d) => ({
      ...d,
      isIncluded: true,
    }));
    setDrafts(initialEditable);

    const initialExpanded: Record<string, boolean> = {};
    initialDrafts.slice(0, 2).forEach((d) => {
      initialExpanded[d.id] = true;
    });
    setExpandedDrafts(initialExpanded);
    setTargetMode("new");
    setSelectedThreadId(null);
  }, [open, initialTitle, initialDrafts]);

  // Fetch threads for existing thread selection
  useEffect(() => {
    if (!open) return;
    setIsLoadingThreads(true);
    let isCancelled = false;
    fetch(getApiUrl("/api/threads"))
      .then((res) => (res.ok ? res.json() : []))
      .then((data: ThreadSummary[]) => {
        if (!isCancelled) {
          setExistingThreads(data);
          setSelectedThreadId((prev) => (prev ?? (data.length > 0 ? data[0].id : null)));
        }
      })
      .catch(() => {
        // ignore error fetching threads
      })
      .finally(() => {
        if (!isCancelled) setIsLoadingThreads(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [open]);

  if (!open) return null;

  const includedDrafts = drafts.filter((d) => d.isIncluded);
  const totalIncludedWords = includedDrafts.reduce((sum, d) => sum + d.word_count, 0);

  const toggleInclude = (id: string) => {
    setDrafts((prev) =>
      prev.map((d) => (d.id === id ? { ...d, isIncluded: !d.isIncluded } : d))
    );
  };

  const updateDraftTitle = (id: string, newTitle: string) => {
    setDrafts((prev) =>
      prev.map((d) => (d.id === id ? { ...d, title: newTitle } : d))
    );
  };

  const updateDraftBody = (id: string, newBody: string) => {
    setDrafts((prev) =>
      prev.map((d) => (d.id === id ? { ...d, body: newBody } : d))
    );
  };

  const toggleExpand = (id: string) => {
    setExpandedDrafts((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const selectAll = () => {
    setDrafts((prev) => prev.map((d) => ({ ...d, isIncluded: true })));
  };

  const deselectAll = () => {
    setDrafts((prev) => prev.map((d) => ({ ...d, isIncluded: false })));
  };

  const handleNextStep = () => {
    if (includedDrafts.length === 0) {
      toast.error("Please select at least one chapter draft to import.");
      return;
    }
    if (!bookTitle.trim()) {
      toast.error("Please enter a valid book title.");
      return;
    }
    const emptyTitleDraft = includedDrafts.find((d) => !d.title.trim());
    if (emptyTitleDraft) {
      toast.error("One or more selected chapters have an empty title. Please provide a title or exclude them.");
      return;
    }
    const emptyBodyDraft = includedDrafts.find((d) => !d.body.trim());
    if (emptyBodyDraft) {
      toast.error("One or more selected chapters have empty content. Please provide content or exclude them.");
      return;
    }
    setStep(2);
  };

  const handleConfirmAndExport = async () => {
    if (isSubmitting) return; // Prevent double click
    if (includedDrafts.length === 0) {
      toast.error("Please select at least one chapter draft to import.");
      return;
    }
    if (targetMode === "existing" && !selectedThreadId) {
      toast.error("Please select an existing target thread.");
      return;
    }

    setIsSubmitting(true);
    try {
      // 1. Authoritative Confirm Call
      const confirmPayload = {
        title: bookTitle.trim(),
        author: author.trim() || undefined,
        target: {
          mode: targetMode,
          thread_id: targetMode === "existing" ? selectedThreadId : undefined,
        },
        drafts: includedDrafts.map((d) => ({
          title: d.title.trim(),
          body: d.body.trim(),
          source_chapter_ordinal: d.source_chapter_ordinal,
          split_ordinal: d.split_ordinal,
          split_total: d.split_total,
        })),
      };

      const confirmRes = await fetch(getApiUrl("/api/txt-import/confirm"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(confirmPayload),
      });

      if (!confirmRes.ok) {
        const errJson = await confirmRes.json().catch(() => ({}));
        throw new Error(errJson.detail || "Failed to confirm TXT import.");
      }

      const confirmData: { thread_id: number; chapter_ids: number[] } =
        await confirmRes.json();
      invalidateThreadCache(confirmData.thread_id);

      // 2. Export EPUB via authoritative Book Builder
      try {
        const exportRes = await fetch(
          getApiUrl(`/api/threads/${confirmData.thread_id}/export`),
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              format: "epub",
              title: bookTitle.trim(),
              author: author.trim() || undefined,
              chapter_ids: confirmData.chapter_ids,
            }),
          }
        );

        if (exportRes.ok) {
          const blob = await exportRes.blob();
          const downloadUrl = window.URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = downloadUrl;
          const safeName = bookTitle.trim().replace(/[^\w\s\-_]/gi, "_");
          a.download = `${safeName || "Imported_Novel"}.epub`;
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(downloadUrl);

          toast.success(
            `Imported ${confirmData.chapter_ids.length} chapters and downloaded EPUB!`
          );
        } else {
          toast.warning(
            `Imported ${confirmData.chapter_ids.length} chapters to library, but EPUB generation failed. You can export it anytime from Book Builder.`
          );
        }
      } catch {
        toast.warning(
          `Imported ${confirmData.chapter_ids.length} chapters to library, but EPUB generation failed. You can export it anytime from Book Builder.`
        );
      }

      onSuccess?.(confirmData.thread_id);
      onClose();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "TXT import failed.";
      toast.error(message);
      // Retain edits and draft state on error (ADR-139 requirement)
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex sm:items-center sm:justify-center bg-black/70 backdrop-blur-sm p-0 sm:p-4 animate-in fade-in duration-200 overflow-x-hidden">
      <Card className="w-full h-full sm:h-[90vh] sm:max-w-4xl flex flex-col rounded-none sm:rounded-2xl border-0 sm:border border-border bg-card shadow-2xl overflow-hidden max-w-full">
        {/* Top Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-3.5 border-b border-border bg-muted/40 shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-primary/10 text-primary border border-primary/20 shrink-0">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm sm:text-base font-bold text-foreground leading-tight">
                Import TXT to EPUB
              </h2>
              <p className="text-[11px] text-muted-foreground">
                {step === 1
                  ? "Step 1 of 2: Review & Edit Draft Chapters"
                  : "Step 2 of 2: Choose Target & Confirm"}
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            disabled={isSubmitting}
            className="h-8 w-8 rounded-xl text-muted-foreground hover:text-foreground cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden p-3.5 sm:p-6 space-y-4 [scrollbar-width:thin]">
          {step === 1 ? (
            /* STEP 1: REVIEW AND EDIT */
            <div className="space-y-4">
              {/* Novel Metadata inputs */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 sm:p-4 rounded-xl bg-muted/20 border border-border">
                <div className="space-y-1">
                  <label
                    htmlFor="txt-book-title"
                    className="text-xs font-semibold text-foreground flex items-center gap-1"
                  >
                    Book Title <span className="text-red-500">*</span>
                  </label>
                  <input
                    id="txt-book-title"
                    type="text"
                    value={bookTitle}
                    onChange={(e) => setBookTitle(e.target.value)}
                    disabled={isSubmitting}
                    placeholder="Enter book title"
                    className="w-full px-3 py-1.5 text-xs sm:text-sm rounded-lg bg-background border border-border text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
                <div className="space-y-1">
                  <label
                    htmlFor="txt-book-author"
                    className="text-xs font-semibold text-foreground"
                  >
                    Author (Optional)
                  </label>
                  <input
                    id="txt-book-author"
                    type="text"
                    value={author}
                    onChange={(e) => setAuthor(e.target.value)}
                    disabled={isSubmitting}
                    placeholder="e.g. Author name"
                    className="w-full px-3 py-1.5 text-xs sm:text-sm rounded-lg bg-background border border-border text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>
              </div>

              {/* Toolbar: Stats & Bulk Selection */}
              <div className="flex flex-wrap items-center justify-between gap-2 px-1">
                <div className="text-xs text-muted-foreground">
                  Included:{" "}
                  <strong className="text-foreground">
                    {includedDrafts.length}
                  </strong>{" "}
                  of {drafts.length} chapters ({totalIncludedWords.toLocaleString()}{" "}
                  words)
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={selectAll}
                    disabled={isSubmitting}
                    className="text-xs text-primary hover:underline font-medium cursor-pointer"
                  >
                    Select All
                  </button>
                  <span className="text-muted-foreground text-xs">•</span>
                  <button
                    type="button"
                    onClick={deselectAll}
                    disabled={isSubmitting}
                    className="text-xs text-muted-foreground hover:underline font-medium cursor-pointer"
                  >
                    Deselect All
                  </button>
                </div>
              </div>

              {/* Draft List */}
              <div className="space-y-3">
                {drafts.map((draft, idx) => {
                  const isExpanded = !!expandedDrafts[draft.id];
                  return (
                    <div
                      key={draft.id}
                      className={`rounded-xl border transition-colors ${
                        draft.isIncluded
                          ? "border-border bg-card shadow-sm"
                          : "border-border/50 bg-muted/10 opacity-60"
                      }`}
                    >
                      <div className="p-3 sm:p-4 space-y-2.5">
                        {/* Draft Card Header */}
                        <div className="flex items-start sm:items-center justify-between gap-2 flex-wrap sm:flex-nowrap">
                          <div className="flex items-center gap-2 flex-1 min-w-0 sm:min-w-[160px] max-w-full">
                            <input
                              type="checkbox"
                              id={`include-${draft.id}`}
                              aria-label={`Include chapter draft ${idx + 1}: ${draft.title || "untitled"}`}
                              checked={draft.isIncluded}
                              onChange={() => toggleInclude(draft.id)}
                              disabled={isSubmitting}
                              className="h-4 w-4 rounded border-border text-primary focus:ring-primary cursor-pointer shrink-0"
                            />
                            <label
                              htmlFor={`title-${draft.id}`}
                              className="sr-only"
                            >
                              Draft {idx + 1} Title
                            </label>
                            <input
                              id={`title-${draft.id}`}
                              type="text"
                              value={draft.title}
                              onChange={(e) =>
                                updateDraftTitle(draft.id, e.target.value)
                              }
                              disabled={!draft.isIncluded || isSubmitting}
                              className="w-full text-xs sm:text-sm font-semibold bg-transparent border-b border-dashed border-border/80 focus:border-primary focus:outline-none px-1 py-0.5 text-foreground"
                            />
                          </div>

                          <div className="flex items-center gap-1.5 flex-wrap shrink-0 max-w-full">
                            {draft.split_total > 1 && (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-primary/10 text-primary border border-primary/20">
                                Part {draft.split_ordinal}/{draft.split_total}
                              </span>
                            )}
                            <span className="px-2 py-0.5 rounded-full text-[10px] bg-muted text-muted-foreground">
                              {draft.word_count.toLocaleString()} words
                            </span>
                            {draft.is_oversized && (
                              <span
                                className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-500 border border-amber-500/20 flex items-center gap-1"
                                title="Paragraph exceeds 6,000 words without break"
                              >
                                <AlertTriangle className="w-2.5 h-2.5" />
                                Oversized
                              </span>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleExpand(draft.id)}
                              className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground cursor-pointer shrink-0"
                              aria-label={isExpanded ? "Collapse draft content" : "Expand draft content"}
                            >
                              {isExpanded ? (
                                <ChevronUp className="w-3.5 h-3.5" />
                              ) : (
                                <ChevronDown className="w-3.5 h-3.5" />
                              )}
                            </Button>
                          </div>
                        </div>

                        {/* Collapsible / Expandable Body Editor */}
                        {isExpanded ? (
                          <div className="pt-1 space-y-1">
                            <label
                              htmlFor={`body-${draft.id}`}
                              className="text-[11px] font-medium text-muted-foreground"
                            >
                              Draft Content (Paragraph Separator: Blank Line)
                            </label>
                            <textarea
                              id={`body-${draft.id}`}
                              rows={5}
                              value={draft.body}
                              onChange={(e) =>
                                updateDraftBody(draft.id, e.target.value)
                              }
                              disabled={!draft.isIncluded || isSubmitting}
                              className="w-full p-2.5 text-xs font-mono rounded-lg bg-background border border-border text-foreground focus:outline-none focus:ring-1 focus:ring-primary [scrollbar-width:thin]"
                            />
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => toggleExpand(draft.id)}
                            className="text-left w-full text-xs text-muted-foreground truncate cursor-pointer hover:text-foreground"
                            title="Click to view/edit content"
                            aria-label={`Expand content preview for ${draft.title || `Draft ${idx + 1}`}`}
                          >
                            {draft.body.slice(0, 140)}...
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            /* STEP 2: CHOOSE TARGET & CONFIRM */
            <div className="space-y-4 max-w-2xl mx-auto">
              <div className="text-center space-y-1 pb-2">
                <h3 className="text-base font-bold text-foreground">
                  Select Import Destination
                </h3>
                <p className="text-xs text-muted-foreground">
                  Choose where to import the {includedDrafts.length} reviewed
                  chapter drafts.
                </p>
              </div>

              {/* Target Options */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => setTargetMode("new")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setTargetMode("new");
                    }
                  }}
                  aria-pressed={targetMode === "new"}
                  className={`p-4 rounded-xl border-2 transition-all cursor-pointer flex flex-col gap-2 ${
                    targetMode === "new"
                      ? "border-primary bg-primary/5 shadow-sm"
                      : "border-border bg-card hover:border-border/80"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-primary/10 text-primary">
                      <BookPlus className="w-4 h-4" />
                    </div>
                    <span className="text-sm font-bold text-foreground">
                      New Thread
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Creates a dedicated new book in your library titled{" "}
                    <strong className="text-foreground">
                      &quot;{bookTitle}&quot;
                    </strong>
                    .
                  </p>
                </div>

                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => setTargetMode("existing")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setTargetMode("existing");
                    }
                  }}
                  aria-pressed={targetMode === "existing"}
                  className={`p-4 rounded-xl border-2 transition-all cursor-pointer flex flex-col gap-2 ${
                    targetMode === "existing"
                      ? "border-primary bg-primary/5 shadow-sm"
                      : "border-border bg-card hover:border-border/80"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-secondary text-foreground">
                      <Library className="w-4 h-4" />
                    </div>
                    <span className="text-sm font-bold text-foreground">
                      Existing Thread
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Appends these drafts after existing chapters in an already
                    created book.
                  </p>
                </div>
              </div>

              {/* Existing Thread Selector */}
              {targetMode === "existing" && (
                <div className="p-4 rounded-xl bg-muted/20 border border-border space-y-2.5 animate-in fade-in duration-150">
                  <label
                    htmlFor="existing-thread-select"
                    className="text-xs font-semibold text-foreground flex items-center justify-between"
                  >
                    <span>Target Existing Book</span>
                    {isLoadingThreads && (
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Loader2 className="w-3 h-3 animate-spin" /> Loading...
                      </span>
                    )}
                  </label>
                  {existingThreads.length === 0 ? (
                    <p className="text-xs text-muted-foreground italic">
                      No existing threads found in active workspace. Please choose
                      &quot;New Thread&quot;.
                    </p>
                  ) : (
                    <select
                      id="existing-thread-select"
                      value={selectedThreadId ?? ""}
                      onChange={(e) =>
                        setSelectedThreadId(Number(e.target.value))
                      }
                      disabled={isSubmitting}
                      className="w-full px-3 py-2 text-xs sm:text-sm rounded-lg bg-background border border-border text-foreground focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
                    >
                      {existingThreads.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.title} (ID #{t.id})
                        </option>
                      ))}
                    </select>
                  )}
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    ℹ️ Selected drafts are appended after the highest chapter
                    order. Existing thread title, author, and prior chapters are
                    never replaced or modified.
                  </p>
                </div>
              )}

              {/* Confirmation Summary Card */}
              <div className="p-4 rounded-xl bg-card border border-border space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Import & Export Summary
                </h4>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-muted-foreground">Book Title:</span>
                    <p className="font-semibold text-foreground truncate">
                      {bookTitle}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Author:</span>
                    <p className="font-semibold text-foreground truncate">
                      {author || "—"}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">
                      Chapters to Import:
                    </span>
                    <p className="font-semibold text-foreground">
                      {includedDrafts.length} chapters
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Total Words:</span>
                    <p className="font-semibold text-foreground">
                      {totalIncludedWords.toLocaleString()} words
                    </p>
                  </div>
                </div>
                <div className="pt-2 border-t border-border/60 text-[11px] text-muted-foreground">
                  🚀 Once confirmed, records will be committed and an EPUB
                  containing these imported chapters will be generated and
                  downloaded.
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-between px-3 sm:px-6 py-3 border-t border-border bg-muted/30 shrink-0 gap-2.5">
          {step === 1 ? (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={onClose}
                disabled={isSubmitting}
                className="w-full sm:w-auto rounded-xl text-xs sm:text-sm cursor-pointer shrink-0"
              >
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleNextStep}
                disabled={includedDrafts.length === 0 || isSubmitting}
                className="w-full sm:w-auto rounded-xl text-xs sm:text-sm gap-1.5 cursor-pointer font-semibold max-w-full"
              >
                <span className="truncate">
                  Next: Choose Target ({includedDrafts.length} chapters)
                </span>
                <ChevronRight className="w-4 h-4 shrink-0" />
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setStep(1)}
                disabled={isSubmitting}
                className="w-full sm:w-auto rounded-xl text-xs sm:text-sm gap-1.5 cursor-pointer shrink-0"
              >
                <ArrowLeft className="w-4 h-4 shrink-0" />
                <span>Back to Review</span>
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleConfirmAndExport}
                disabled={
                  isSubmitting ||
                  includedDrafts.length === 0 ||
                  (targetMode === "existing" && !selectedThreadId)
                }
                className="w-full sm:w-auto rounded-xl text-xs sm:text-sm gap-1.5 cursor-pointer font-bold bg-primary text-primary-foreground hover:bg-primary/90 max-w-full"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                    <span className="truncate">Importing & Exporting EPUB...</span>
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 shrink-0" />
                    <span className="truncate">Confirm & Export EPUB</span>
                  </>
                )}
              </Button>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
