import { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Loader2, Image as ImageIcon, ChevronLeft, ChevronRight, X, 
  BookOpen, ZoomIn, ZoomOut, Download, ImageOff, RefreshCw
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getApiUrl, API_BASE } from '@/lib/api';
import { cn } from '@/lib/utils';

export interface ThreadImageItem {
  url: string;
  chapter_id: number;
  chapter_order: number;
  chapter_title: string;
  alt?: string;
  image_index?: number;
  total_in_chapter?: number;
}

interface ThreadImageGalleryProps {
  threadId: number;
  chapterSearch?: string;
  onSelectChapter: (chapterId: number) => void;
}

export default function ThreadImageGallery({
  threadId,
  chapterSearch = '',
  onSelectChapter,
}: ThreadImageGalleryProps) {
  const [images, setImages] = useState<ThreadImageItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null);
  const [lightboxZoom, setLightboxZoom] = useState(1);
  const [touchStartX, setTouchStartX] = useState<number | null>(null);

  // Per-image error and retry states
  const [failedUrls, setFailedUrls] = useState<Record<string, boolean>>({});
  const [retryingUrls, setRetryingUrls] = useState<Record<string, boolean>>({});
  const [retryKeys, setRetryKeys] = useState<Record<string, number>>({});

  const fetchImages = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(getApiUrl(`/api/threads/${threadId}/images`));
      if (res.ok) {
        const data = await res.json();
        setImages(data.images || []);
      }
    } catch (err) {
      console.error('Failed to load thread images', err);
    } finally {
      setLoading(false);
    }
  }, [threadId]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchImages();
  }, [fetchImages]);

  const getProxiedUrl = (url: string) => {
    let base = url;
    if (url.startsWith('/images/')) {
      base = `${API_BASE}${url}`;
    } else if (url.startsWith('http://') || url.startsWith('https://')) {
      base = `${API_BASE}/api/images/proxy?url=${encodeURIComponent(url)}`;
    }
    const key = retryKeys[url];
    if (key) {
      const sep = base.includes('?') ? '&' : '?';
      return `${base}${sep}force=true&t=${key}`;
    }
    return base;
  };

  const handleRefreshSingleImage = (url: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setRetryingUrls(prev => ({ ...prev, [url]: true }));
    setFailedUrls(prev => ({ ...prev, [url]: false }));
    setRetryKeys(prev => ({ ...prev, [url]: Date.now() }));
  };

  const handleRefreshAllFailed = () => {
    const now = Date.now();
    const failedList = Object.entries(failedUrls)
      .filter(([, hasErr]) => hasErr)
      .map(([u]) => u);

    if (failedList.length === 0) return;

    const nextRetrying = { ...retryingUrls };
    const nextFailed = { ...failedUrls };
    const nextKeys = { ...retryKeys };

    failedList.forEach(u => {
      nextRetrying[u] = true;
      nextFailed[u] = false;
      nextKeys[u] = now;
    });

    setRetryingUrls(nextRetrying);
    setFailedUrls(nextFailed);
    setRetryKeys(nextKeys);
  };

  const filteredImages = useMemo(() => {
    if (!chapterSearch.trim()) return images;
    const q = chapterSearch.toLowerCase();
    return images.filter(img => 
      img.chapter_title.toLowerCase().includes(q) ||
      img.chapter_order.toString().includes(q) ||
      (img.alt && img.alt.toLowerCase().includes(q))
    );
  }, [images, chapterSearch]);

  const currentLightboxImage = lightboxIndex !== null ? filteredImages[lightboxIndex] : null;

  const handleNext = useCallback(() => {
    if (lightboxIndex !== null && lightboxIndex < filteredImages.length - 1) {
      setLightboxIndex(lightboxIndex + 1);
      setLightboxZoom(1);
    }
  }, [lightboxIndex, filteredImages.length]);

  const handlePrev = useCallback(() => {
    if (lightboxIndex !== null && lightboxIndex > 0) {
      setLightboxIndex(lightboxIndex - 1);
      setLightboxZoom(1);
    }
  }, [lightboxIndex]);

  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchStartX(e.touches[0].clientX);
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (touchStartX === null) return;
    const diff = touchStartX - e.changedTouches[0].clientX;
    if (diff > 40) {
      handleNext();
    } else if (diff < -40) {
      handlePrev();
    }
    setTouchStartX(null);
  };

  const handleCloseLightbox = useCallback(() => {
    setLightboxIndex(null);
    setLightboxZoom(1);
  }, []);

  // Keyboard navigation for Lightbox
  useEffect(() => {
    if (lightboxIndex === null) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleCloseLightbox();
      if (e.key === 'ArrowRight') handleNext();
      if (e.key === 'ArrowLeft') handlePrev();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [lightboxIndex, handleCloseLightbox, handleNext, handlePrev]);

  const totalFailedCount = useMemo(() => {
    return filteredImages.filter(img => failedUrls[img.url]).length;
  }, [filteredImages, failedUrls]);

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-20 flex flex-col items-center justify-center text-center space-y-4">
        <Loader2 className="w-8 h-8 text-[var(--primary)] animate-spin" />
        <p className="text-sm font-semibold text-[var(--muted-foreground)]">
          Scanning novel for illustrations...
        </p>
      </div>
    );
  }

  if (images.length === 0) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-20 flex flex-col items-center justify-center text-center space-y-3">
        <div className="w-14 h-14 rounded-2xl bg-[var(--secondary)] flex items-center justify-center text-[var(--muted-foreground)]">
          <ImageIcon className="w-7 h-7 opacity-60" />
        </div>
        <h3 className="text-base font-bold text-[var(--foreground)]">No Illustrations Found</h3>
        <p className="text-xs text-[var(--muted-foreground)] max-w-sm">
          Chapters in this thread do not contain embedded image tags or illustration covers.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 pb-20">
      {/* Header bar info */}
      <div className="flex items-center justify-between py-4 mb-4 border-b border-[var(--border)]/60 text-xs text-[var(--muted-foreground)] font-semibold flex-wrap gap-2">
        <span>
          Showing <strong className="text-[var(--foreground)]">{filteredImages.length}</strong> {filteredImages.length === 1 ? 'illustration' : 'illustrations'}
          {chapterSearch && ` matching "${chapterSearch}"`}
        </span>
        <div className="flex items-center gap-3">
          {totalFailedCount > 0 && (
            <Button
              size="sm"
              variant="outline"
              onClick={handleRefreshAllFailed}
              className="rounded-xl h-7 px-2.5 gap-1.5 text-xs font-bold border-rose-500/30 text-rose-400 hover:bg-rose-500/10"
            >
              <RefreshCw className="w-3 h-3" />
              <span>Retry Failed ({totalFailedCount})</span>
            </Button>
          )}
          <span className="text-[11px] opacity-70 hidden sm:inline">Click any image to view full-size</span>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {filteredImages.map((item, idx) => (
          <div
            key={`${item.chapter_id}_${idx}`}
            onClick={() => setLightboxIndex(idx)}
            className="group relative rounded-2xl overflow-hidden border border-[var(--border)] bg-[var(--card)] hover:border-[var(--primary)]/60 hover:shadow-lg transition-all duration-200 cursor-pointer flex flex-col"
          >
            {/* Image container with fixed aspect ratio */}
            <div className="relative aspect-[3/4] bg-[var(--secondary)]/40 overflow-hidden">
              {failedUrls[item.url] ? (
                <div 
                  className="w-full h-full flex flex-col items-center justify-center p-3 text-center bg-rose-500/5 space-y-2 cursor-default"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="w-8 h-8 rounded-xl bg-rose-500/10 text-rose-400 flex items-center justify-center">
                    <ImageOff className="w-4 h-4" />
                  </div>
                  <p className="text-[10px] font-bold text-rose-400">Failed to load</p>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={(e) => handleRefreshSingleImage(item.url, e)}
                    disabled={retryingUrls[item.url]}
                    className="rounded-xl h-7 px-2 text-[10px] font-bold gap-1 border-rose-500/30 text-rose-400 hover:bg-rose-500/10"
                  >
                    <RefreshCw className={cn("w-3 h-3", retryingUrls[item.url] && "animate-spin")} />
                    <span>{retryingUrls[item.url] ? "Retrying..." : "Refresh"}</span>
                  </Button>
                </div>
              ) : (
                <img
                  src={getProxiedUrl(item.url)}
                  alt={item.alt || `Ch. ${item.chapter_order}`}
                  loading="lazy"
                  onLoad={() => {
                    if (retryingUrls[item.url]) {
                      setRetryingUrls(prev => ({ ...prev, [item.url]: false }));
                    }
                  }}
                  onError={() => {
                    setFailedUrls(prev => ({ ...prev, [item.url]: true }));
                    setRetryingUrls(prev => ({ ...prev, [item.url]: false }));
                  }}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
              )}
              
              {/* Badge top-left */}
              <div className="absolute top-2 left-2 px-2 py-0.5 rounded-md bg-black/60 backdrop-blur-md text-[10px] font-mono font-bold text-white shadow-sm flex items-center gap-1">
                <span>Ch. {item.chapter_order}</span>
                {item.total_in_chapter && item.total_in_chapter > 1 && (
                  <span className="text-pink-300 font-semibold">
                    ({item.image_index}/{item.total_in_chapter})
                  </span>
                )}
              </div>

              {/* Hover actions overlay (if not failed) */}
              {!failedUrls[item.url] && (
                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center gap-2 p-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectChapter(item.chapter_id);
                    }}
                    className="rounded-xl h-8 px-2.5 gap-1 text-xs font-bold shadow-md hover:bg-white hover:text-black"
                    title="Read this chapter"
                  >
                    <BookOpen className="w-3.5 h-3.5" />
                    <span>Read</span>
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={(e) => handleRefreshSingleImage(item.url, e)}
                    disabled={retryingUrls[item.url]}
                    className="rounded-xl h-8 w-8 p-0 text-xs font-bold shadow-md hover:bg-white hover:text-black"
                    title="Refresh this image"
                  >
                    <RefreshCw className={cn("w-3.5 h-3.5", retryingUrls[item.url] && "animate-spin")} />
                  </Button>
                </div>
              )}
            </div>

            {/* Bottom info */}
            <div className="p-2.5 text-left border-t border-[var(--border)]/40">
              <p className="text-[11px] font-bold text-[var(--foreground)] truncate" title={item.chapter_title}>
                {item.chapter_title}
              </p>
              {item.alt && (
                <p className="text-[10px] text-[var(--muted-foreground)] truncate mt-0.5" title={item.alt}>
                  {item.alt}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Full-Screen Lightbox */}
      {currentLightboxImage && (
        <div 
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex flex-col justify-between p-4 md:p-6 animate-in fade-in duration-200 select-none touch-none"
          onClick={handleCloseLightbox}
          onTouchStart={handleTouchStart}
          onTouchEnd={handleTouchEnd}
        >
          {/* Top toolbar */}
          <div 
            className="flex items-center justify-between text-white z-10"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-left">
              <span className="text-xs font-mono font-bold px-2 py-0.5 bg-white/20 rounded-md mr-2">
                Ch. {currentLightboxImage.chapter_order}
                {currentLightboxImage.total_in_chapter && currentLightboxImage.total_in_chapter > 1 && (
                  ` (${currentLightboxImage.image_index}/${currentLightboxImage.total_in_chapter})`
                )}
              </span>
              <span className="text-sm font-bold">{currentLightboxImage.chapter_title}</span>
              {currentLightboxImage.alt && (
                <p className="text-xs text-zinc-400 mt-0.5">{currentLightboxImage.alt}</p>
              )}
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleRefreshSingleImage(currentLightboxImage.url)}
                disabled={retryingUrls[currentLightboxImage.url]}
                className="rounded-xl h-8 px-2.5 bg-white/10 text-white border-white/20 hover:bg-white/20 text-xs font-bold gap-1"
                title="Refresh / Redownload this illustration"
              >
                <RefreshCw className={cn("w-3.5 h-3.5", retryingUrls[currentLightboxImage.url] && "animate-spin")} />
                <span className="hidden sm:inline">{retryingUrls[currentLightboxImage.url] ? "Retrying..." : "Refresh"}</span>
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setLightboxZoom(prev => prev === 1 ? 1.5 : 1)}
                className="rounded-xl h-8 px-2.5 bg-white/10 text-white border-white/20 hover:bg-white/20"
                title={lightboxZoom === 1 ? "Zoom In" : "Reset Zoom"}
              >
                {lightboxZoom === 1 ? <ZoomIn className="w-4 h-4" /> : <ZoomOut className="w-4 h-4" />}
              </Button>

              <a
                href={currentLightboxImage.url}
                target="_blank"
                rel="noreferrer"
                download
                className="inline-flex items-center justify-center rounded-xl h-8 px-2.5 bg-white/10 text-white border border-white/20 hover:bg-white/20 text-xs font-bold transition-colors"
                title="Download original file"
              >
                <Download className="w-4 h-4" />
              </a>

              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  handleCloseLightbox();
                  onSelectChapter(currentLightboxImage.chapter_id);
                }}
                className="rounded-xl h-8 px-3 gap-1.5 bg-[var(--primary)] text-white border-none hover:bg-[var(--primary)]/90 font-bold text-xs"
              >
                <BookOpen className="w-3.5 h-3.5" />
                <span>Read Chapter</span>
              </Button>

              <Button
                variant="ghost"
                size="sm"
                onClick={handleCloseLightbox}
                className="rounded-xl h-8 w-8 p-0 text-white hover:bg-white/20"
              >
                <X className="w-5 h-5" />
              </Button>
            </div>
          </div>

          {/* Center Image with navigation */}
          <div 
            className="relative flex-1 flex items-center justify-center overflow-hidden my-4"
            onClick={(e) => e.stopPropagation()}
          >
            {lightboxIndex !== null && lightboxIndex > 0 && (
              <button
                onClick={handlePrev}
                className="absolute left-2 md:left-6 z-20 p-2.5 rounded-full bg-black/60 text-white hover:bg-black/80 transition-all cursor-pointer border-none"
                title="Previous Image (Left Arrow)"
              >
                <ChevronLeft className="w-6 h-6" />
              </button>
            )}

            {failedUrls[currentLightboxImage.url] ? (
              <div 
                className="flex flex-col items-center justify-center p-8 bg-zinc-900/90 rounded-2xl border border-rose-500/30 text-center space-y-4 max-w-sm"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="w-12 h-12 rounded-2xl bg-rose-500/10 text-rose-400 flex items-center justify-center">
                  <ImageOff className="w-6 h-6" />
                </div>
                <div className="space-y-1">
                  <h4 className="text-sm font-bold text-white">Illustration Failed to Load</h4>
                  <p className="text-xs text-zinc-400">
                    The image could not be loaded from the source host.
                  </p>
                </div>
                <Button
                  onClick={() => handleRefreshSingleImage(currentLightboxImage.url)}
                  disabled={retryingUrls[currentLightboxImage.url]}
                  className="rounded-xl h-9 px-4 gap-2 bg-[var(--primary)] text-white font-bold text-xs hover:bg-[var(--primary)]/90"
                >
                  <RefreshCw className={cn("w-3.5 h-3.5", retryingUrls[currentLightboxImage.url] && "animate-spin")} />
                  <span>{retryingUrls[currentLightboxImage.url] ? "Retrying..." : "Refresh Illustration"}</span>
                </Button>
              </div>
            ) : (
              <img
                src={getProxiedUrl(currentLightboxImage.url)}
                alt={currentLightboxImage.alt || currentLightboxImage.chapter_title}
                style={{ transform: `scale(${lightboxZoom})`, transition: 'transform 0.2s ease-out' }}
                onLoad={() => {
                  if (retryingUrls[currentLightboxImage.url]) {
                    setRetryingUrls(prev => ({ ...prev, [currentLightboxImage.url]: false }));
                  }
                }}
                onError={() => {
                  setFailedUrls(prev => ({ ...prev, [currentLightboxImage.url]: true }));
                  setRetryingUrls(prev => ({ ...prev, [currentLightboxImage.url]: false }));
                }}
                className="max-h-[78vh] max-w-[85vw] object-contain rounded-xl shadow-2xl"
              />
            )}

            {lightboxIndex !== null && lightboxIndex < filteredImages.length - 1 && (
              <button
                onClick={handleNext}
                className="absolute right-2 md:right-6 z-20 p-2.5 rounded-full bg-black/60 text-white hover:bg-black/80 transition-all cursor-pointer border-none"
                title="Next Image (Right Arrow)"
              >
                <ChevronRight className="w-6 h-6" />
              </button>
            )}
          </div>

          {/* Bottom counter */}
          <div className="text-center text-xs font-mono text-zinc-400">
            {lightboxIndex !== null ? `${lightboxIndex + 1} / ${filteredImages.length}` : ''}
          </div>
        </div>
      )}
    </div>
  );
}
