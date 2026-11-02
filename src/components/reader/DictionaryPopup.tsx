import { useState, useEffect, useRef } from "react";
import { Volume2, X, Loader2, BookOpen, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";

interface DefinitionItem {
  definition: string;
  example?: string;
  synonyms?: string[];
}

interface MeaningItem {
  partOfSpeech: string;
  definitions: DefinitionItem[];
}

interface PhoneticItem {
  text?: string;
  audio?: string;
}

interface DictionaryEntry {
  word: string;
  phonetic?: string;
  phonetics?: PhoneticItem[];
  meanings?: MeaningItem[];
}

interface DictionaryPopupProps {
  word: string;
  position: { x: number; y: number };
  onClose: () => void;
  onSpeakWord?: (text: string) => void;
}

export default function DictionaryPopup({
  word,
  position,
  onClose,
  onSpeakWord,
}: DictionaryPopupProps) {
  // Clean word: remove surrounding punctuation, spaces, symbols while supporting full Unicode (CJK, accents, etc.)
  const cleanWord = word
    .replace(/^[\s\p{P}\p{S}]+|[\s\p{P}\p{S}]+$/gu, "")
    .trim()
    .toLowerCase();
  const isInvalidWord = !cleanWord;

  const [loading, setLoading] = useState(true);
  const [entry, setEntry] = useState<DictionaryEntry | null>(null);
  const [error, setError] = useState<string | null>(null);
  const popupRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const effectiveLoading = isInvalidWord ? false : loading;
  const effectiveError = isInvalidWord ? "Kata tidak valid" : error;

  useEffect(() => {
    if (!cleanWord) return;

    let isCancelled = false;
    fetch(`https://api.dictionaryapi.dev/api/v2/entries/en/${encodeURIComponent(cleanWord)}`)
      .then(async (res) => {
        if (isCancelled) return;
        if (!res.ok) {
          if (res.status === 404) {
            setError(`Definisi untuk "${cleanWord}" tidak ditemukan dalam kamus.`);
          } else {
            setError("Gagal memuat kamus (server sibuk).");
          }
          setLoading(false);
          return;
        }
        const data = await res.json();
        if (isCancelled) return;
        if (Array.isArray(data) && data.length > 0) {
          setEntry(data[0]);
        } else {
          setError(`Definisi untuk "${cleanWord}" tidak ditemukan.`);
        }
        setLoading(false);
      })
      .catch((err) => {
        if (isCancelled) return;
        console.error("Dictionary API error:", err);
        setError("Gagal menghubungi layanan kamus.");
        setLoading(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [cleanWord, setEntry, setError, setLoading]);

  // Click outside to dismiss
  useEffect(() => {
    const handlePointerDown = (e: MouseEvent | TouchEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("touchstart", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("touchstart", handlePointerDown);
    };
  }, [onClose]);

  // Pronunciation handler (audio clip or SpeechSynthesis)
  const handlePronounce = () => {
    const audioUrl = entry?.phonetics?.find((p) => p.audio && p.audio.trim().length > 0)?.audio;
    if (audioUrl) {
      if (!audioRef.current) {
        audioRef.current = new Audio(audioUrl);
      } else {
        audioRef.current.src = audioUrl;
      }
      audioRef.current.play().catch(() => {
        if (onSpeakWord) onSpeakWord(cleanWord);
      });
    } else if (onSpeakWord) {
      onSpeakWord(cleanWord);
    }
  };

  // Adjust popup position so it doesn't overflow window viewport
  const viewportWidth = typeof window !== "undefined" ? window.innerWidth : 1000;
  const viewportHeight = typeof window !== "undefined" ? window.innerHeight : 800;
  const popupWidth = Math.min(340, viewportWidth - 32);
  const left = Math.max(16, Math.min(position.x - popupWidth / 2, viewportWidth - popupWidth - 16));
  const top = position.y + 12 > viewportHeight - 260
    ? Math.max(16, position.y - 270)
    : position.y + 12;

  const phoneticText = entry?.phonetic || entry?.phonetics?.find((p) => p.text)?.text;

  return (
    <div
      ref={popupRef}
      role="dialog"
      aria-label="Kamus Pop-up"
      style={{
        position: "fixed",
        left: `${left}px`,
        top: `${top}px`,
        width: `${popupWidth}px`,
        zIndex: 60,
      }}
      className="bg-[var(--card)]/95 backdrop-blur-xl border border-[var(--border)] rounded-2xl shadow-2xl p-4 text-xs font-sans text-[var(--foreground)] animate-in fade-in zoom-in-95 duration-150 select-none"
    >
      {/* Header */}
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-[var(--border)]">
        <div className="flex items-center gap-2 min-w-0">
          <BookOpen className="w-4 h-4 text-[var(--primary)] shrink-0" />
          <span className="font-black text-sm capitalize truncate">{cleanWord}</span>
          {phoneticText && (
            <span className="text-[11px] text-[var(--muted-foreground)] font-mono">
              {phoneticText}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Button
            variant="ghost"
            size="icon"
            onClick={handlePronounce}
            className="w-7 h-7 rounded-lg text-[var(--primary)] hover:bg-[var(--primary)]/10"
            title="Dengarkan pengucapan"
            aria-label="Dengarkan pengucapan kata"
          >
            <Volume2 className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="w-7 h-7 rounded-lg text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            title="Tutup kamus"
            aria-label="Tutup kamus"
          >
            <X className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="max-h-56 overflow-y-auto space-y-2.5 pr-1 select-text">
        {effectiveLoading && (
          <div className="flex items-center justify-center py-6 gap-2 text-[var(--muted-foreground)]">
            <Loader2 className="w-4 h-4 animate-spin text-[var(--primary)]" />
            <span>Mencari definisi...</span>
          </div>
        )}

        {effectiveError && !effectiveLoading && (
          <div className="py-3 text-center space-y-2">
            <p className="text-[var(--muted-foreground)]">{effectiveError}</p>
            <a
              href={`https://en.wiktionary.org/wiki/${encodeURIComponent(cleanWord)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[11px] font-bold text-[var(--primary)] hover:underline"
            >
              Cari di Wiktionary
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        )}

        {entry && !effectiveLoading && (
          <>
            {entry.meanings?.slice(0, 3).map((m, mIdx) => (
              <div key={mIdx} className="space-y-1">
                <div className="flex items-center gap-1.5">
                  <span className="px-1.5 py-0.5 rounded bg-[var(--secondary)] text-[10px] font-bold uppercase tracking-wider text-[var(--primary)]">
                    {m.partOfSpeech}
                  </span>
                </div>
                <ol className="list-decimal list-inside space-y-1 pl-1 text-[11px] leading-relaxed">
                  {m.definitions.slice(0, 2).map((def, dIdx) => (
                    <li key={dIdx} className="text-[var(--foreground)]">
                      <span className="font-medium">{def.definition}</span>
                      {def.example && (
                        <p className="text-[10px] text-[var(--muted-foreground)] italic mt-0.5 pl-3 border-l-2 border-[var(--border)]">
                          "{def.example}"
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            ))}
            <div className="pt-1 text-right">
              <a
                href={`https://en.wiktionary.org/wiki/${encodeURIComponent(cleanWord)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[10px] text-[var(--muted-foreground)] hover:text-[var(--primary)]"
              >
                Selengkapnya di Wiktionary
                <ExternalLink className="w-2.5 h-2.5" />
              </a>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
