import { getApiUrl } from "@/lib/api";

export type PdfTranslateEvent =
  | { type: "start"; pages: number }
  | { type: "page"; index: number; mode: "text" | "image"; translation: string }
  | { type: "page_error"; index: number; error: string }
  | { type: "done"; model_used: string };

export interface PdfTranslateOptions {
  file: File;
  model?: string;
  targetLang?: string;
  signal?: AbortSignal;
  onEvent: (event: PdfTranslateEvent) => void;
}

/** Streams NDJSON page events from POST /api/translate/pdf; throws with the server's message on HTTP errors. */
export async function translatePdf({
  file,
  model,
  targetLang,
  signal,
  onEvent,
}: PdfTranslateOptions): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  if (model) form.append("model", model);
  if (targetLang) form.append("target_lang", targetLang);

  const res = await fetch(getApiUrl("/api/translate/pdf"), {
    method: "POST",
    body: form,
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      typeof err.detail === "string" ? err.detail : "PDF translation failed"
    );
  }

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

export function joinPageTranslations(
  pages: ReadonlyArray<{ index: number; text: string }>
): string {
  return [...pages]
    .sort((a, b) => a.index - b.index)
    .map((p) => `--- Halaman ${p.index + 1} ---\n${p.text}`)
    .join("\n\n");
}
