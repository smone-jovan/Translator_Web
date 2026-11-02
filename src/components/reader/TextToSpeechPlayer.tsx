import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import {
  Play,
  Pause,
  Square,
  SkipForward,
  SkipBack,
  Volume2,
  X,
  Gauge,
  ChevronDown,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface TextToSpeechPlayerProps {
  text: string;
  title?: string;
  displayMode?: string;
  onClose: () => void;
}

function cleanTextForSpeech(raw: string): string[] {
  if (!raw) return [];

  // Strip html tags and markdown syntax like headers, asterisks, links
  const cleaned = raw
    .replace(/<[^>]*>/g, " ")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/[#*_~`>]/g, "")
    .replace(/&nbsp;/g, " ")
    .trim();

  // Split into chunks by double newline or sentence boundaries to prevent speech synthesis cutoffs
  const rawParagraphs = cleaned.split(/\n+/);
  const chunks: string[] = [];

  for (const p of rawParagraphs) {
    const trimmed = p.trim();
    if (!trimmed) continue;

    // If paragraph is long (> 250 chars), split by sentence boundaries (supports both Latin and Asian punctuation)
    if (trimmed.length > 250) {
      const sentences =
        trimmed.match(/[^.!?。！？\n]+[.!?。！？]+|\s*[^.!?。！？\n]+$/g) || [
          trimmed,
        ];
      let currentSubChunk = "";
      for (const s of sentences) {
        if (s.length > 250) {
          if (currentSubChunk.trim()) {
            chunks.push(currentSubChunk.trim());
            currentSubChunk = "";
          }
          for (let i = 0; i < s.length; i += 200) {
            const slice = s.slice(i, i + 200).trim();
            if (slice) chunks.push(slice);
          }
        } else if ((currentSubChunk + " " + s).length > 250) {
          if (currentSubChunk.trim()) chunks.push(currentSubChunk.trim());
          currentSubChunk = s;
        } else {
          currentSubChunk += (currentSubChunk ? " " : "") + s;
        }
      }
      if (currentSubChunk.trim()) chunks.push(currentSubChunk.trim());
    } else {
      chunks.push(trimmed);
    }
  }

  return chunks;
}

export default function TextToSpeechPlayer({
  text,
  title,
  displayMode,
  onClose,
}: TextToSpeechPlayerProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [rate, setRate] = useState<number>(1.0);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<SpeechSynthesisVoice | null>(null);
  const [showVoiceSelect, setShowVoiceSelect] = useState(false);

  const paragraphs = useMemo(() => cleanTextForSpeech(text), [text]);
  const isSupported = typeof window !== "undefined" && "speechSynthesis" in window;

  const currentIdxRef = useRef(currentIdx);
  const isPlayingRef = useRef(isPlaying);
  const isPausedRef = useRef(isPaused);
  const rateRef = useRef(rate);
  const voiceRef = useRef(selectedVoice);
  const speakCurrentParagraphRef = useRef<(index: number) => void>(() => {});

  useEffect(() => {
    currentIdxRef.current = currentIdx;
    isPlayingRef.current = isPlaying;
    isPausedRef.current = isPaused;
    rateRef.current = rate;
    voiceRef.current = selectedVoice;
  });

function detectTextLanguage(sampleText: string, displayMode?: string): string {
  if (displayMode === "translated" || displayMode === "both") {
    return "id-ID";
  }
  if (/[\u3040-\u30ff]/.test(sampleText)) {
    return "ja-JP";
  }
  if (/[\u4e00-\u9fff]/.test(sampleText)) {
    return "zh-CN";
  }
  if (/[\uac00-\ud7af]/.test(sampleText)) {
    return "ko-KR";
  }
  return "en-US";
}

  // Load available speech synthesis voices
  useEffect(() => {
    if (!isSupported) return;

    const updateVoices = () => {
      const available = window.speechSynthesis.getVoices();
      setVoices(available);

      // Match voice based on detected text language (supports ja, zh, ko, id, en)
      const detectedLang = detectTextLanguage(text, displayMode);
      const targetLangPrefix = detectedLang.split("-")[0].toLowerCase();

      const matched = available.find((v) =>
        v.lang.toLowerCase().startsWith(targetLangPrefix)
      );
      const fallback = available.find((v) => v.default) || available[0] || null;
      setSelectedVoice(matched || fallback);
    };

    updateVoices();
    window.speechSynthesis.onvoiceschanged = updateVoices;
    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, [displayMode, isSupported, text]);

  // Clean up speech when component unmounts
  useEffect(() => {
    return () => {
      if (isSupported) {
        window.speechSynthesis.cancel();
      }
    };
  }, [isSupported]);

  const speakCurrentParagraph = useCallback(
    (index: number) => {
      if (!isSupported || index >= paragraphs.length || index < 0) {
        setIsPlaying(false);
        setIsPaused(false);
        return;
      }

      window.speechSynthesis.cancel();

      const chunk = paragraphs[index];
      const utterance = new SpeechSynthesisUtterance(chunk);
      utterance.rate = rateRef.current;
      if (voiceRef.current) {
        utterance.voice = voiceRef.current;
        utterance.lang = voiceRef.current.lang;
      } else {
        utterance.lang = detectTextLanguage(chunk, displayMode);
      }

      utterance.onend = () => {
        if (!isPlayingRef.current || isPausedRef.current) return;
        const nextIdx = currentIdxRef.current + 1;
        if (nextIdx < paragraphs.length) {
          setCurrentIdx(nextIdx);
          speakCurrentParagraphRef.current(nextIdx);
        } else {
          setIsPlaying(false);
          setIsPaused(false);
          setCurrentIdx(0);
        }
      };

      utterance.onerror = (e) => {
        if (e.error === "canceled" || e.error === "interrupted") return;
        console.error("SpeechSynthesis error:", e);
        setIsPlaying(false);
        setIsPaused(false);
      };

      window.speechSynthesis.speak(utterance);
    },
    [displayMode, isSupported, paragraphs]
  );

  useEffect(() => {
    speakCurrentParagraphRef.current = speakCurrentParagraph;
  }, [speakCurrentParagraph]);

  const handlePlay = () => {
    if (!isSupported || paragraphs.length === 0) return;

    if (isPaused) {
      if (window.speechSynthesis.paused) {
        window.speechSynthesis.resume();
      } else {
        speakCurrentParagraph(currentIdx);
      }
      setIsPaused(false);
      setIsPlaying(true);
    } else {
      setIsPlaying(true);
      setIsPaused(false);
      speakCurrentParagraph(currentIdx);
    }
  };

  const handlePause = () => {
    if (!isSupported) return;
    window.speechSynthesis.pause();
    setIsPaused(true);
  };

  const handleStop = () => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    setIsPlaying(false);
    setIsPaused(false);
    setCurrentIdx(0);
  };

  const handlePrev = () => {
    const prev = Math.max(0, currentIdx - 1);
    setCurrentIdx(prev);
    if (isPlaying) {
      speakCurrentParagraph(prev);
    }
  };

  const handleNext = () => {
    const next = Math.min(paragraphs.length - 1, currentIdx + 1);
    setCurrentIdx(next);
    if (isPlaying) {
      speakCurrentParagraph(next);
    }
  };

  const cycleRate = () => {
    const rates = [0.8, 1.0, 1.25, 1.5, 2.0];
    const curIdx = rates.indexOf(rate);
    const nextRate = rates[(curIdx + 1) % rates.length];
    setRate(nextRate);
    rateRef.current = nextRate;
    if (isPlaying && !isPaused) {
      speakCurrentParagraph(currentIdx);
    }
  };

  if (!isSupported) {
    return (
      <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 bg-[var(--card)] border border-[var(--border)] rounded-2xl shadow-xl px-4 py-2 text-xs text-[var(--muted-foreground)] flex items-center gap-2">
        <span>Peramban tidak mendukung Web Speech API (TTS).</span>
        <Button variant="ghost" size="icon" onClick={onClose} className="w-6 h-6">
          <X className="w-3.5 h-3.5" />
        </Button>
      </div>
    );
  }

  return (
    <div
      role="region"
      aria-label="Text to Speech Player"
      className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 w-[92%] max-w-lg bg-[var(--card)]/95 backdrop-blur-2xl border border-[var(--border)] rounded-2xl shadow-2xl p-3 sm:p-4 text-[var(--foreground)] animate-in slide-in-from-bottom-5 duration-200 select-none"
    >
      {/* Top row: Title & progress & close */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-7 h-7 rounded-xl bg-[var(--primary)]/10 text-[var(--primary)] flex items-center justify-center shrink-0">
            <Volume2 className="w-4 h-4 animate-pulse" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-bold truncate">
              {title || "Membaca Bab Ini"}
            </p>
            <p className="text-[10px] text-[var(--muted-foreground)]">
              {paragraphs.length > 0
                ? `Paragraf ${currentIdx + 1} dari ${paragraphs.length}`
                : "Tidak ada teks"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {/* Rate button */}
          <button
            onClick={cycleRate}
            className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] font-bold bg-[var(--secondary)] border border-[var(--border)] hover:bg-[var(--secondary)]/80 transition-colors"
            title="Kecepatan Bicara"
          >
            <Gauge className="w-3 h-3 text-[var(--primary)]" />
            <span>{rate}x</span>
          </button>

          {/* Close button */}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => {
              handleStop();
              onClose();
            }}
            className="w-7 h-7 rounded-lg text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            title="Tutup TTS"
          >
            <X className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Preview current spoken text snippet */}
      {paragraphs[currentIdx] && (
        <div className="mb-3 px-2.5 py-1.5 rounded-xl bg-[var(--secondary)]/40 border border-[var(--border)]/50 text-[11px] text-[var(--muted-foreground)] line-clamp-2 italic leading-relaxed">
          "{paragraphs[currentIdx]}"
        </div>
      )}

      {/* Main Controls */}
      <div className="flex items-center justify-between gap-2">
        {/* Voice Selector Toggle */}
        <div className="relative">
          <button
            onClick={() => setShowVoiceSelect((prev) => !prev)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded-xl text-[10px] font-semibold bg-[var(--secondary)]/50 hover:bg-[var(--secondary)] border border-[var(--border)] max-w-[130px] sm:max-w-[160px] truncate"
            title={selectedVoice?.name || "Pilih Suara"}
          >
            <span className="truncate">{selectedVoice?.name || "Suara Default"}</span>
            <ChevronDown className="w-3 h-3 shrink-0 opacity-60" />
          </button>

          {showVoiceSelect && (
            <div className="absolute bottom-full left-0 mb-1 w-56 max-h-48 overflow-y-auto bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-xl p-1 z-20 space-y-0.5">
              {voices.map((v) => (
                <button
                  key={`${v.name}-${v.lang}`}
                  onClick={() => {
                    setSelectedVoice(v);
                    voiceRef.current = v;
                    setShowVoiceSelect(false);
                    if (isPlaying && !isPaused) {
                      speakCurrentParagraph(currentIdx);
                    }
                  }}
                  className={`w-full text-left px-2 py-1.5 rounded-lg text-[10px] truncate transition-colors ${
                    selectedVoice?.name === v.name
                      ? "bg-[var(--primary)] text-white font-bold"
                      : "hover:bg-[var(--secondary)] text-[var(--foreground)]"
                  }`}
                >
                  <span className="font-bold">[{v.lang}]</span> {v.name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Playback action buttons */}
        <div className="flex items-center gap-1.5">
          <Button
            variant="outline"
            size="icon"
            onClick={handlePrev}
            disabled={currentIdx === 0}
            className="w-8 h-8 rounded-xl border-[var(--border)]"
            title="Paragraf Sebelumnya"
          >
            <SkipBack className="w-3.5 h-3.5" />
          </Button>

          {isPlaying && !isPaused ? (
            <Button
              variant="default"
              size="icon"
              onClick={handlePause}
              className="w-10 h-10 rounded-xl bg-[var(--primary)] text-[var(--primary-foreground)] shadow-lg shadow-[var(--primary)]/20"
              title="Jeda"
            >
              <Pause className="w-4 h-4" />
            </Button>
          ) : (
            <Button
              variant="default"
              size="icon"
              onClick={handlePlay}
              disabled={paragraphs.length === 0}
              className="w-10 h-10 rounded-xl bg-[var(--primary)] text-[var(--primary-foreground)] shadow-lg shadow-[var(--primary)]/20"
              title={isPaused ? "Lanjutkan" : "Mulai Membaca"}
            >
              <Play className="w-4 h-4 ml-0.5 fill-current" />
            </Button>
          )}

          <Button
            variant="outline"
            size="icon"
            onClick={handleStop}
            disabled={!isPlaying && !isPaused}
            className="w-8 h-8 rounded-xl border-[var(--border)]"
            title="Hentikan"
          >
            <Square className="w-3.5 h-3.5" />
          </Button>

          <Button
            variant="outline"
            size="icon"
            onClick={handleNext}
            disabled={currentIdx >= paragraphs.length - 1}
            className="w-8 h-8 rounded-xl border-[var(--border)]"
            title="Paragraf Berikutnya"
          >
            <SkipForward className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
