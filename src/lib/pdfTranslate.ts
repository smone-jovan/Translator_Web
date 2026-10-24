import { getApiUrl } from "@/lib/api";

export interface OverlayBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  text: string;
}

export type PdfTranslateEvent =
  | { type: "start"; pages: number }
  | {
      type: "page";
      index: number;
      mode: "text" | "image" | "overlay";
      translation: string;
      boxes?: OverlayBox[];
    }
  | { type: "page_error"; index: number; error: string }
  | { type: "done"; model_used: string };

interface StreamOptions {
  signal?: AbortSignal;
  onEvent: (event: PdfTranslateEvent) => void;
}

export interface PdfTranslateOptions extends StreamOptions {
  file: File;
  model?: string;
  targetLang?: string;
}

export interface ImagesTranslateOptions extends StreamOptions {
  files: readonly File[];
  model?: string;
  targetLang?: string;
  /** Detect text boxes and translate each one so the PDF export can draw it over the page. */
  overlay?: boolean;
}

export interface ExportImagesPdfOptions {
  /** One list of boxes per image, same order as the files. */
  boxes?: readonly (readonly OverlayBox[])[];
  includeTextPages?: boolean;
}

async function throwHttpError(res: Response, fallback: string): Promise<never> {
  const err = await res.json().catch(() => ({}));
  throw new Error(typeof err.detail === "string" ? err.detail : fallback);
}

/** POSTs a multipart form and reads the NDJSON page events; throws with the server's message on HTTP errors. */
async function streamNdjson(
  path: string,
  form: FormData,
  { signal, onEvent }: StreamOptions
): Promise<void> {
  const res = await fetch(getApiUrl(path), {
    method: "POST",
    body: form,
    signal,
  });
  if (!res.ok) return throwHttpError(res, "Translation failed");

  const reader = res.body?.getReader();
  if (!reader) throw new Error("Response body is not readable");

  const decoder = new TextDecoder();
  let buffer = "";
  const flush = (line: string) => {
    const trimmed = line.trim();
    if (trimmed) onEvent(JSON.parse(trimmed) as PdfTranslateEvent);
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    lines.forEach(flush);
  }
  flush(buffer);
}

function buildForm(
  files: readonly File[],
  fileField: string,
  model?: string,
  targetLang?: string
): FormData {
  const form = new FormData();
  files.forEach((file) => form.append(fileField, file));
  if (model) form.append("model", model);
  if (targetLang) form.append("target_lang", targetLang);
  return form;
}

export function translatePdf({
  file,
  model,
  targetLang,
  ...stream
}: PdfTranslateOptions): Promise<void> {
  return streamNdjson(
    "/api/translate/pdf",
    buildForm([file], "file", model, targetLang),
    stream
  );
}

export function translateImages({
  files,
  model,
  targetLang,
  overlay,
  ...stream
}: ImagesTranslateOptions): Promise<void> {
  const form = buildForm(files, "files", model, targetLang);
  if (overlay) form.append("overlay", "true");
  return streamNdjson("/api/translate/images", form, stream);
}

/** Returns the PDF (each image followed by its translation) built from the same files, in the same order. */
export async function exportImagesPdf(
  files: readonly File[],
  translations: readonly string[],
  { boxes, includeTextPages = true }: ExportImagesPdfOptions = {}
): Promise<Blob> {
  const form = buildForm(files, "files");
  form.append("translations", JSON.stringify(translations));
  if (boxes) form.append("boxes", JSON.stringify(boxes));
  if (!includeTextPages) form.append("include_text_pages", "false");
  const res = await fetch(getApiUrl("/api/translate/images/export-pdf"), {
    method: "POST",
    body: form,
  });
  if (!res.ok) return throwHttpError(res, "PDF export failed");
  return res.blob();
}

const IMAGE_NAME = /\.(png|jpe?g)$/i;

/** Keeps PNG/JPEG files and orders them like a file manager does (page2 before page10). */
export function sortImageFiles(files: Iterable<File>): File[] {
  const key = (file: File) => file.webkitRelativePath || file.name;
  return [...files]
    .filter((file) => IMAGE_NAME.test(file.name))
    .sort((a, b) => key(a).localeCompare(key(b), undefined, { numeric: true }));
}

export function joinPageTranslations(
  pages: ReadonlyArray<{ index: number; text: string }>
): string {
  return [...pages]
    .sort((a, b) => a.index - b.index)
    .map((p) => `--- Halaman ${p.index + 1} ---\n${p.text}`)
    .join("\n\n");
}
