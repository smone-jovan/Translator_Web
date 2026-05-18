/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable react-refresh/only-export-components */
/* eslint-disable react-hooks/set-state-in-effect */
import React, { useState, useEffect, useRef } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import IconButton from '@mui/material/IconButton';
import { UploadCloud, Link as LinkIcon, Sparkles, Trash2, Check, AlertCircle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface EditCoverModalProps {
  isOpen: boolean;
  onClose: () => void;
  threadId: number;
  threadTitle: string;
  currentCover: string | null;
  onSave: (coverValue: string | null) => Promise<void>;
}

// Helper to generate seeded gradient from title
export const getTitleGradient = (title: string) => {
  let hash = 0;
  for (let i = 0; i < title.length; i++) {
    hash = title.charCodeAt(i) + ((hash << 5) - hash);
  }
  
  // High saturation premium hues (HSL)
  const hue1 = Math.abs(hash % 360);
  const hue2 = Math.abs((hash + 80) % 360);
  
  return `linear-gradient(135deg, hsl(${hue1}, 75%, 35%) 0%, hsl(${hue2}, 85%, 20%) 100%)`;
};

export default function EditCoverModal({
  isOpen,
  onClose,
  threadTitle,
  currentCover,
  onSave
}: EditCoverModalProps) {
  const [activeTab, setActiveTab] = useState<'upload' | 'url'>('upload');
  const [urlInput, setUrlInput] = useState('');
  const [base64Image, setBase64Image] = useState<string | null>(null);
  const [previewSrc, setPreviewSrc] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Initialize values
  useEffect(() => {
    if (isOpen) {
      setErrorMsg(null);
      setBase64Image(null);
      
      if (currentCover) {
        setPreviewSrc(currentCover);
        if (currentCover.startsWith('http')) {
          setActiveTab('url');
          setUrlInput(currentCover);
        } else {
          setActiveTab('upload');
          setUrlInput('');
        }
      } else {
        setPreviewSrc(null);
        setUrlInput('');
        setActiveTab('upload');
      }
    }
  }, [isOpen, currentCover]);

  // Handle URL change
  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setUrlInput(val);
    if (val.trim()) {
      setPreviewSrc(val.trim());
      setErrorMsg(null);
    } else {
      setPreviewSrc(null);
    }
  };

  // Image Compressor (Aspect ratio 3:4, max width 320px, compressed quality 0.75)
  const compressImage = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = (event) => {
        const img = new Image();
        img.src = event.target?.result as string;
        img.onload = () => {
          try {
            const canvas = document.createElement('canvas');
            const targetWidth = 300;
            const targetHeight = 400; // Exact 3:4 ratio

            canvas.width = targetWidth;
            canvas.height = targetHeight;
            const ctx = canvas.getContext('2d');
            
            if (ctx) {
              // Center crop calculation
              let srcX = 0;
              let srcY = 0;
              let srcWidth = img.width;
              let srcHeight = img.height;

              const imgRatio = img.width / img.height;
              const targetRatio = 3 / 4;

              if (imgRatio > targetRatio) {
                // Image is wider than 3:4
                srcWidth = img.height * targetRatio;
                srcX = (img.width - srcWidth) / 2;
              } else {
                // Image is taller than 3:4
                srcHeight = img.width / targetRatio;
                srcY = (img.height - srcHeight) / 2;
              }

              ctx.drawImage(img, srcX, srcY, srcWidth, srcHeight, 0, 0, targetWidth, targetHeight);
            }

            const dataUrl = canvas.toDataURL('image/jpeg', 0.75);
            resolve(dataUrl);
          } catch (err) {
            reject(err);
          }
        };
        img.onerror = () => reject(new Error('Failed to load image file.'));
      };
      reader.onerror = () => reject(new Error('Failed to read image file.'));
    });
  };

  // Process selected file
  const processFile = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      setErrorMsg('Please select a valid image file (PNG, JPG, WEBP).');
      return;
    }

    try {
      setErrorMsg(null);
      const compressed = await compressImage(file);
      setBase64Image(compressed);
      setPreviewSrc(compressed);
    } catch (err) {
      console.error(err);
      setErrorMsg('Failed to process and compress cover image.');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      processFile(files[0]);
    }
  };

  // Drag and Drop
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      processFile(files[0]);
    }
  };

  // Reset to gradient fallback
  const handleResetCover = () => {
    setBase64Image(null);
    setUrlInput('');
    setPreviewSrc(null);
    setErrorMsg(null);
  };

  // Handle Save
  const handleSaveClick = async () => {
    setIsSaving(true);
    setErrorMsg(null);
    try {
      const coverValue = activeTab === 'upload' ? base64Image : urlInput.trim();
      // If we cleared the cover completely, save as null
      const finalVal = previewSrc === null ? null : (coverValue || previewSrc);
      
      await onSave(finalVal);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to save custom book cover.');
    } finally {
      setIsSaving(false);
    }
  };

  // Generate title initials for fallback design
  const getInitials = (text: string) => {
    if (!text) return 'N/A';
    const cleanText = text.replace(/[^\w\s\u4e00-\u9fa5]/g, '').trim();
    const parts = cleanText.split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    // Handle single word or Chinese characters
    return text.substring(0, 2).toUpperCase();
  };

  const currentGradient = getTitleGradient(threadTitle);

  return (
    <Dialog
      open={isOpen}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      // @ts-expect-error: PaperProps uses standard sx override styling which MUI type definition warns on under strict configs
      PaperProps={{
        sx: {
          background: 'var(--card)',
          border: '1px solid var(--border)',
          color: 'var(--foreground)',
          borderRadius: '16px',
          padding: '8px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 10px 10px -5px rgba(0, 0, 0, 0.4)',
          overflow: 'hidden'
        }
      }}
    >
      <div className="flex justify-between items-center px-6 py-4 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-[var(--primary)]/10 text-[var(--primary)]">
            <Sparkles size={18} />
          </div>
          <div>
            <DialogTitle style={{ padding: 0, fontSize: '1.1rem', fontWeight: 700 }} className="text-[var(--foreground)]">
              Customize Book Cover
            </DialogTitle>
            <p className="text-[11px] text-[var(--muted-foreground)] line-clamp-1 mt-0.5">
              {threadTitle}
            </p>
          </div>
        </div>
        <IconButton 
          onClick={onClose} 
          size="small" 
          sx={{ color: 'var(--muted-foreground)', '&:hover': { color: 'var(--foreground)', background: 'rgba(255,255,255,0.05)' } }}
        >
          <X size={18} />
        </IconButton>
      </div>

      <DialogContent className="p-6 flex flex-col md:flex-row gap-6 mt-2">
        {/* Left Side: Forms */}
        <div className="flex-1 flex flex-col justify-between space-y-5">
          {/* Tab Headers */}
          <div className="flex bg-[var(--secondary)] p-1 rounded-lg border border-[var(--border)]">
            <button
              onClick={() => setActiveTab('upload')}
              className={`flex-1 py-2 text-xs font-bold rounded-md flex items-center justify-center gap-1.5 transition-all ${
                activeTab === 'upload'
                  ? 'bg-[var(--card)] text-[var(--primary)] shadow-sm'
                  : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
              }`}
            >
              <UploadCloud size={14} />
              Upload Image
            </button>
            <button
              onClick={() => setActiveTab('url')}
              className={`flex-1 py-2 text-xs font-bold rounded-md flex items-center justify-center gap-1.5 transition-all ${
                activeTab === 'url'
                  ? 'bg-[var(--card)] text-[var(--primary)] shadow-sm'
                  : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
              }`}
            >
              <LinkIcon size={14} />
              Paste URL
            </button>
          </div>

          {/* Tab Panel Upload */}
          {activeTab === 'upload' && (
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center gap-3 cursor-pointer transition-all ${
                isDragOver
                  ? 'border-[var(--primary)] bg-[var(--primary)]/5 scale-[0.99]'
                  : 'border-[var(--border)] hover:border-[var(--primary)]/40 hover:bg-[var(--secondary)]/30'
              }`}
            >
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept="image/*"
                className="hidden"
              />
              <div className="w-12 h-12 rounded-full bg-[var(--secondary)] border border-[var(--border)] flex items-center justify-center text-[var(--muted-foreground)] group-hover:text-[var(--primary)]">
                <UploadCloud size={24} />
              </div>
              <div className="text-center">
                <p className="text-xs font-bold text-[var(--foreground)]">Drag & drop your cover image here</p>
                <p className="text-[10px] text-[var(--muted-foreground)] mt-1">PNG, JPG, WEBP formats. Crop to 3:4 recommended.</p>
              </div>
              <Button size="sm" variant="outline" className="text-[11px] h-8 mt-1 border-[var(--border)] pointer-events-none">
                Browse Files
              </Button>
            </div>
          )}

          {/* Tab Panel URL */}
          {activeTab === 'url' && (
            <div className="space-y-2">
              <label className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Image Web URL</label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="https://example.com/novel-cover.jpg"
                  value={urlInput}
                  onChange={handleUrlChange}
                  className="w-full bg-[var(--input)] border border-[var(--border)] rounded-lg py-2.5 px-3.5 pr-10 text-xs text-[var(--foreground)] focus:outline-none focus:border-[var(--primary)]"
                />
                <div className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)]">
                  <LinkIcon size={14} />
                </div>
              </div>
              <p className="text-[10px] text-[var(--muted-foreground)]">
                Provide a direct link to any image file (e.g., from Pinterest, novel updates, etc.).
              </p>
            </div>
          )}

          {/* Error Message */}
          {errorMsg && (
            <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-lg text-xs">
              <AlertCircle size={14} className="mt-0.5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Helper Actions */}
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleResetCover}
              disabled={previewSrc === null}
              className="text-[11px] h-8 font-semibold flex items-center gap-1.5 text-red-400 hover:text-red-500 hover:bg-red-500/5 border-[var(--border)]"
            >
              <Trash2 size={12} />
              Reset to Default Cover
            </Button>
          </div>
        </div>

        {/* Right Side: Visual 3:4 Preview Column */}
        <div className="w-[180px] shrink-0 mx-auto flex flex-col items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)] self-start">Live Preview</span>
          
          <div className="relative w-full aspect-[3/4] rounded-xl overflow-hidden shadow-2xl border border-[var(--border)] group/preview bg-[var(--secondary)]">
            {previewSrc ? (
              <img
                src={previewSrc}
                alt="Book cover preview"
                className="w-full h-full object-cover"
                onError={() => {
                  setErrorMsg('Invalid or broken image URL. Please check the address.');
                }}
              />
            ) : (
              // Seeded dynamic gradient generator based on title
              <div 
                className="w-full h-full p-4 flex flex-col justify-between items-center text-center select-none"
                style={{ background: currentGradient }}
              >
                {/* Visual Accent */}
                <div className="w-8 h-1 bg-white/30 rounded-full mt-2" />
                
                {/* Stylized initials in middle */}
                <div className="w-16 h-16 rounded-full bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-xl font-black text-white tracking-widest">
                  {getInitials(threadTitle)}
                </div>
                
                {/* Mini Title below */}
                <div className="w-full mb-1">
                  <p className="text-[10px] font-black text-white/95 uppercase tracking-widest line-clamp-2 px-1 leading-tight">
                    {threadTitle}
                  </p>
                </div>
              </div>
            )}

            {/* Source badge overlay */}
            <div className="absolute top-2 right-2 px-1.5 py-0.5 rounded bg-black/40 backdrop-blur-md text-[8px] font-black text-white uppercase tracking-widest">
              {previewSrc ? (previewSrc.startsWith('data:') ? 'LOKAL' : 'URL') : 'DEFAULT'}
            </div>
          </div>
          
          <p className="text-[10px] text-[var(--muted-foreground)] text-center max-w-[150px] leading-tight">
            Fits the library bookshelf beautifully.
          </p>
        </div>
      </DialogContent>

      <DialogActions className="px-6 py-4 border-t border-[var(--border)] flex justify-end gap-2 bg-[var(--secondary)]/20">
        <Button
          variant="outline"
          onClick={onClose}
          disabled={isSaving}
          className="text-xs h-9 font-semibold border-[var(--border)]"
        >
          Cancel
        </Button>
        <Button
          onClick={handleSaveClick}
          disabled={isSaving}
          className="text-xs h-9 font-bold bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 flex items-center gap-1.5"
        >
          {isSaving ? (
            <div className="w-3.5 h-3.5 border-2 border-[var(--primary-foreground)] border-t-transparent rounded-full animate-spin" />
          ) : (
            <Check size={14} />
          )}
          Save Cover
        </Button>
      </DialogActions>
    </Dialog>
  );
}
