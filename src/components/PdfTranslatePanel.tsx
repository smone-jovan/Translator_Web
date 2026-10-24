import { useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  joinPageTranslations,
  translatePdf,
  type PdfTranslateEvent,
} from "@/lib/pdfTranslate";

interface PageResult {
  index: number;
  text: string;
  failed: boolean;
}

interface PdfTranslatePanelProps {
  model: string;
  /** ZIPs and images picked here are handed to the image folder panel. */
  onOtherFiles: (files: File[]) => void;
}

const PDF_NAME = /\.pdf$/i;
const isPdf = (file: File) => PDF_NAME.test(file.name) || file.type === "application/pdf";

export function PdfTranslatePanel({
  model,
  onOtherFiles,
}: PdfTranslatePanelProps) {
  const [totalPages, setTotalPages] = useState(0);
  const [results, setResults] = useState<PageResult[]>([]);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleEvent = (event: PdfTranslateEvent) => {
    if (event.type === "start") {
      setTotalPages(event.pages);
    } else if (event.type === "page") {
      setResults((prev) => [
        ...prev,
        { index: event.index, text: event.translation, failed: false },
      ]);
    } else if (event.type === "page_error") {
      setResults((prev) => [
        ...prev,
        { index: event.index, text: event.error, failed: true },
      ]);
    }
  };

  const handleFile = async (file: File) => {
    const controller = new AbortController();
    abortRef.current = controller;
    setResults([]);
    setTotalPages(0);
    setRunning(true);
    try {
      await translatePdf({
        file,
        model: model || undefined,
        signal: controller.signal,
        onEvent: handleEvent,
      });
    } catch (error) {
      if (!controller.signal.aborted) {
        toast.error(
          error instanceof Error ? error.message : "PDF translation failed."
        );
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const goodPages = results.filter((r) => !r.failed);
  const combined = joinPageTranslations(goodPages);

  const download = () => {
    const url = URL.createObjectURL(
      new Blob([combined], { type: "text/plain" })
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "translated-pdf.txt";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="rounded-3xl border border-[var(--border)] bg-[var(--card)] p-4 sm:p-6 mb-8">
      <h2 className="text-lg font-semibold text-[var(--foreground)] mb-1">
        Terjemahkan PDF, ZIP, atau gambar
      </h2>
      <p className="text-sm text-[var(--muted-foreground)] mb-4">
        Pilih satu PDF (maks. 20 MB, 50 halaman), satu ZIP berisi gambar, atau
        banyak gambar PNG/JPG sekaligus. Halaman PDF berteks diterjemahkan
        langsung, halaman scan/komik dibaca sebagai gambar. Hasil ZIP dan
        gambar tampil di panel di bawah ini. Butuh model Index-Translate.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={fileInputRef}
          type="file"
          multiple
          disabled={running}
          className="text-sm"
          onChange={(e) => {
            // No `accept`: Chrome on Android greys out files that do not match it (e.g. .zip).
            const picked = Array.from(e.target.files ?? []);
            e.target.value = "";
            const pdfs = picked.filter(isPdf);
            if (picked.length === 0) return;
            if (pdfs.length === 0) onOtherFiles(picked);
            else if (pdfs.length === picked.length)
              void handleFile(pdfs[0]);
            else toast.error("Pilih PDF saja, atau ZIP/gambar saja.");
          }}
        />
        {running && (
          <Button variant="outline" onClick={() => abortRef.current?.abort()}>
            Batal
          </Button>
        )}
        {!running && goodPages.length > 0 && (
          <>
            <Button
              variant="outline"
              onClick={() => void navigator.clipboard.writeText(combined)}
            >
              Salin
            </Button>
            <Button variant="outline" onClick={download}>
              Unduh .txt
            </Button>
          </>
        )}
      </div>
      {totalPages > 0 && (
        <p
          className="mt-3 text-sm text-[var(--muted-foreground)]"
          aria-live="polite"
        >
          Halaman {results.length}/{totalPages}
        </p>
      )}
      <div className="mt-3 space-y-3">
        {results.map((r) => (
          <div key={r.index}>
            <div className="text-xs font-medium text-[var(--muted-foreground)]">
              Halaman {r.index + 1}
            </div>
            <p
              className={`whitespace-pre-wrap text-sm ${r.failed ? "text-red-500" : "text-[var(--foreground)]"}`}
            >
              {r.text}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
