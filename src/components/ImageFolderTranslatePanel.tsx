import { useRef, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  exportImagesPdf,
  findZipFile,
  joinPageTranslations,
  sortImageFiles,
  translateImages,
  type OverlayBox,
  type PdfTranslateEvent,
} from "@/lib/pdfTranslate";

interface PageResult {
  index: number;
  text: string;
  failed: boolean;
  boxes?: OverlayBox[];
}

interface ImageFolderTranslatePanelProps {
  model: string;
}

const FAILED_PAGE_TEXT = "[halaman ini gagal diterjemahkan]";
// React's typings do not know the non-standard folder-picker attribute.
const FOLDER_ATTRIBUTES = { webkitdirectory: "" } as Record<string, string>;

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function ImageFolderTranslatePanel({
  model,
}: ImageFolderTranslatePanelProps) {
  const [files, setFiles] = useState<File[]>([]);
  // A ZIP is one uploaded file but many pages, so the page count and names come from the server.
  const [pageNames, setPageNames] = useState<string[]>([]);
  const [results, setResults] = useState<PageResult[]>([]);
  // Phone browsers cannot pick a folder (the folder input degrades to a plain file picker).
  const [canPickFolder] = useState(
    () => !window.matchMedia("(pointer: coarse)").matches
  );
  const [running, setRunning] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [overlay, setOverlay] = useState(false);
  const [includeTextPages, setIncludeTextPages] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  const handleEvent = (event: PdfTranslateEvent) => {
    if (event.type === "start") {
      setPageNames(
        event.names ?? Array.from({ length: event.pages }, () => "")
      );
    } else if (event.type === "page") {
      setResults((prev) => [
        ...prev,
        {
          index: event.index,
          text: event.translation,
          failed: false,
          boxes: event.boxes,
        },
      ]);
    } else if (event.type === "page_error") {
      setResults((prev) => [
        ...prev,
        { index: event.index, text: event.error, failed: true },
      ]);
    }
  };

  const start = async (picked: FileList | null) => {
    const zip = findZipFile(picked ?? []);
    const sorted = zip ? [zip] : sortImageFiles(Array.from(picked ?? []));
    if (sorted.length === 0) {
      toast.error("Tidak ada gambar PNG/JPG atau file ZIP di pilihan ini.");
      return;
    }
    const controller = new AbortController();
    abortRef.current = controller;
    setFiles(sorted);
    setPageNames(zip ? [] : sorted.map((file) => file.name));
    setResults([]);
    setRunning(true);
    try {
      await translateImages({
        files: sorted,
        model: model || undefined,
        overlay,
        signal: controller.signal,
        onEvent: handleEvent,
      });
    } catch (error) {
      if (!controller.signal.aborted) {
        toast.error(
          error instanceof Error ? error.message : "Image translation failed."
        );
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  };

  const goodPages = results.filter((r) => !r.failed);
  const combined = joinPageTranslations(goodPages);

  const exportPdf = async () => {
    const byIndex = new Map(results.map((r) => [r.index, r]));
    const translations = pageNames.map((_, i) => {
      const page = byIndex.get(i);
      return page && !page.failed ? page.text : FAILED_PAGE_TEXT;
    });
    const boxes = pageNames.map((_, i) => byIndex.get(i)?.boxes ?? []);
    const hasBoxes = boxes.some((page) => page.length > 0);
    setExporting(true);
    try {
      saveBlob(
        await exportImagesPdf(files, translations, {
          boxes: hasBoxes ? boxes : undefined,
          // Without overlaid pages the translation text would be missing from the PDF entirely.
          includeTextPages: hasBoxes ? includeTextPages : true,
        }),
        "translated-images.pdf"
      );
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "PDF export failed."
      );
    } finally {
      setExporting(false);
    }
  };

  const finished = !running && results.length > 0;

  return (
    <section className="rounded-3xl border border-[var(--border)] bg-[var(--card)] p-4 sm:p-6 mb-8">
      <h2 className="text-lg font-semibold text-[var(--foreground)] mb-1">
        Terjemahkan folder gambar
      </h2>
      <p className="text-sm text-[var(--muted-foreground)] mb-4">
        Pilih folder (atau banyak gambar) PNG/JPG, maks. 60 gambar, 10 MB per
        gambar. Urutan mengikuti nama file. Hasilnya bisa diunduh sebagai PDF
        (gambar lalu terjemahannya). Butuh model Index-Translate.
      </p>
      <div className="mb-4 space-y-1 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={overlay}
            disabled={running}
            onChange={(e) => setOverlay(e.target.checked)}
          />
          Timpa terjemahan ke gambar (manga, jauh lebih lambat: satu permintaan
          per gelembung teks)
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={includeTextPages}
            disabled={!overlay}
            onChange={(e) => setIncludeTextPages(e.target.checked)}
          />
          Sertakan juga halaman teks terjemahan di PDF
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-4">
        {canPickFolder && (
          <label className="text-sm">
            <span className="mr-2">Folder:</span>
            <input
              type="file"
              multiple
              disabled={running}
              {...FOLDER_ATTRIBUTES}
              onChange={(e) => {
                void start(e.target.files);
                e.target.value = "";
              }}
            />
          </label>
        )}
        <label className="text-sm">
          <span className="mr-2">ZIP berisi gambar:</span>
          <input
            type="file"
            accept=".zip,application/zip,application/x-zip-compressed"
            disabled={running}
            onChange={(e) => {
              void start(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
        <label className="text-sm">
          <span className="mr-2">
            {canPickFolder
              ? "atau gambar:"
              : "atau pilih gambar (bisa banyak sekaligus):"}
          </span>
          <input
            type="file"
            multiple
            accept="image/png,image/jpeg"
            disabled={running}
            onChange={(e) => {
              void start(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
        {running && (
          <Button variant="outline" onClick={() => abortRef.current?.abort()}>
            Batal
          </Button>
        )}
        {finished && (
          <>
            <Button variant="outline" onClick={exportPdf} disabled={exporting}>
              {exporting ? "Membuat PDF..." : "Unduh PDF"}
            </Button>
            <Button
              variant="outline"
              onClick={() => void navigator.clipboard.writeText(combined)}
            >
              Salin teks
            </Button>
          </>
        )}
      </div>
      {pageNames.length > 0 && (
        <p
          className="mt-3 text-sm text-[var(--muted-foreground)]"
          aria-live="polite"
        >
          Gambar {results.length}/{pageNames.length}
        </p>
      )}
      <div className="mt-3 space-y-3">
        {results.map((r) => (
          <div key={r.index}>
            <div className="text-xs font-medium text-[var(--muted-foreground)]">
              {pageNames[r.index] || `Halaman ${r.index + 1}`}
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
