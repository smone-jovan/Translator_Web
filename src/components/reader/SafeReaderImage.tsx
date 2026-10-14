import React, { useState, useCallback } from "react";
import { RefreshCw, ImageOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface SafeReaderImageProps {
  src: string;
  alt?: string;
  className?: string;
}

export default function SafeReaderImage({
  src,
  alt,
  className,
}: SafeReaderImageProps) {
  const [hasError, setHasError] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  const getEffectiveSrc = useCallback(() => {
    if (retryKey === 0) return src;
    const sep = src.includes("?") ? "&" : "?";
    return `${src}${sep}force=true&t=${retryKey}`;
  }, [src, retryKey]);

  const handleRetry = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsRetrying(true);
    setHasError(false);
    setRetryKey(Date.now());
  };

  if (hasError) {
    return (
      <span className="my-6 p-4 rounded-2xl border border-rose-500/30 bg-rose-500/5 max-w-sm mx-auto text-center space-y-2.5 shadow-sm block">
        <span className="w-10 h-10 rounded-xl bg-rose-500/10 text-rose-400 mx-auto flex items-center justify-center">
          <ImageOff className="w-5 h-5" />
        </span>
        <span
          className="block text-xs font-bold text-[var(--foreground)] truncate"
          title={alt}
        >
          {alt && alt !== "Image" ? alt : "Illustration"} failed to load
        </span>
        <span className="block text-[11px] text-[var(--muted-foreground)]">
          Network timeout or image blocked by host.
        </span>
        <Button
          size="sm"
          variant="outline"
          onClick={handleRetry}
          disabled={isRetrying}
          className="rounded-xl h-8 px-3 gap-1.5 border-rose-500/30 text-rose-400 hover:bg-rose-500/10 font-bold text-xs mx-auto"
        >
          <RefreshCw
            className={cn("w-3.5 h-3.5", isRetrying && "animate-spin")}
          />
          <span>{isRetrying ? "Retrying..." : "Refresh Image"}</span>
        </Button>
      </span>
    );
  }

  return (
    <span className="relative block max-w-full my-4 mx-auto text-center group">
      <img
        src={getEffectiveSrc()}
        alt={alt || "Image"}
        loading="lazy"
        onLoad={() => setIsRetrying(false)}
        onError={() => {
          setHasError(true);
          setIsRetrying(false);
        }}
        className={
          className ||
          "max-w-full h-auto rounded-xl border border-[var(--border)] shadow-sm mx-auto block"
        }
      />
      {/* Quick hover refresh icon */}
      <button
        type="button"
        onClick={handleRetry}
        title="Refresh / Reload illustration"
        className="absolute top-2 right-2 p-1.5 rounded-lg bg-black/60 text-white opacity-90 sm:opacity-0 sm:group-hover:opacity-80 hover:opacity-100 transition-opacity duration-200 cursor-pointer border-none shadow"
      >
        <RefreshCw
          className={cn("w-3.5 h-3.5", isRetrying && "animate-spin")}
        />
      </button>
    </span>
  );
}
