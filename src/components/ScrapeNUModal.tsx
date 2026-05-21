import { useState, useEffect } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import IconButton from '@mui/material/IconButton';
import { Search, Sparkles, Check, AlertCircle, X, Globe, Info, ArrowLeft, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getApiUrl } from '@/lib/api';
import { getTitleGradient } from './EditCoverModal';

interface ScrapeNUModalProps {
  isOpen: boolean;
  onClose: () => void;
  threadId: number;
  threadTitle: string;
  threadOriginalTitle: string | null;
  onScrapeSuccess: () => void;
}

interface ScrapedMetadata {
  success?: boolean;
  title: string;
  original_title: string;
  author?: string | null;
  cover_image?: string | null;
  status?: string | null;
  status_coo?: string | null;
  genres?: string | null;
  tags?: string | null;
  synopsis?: string | null;
  detail_url?: string | null;
}

export default function ScrapeNUModal({
  isOpen,
  onClose,
  threadId,
  threadTitle,
  threadOriginalTitle,
  onScrapeSuccess
}: ScrapeNUModalProps) {
  const [originalTitleInput, setOriginalTitleInput] = useState('');
  const [includeCover, setIncludeCover] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<ScrapedMetadata[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<ScrapedMetadata | null>(null);
  const [successData, setSuccessData] = useState<ScrapedMetadata | null>(null);
  const [source, setSource] = useState<'novelupdates' | 'sfacg'>('novelupdates');
  const [searchBy, setSearchBy] = useState<'original' | 'translated'>('original');

  // Initialize values
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => {
        setErrorMsg(null);
        setSuccessData(null);
        setCandidates([]);
        setSelectedCandidate(null);
        setIsSaving(false);
        setIncludeCover(true);
        
        // Auto-detect SFACG source from original title or title
        const isSfacg = (threadOriginalTitle && threadOriginalTitle.includes('sfacg.com')) || 
                        (threadTitle && threadTitle.includes('sfacg.com'));
        
        if (isSfacg) {
          setSource('sfacg');
          setOriginalTitleInput(threadOriginalTitle || threadTitle || '');
        } else {
          setSource('novelupdates');
          setOriginalTitleInput(threadOriginalTitle || threadTitle || '');
        }
        setSearchBy('original');
      }, 0);
    }
  }, [isOpen, threadTitle, threadOriginalTitle]);

  const handleSearchCandidates = async () => {
    if (!originalTitleInput.trim()) {
      setErrorMsg(source === 'sfacg' ? 'SFACG URL or Novel ID cannot be empty.' : 'Original title or URL cannot be empty.');
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);
    setSuccessData(null);
    setCandidates([]);
    setSelectedCandidate(null);

    try {
      const response = await fetch(getApiUrl(`/api/threads/${threadId}/scrape_candidates`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          original_title: originalTitleInput.trim(),
          include_cover: includeCover,
          search_by: searchBy,
          source: source
        })
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || `Server returned error status ${response.status}`);
      }

      const data = await response.json();
      if (data.success && data.candidates && data.candidates.length > 0) {
        setCandidates(data.candidates);
        setSelectedCandidate(data.candidates[0]); // Auto-select the first candidate by default
      } else {
        throw new Error(`No matching candidates found on ${source === 'sfacg' ? 'SFACG' : 'Novel Updates'}.`);
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'An error occurred while connecting to the scraper.';
      setErrorMsg(errMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveMetadata = async () => {
    if (!selectedCandidate) {
      setErrorMsg('Please select a candidate first.');
      return;
    }

    setIsSaving(true);
    setErrorMsg(null);

    try {
      const response = await fetch(getApiUrl(`/api/threads/${threadId}/save_metadata`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: selectedCandidate.title,
          original_title: selectedCandidate.original_title,
          author: selectedCandidate.author,
          genres: selectedCandidate.genres,
          tags: selectedCandidate.tags,
          synopsis: selectedCandidate.synopsis,
          status: selectedCandidate.status,
          status_coo: selectedCandidate.status_coo,
          cover_image: includeCover ? selectedCandidate.cover_image : null,
          detail_url: selectedCandidate.detail_url
        })
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || `Failed to save metadata (status ${response.status})`);
      }

      setSuccessData(selectedCandidate);
      onScrapeSuccess(); // Trigger refresh on parent library
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'An error occurred while saving the metadata.';
      setErrorMsg(errMsg);
    } finally {
      setIsSaving(false);
    }
  };

  const getInitials = (text: string) => {
    if (!text) return 'NU';
    const clean = text.replace(/[^\w\s]/g, '');
    const words = clean.split(/\s+/).filter(Boolean);
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    return text.substring(0, 2).toUpperCase();
  };

  const showSelection = candidates.length > 0 && !successData;

  return (
    <Dialog
      open={isOpen}
      onClose={isLoading || isSaving ? undefined : onClose}
      maxWidth={successData || showSelection ? "md" : "sm"}
      fullWidth
      slotProps={{
        paper: {
          sx: {
            background: 'var(--background)',
            backdropFilter: 'blur(20px)',
            border: '1px solid var(--border)',
            borderRadius: '16px',
            color: 'var(--foreground)',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
          }
        }
      }}
    >
      {/* Title Header */}
      <DialogTitle className="flex justify-between items-center px-6 py-4 border-b border-[var(--border)] bg-[var(--secondary)]/10">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-[var(--primary)]/10 text-[var(--primary)]">
            <Globe size={18} />
          </div>
          <div>
            <h3 className="text-sm font-bold tracking-tight">Scrape Novel Metadata</h3>
            <p className="text-[10px] text-[var(--muted-foreground)]">Enrich tags, genres, synopsis & cover image via Novel Updates or SFACG</p>
          </div>
        </div>
        {!isLoading && !isSaving && (
          <IconButton 
            onClick={onClose} 
            size="small" 
            className="text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)]"
          >
            <X size={16} />
          </IconButton>
        )}
      </DialogTitle>

      {/* Main Content Area */}
      <DialogContent className="p-6">
        {isLoading || isSaving ? (
          // BEAUTIFUL SCANNING LOADING STATE
          <div className="flex flex-col items-center justify-center py-12 gap-6 select-none">
            <div className="relative w-20 h-20">
              {/* Outer Pulsing Glow */}
              <div className="absolute inset-0 rounded-full bg-[var(--primary)]/10 animate-ping" />
              {/* Spinner */}
              <div className="absolute inset-0 rounded-full border-4 border-[var(--border)] border-t-[var(--primary)] animate-spin" />
              {/* Core Sparkle */}
              <div className="absolute inset-4 rounded-full bg-[var(--secondary)] flex items-center justify-center border border-[var(--border)] text-[var(--primary)]">
                <Sparkles size={20} className="animate-pulse" />
              </div>
            </div>
            
            <div className="text-center max-w-[320px] flex flex-col gap-1.5">
              <span className="text-xs font-black tracking-wider text-[var(--foreground)] flex items-center justify-center gap-1.5">
                {isSaving ? 'APPLYING METADATA...' : 'AI CLEANSING & SCRAPING...'} <Sparkles size={12} className="text-[var(--primary)] animate-bounce" />
              </span>
              <p className="text-[11px] text-[var(--muted-foreground)] leading-relaxed">
                {isSaving 
                  ? 'Saving chosen metadata fields and downloading cover images if applicable...'
                  : 'Using local AI model to isolate the core title and scanning sources... This may take up to 15 seconds.'}
              </p>
            </div>
            
            {/* Glowing Scanlines Simulation */}
            <div className="w-full max-w-[280px] h-1.5 bg-[var(--secondary)] rounded-full overflow-hidden relative border border-[var(--border)]">
              <div className="absolute top-0 bottom-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-[var(--primary)] to-transparent animate-shimmer" 
                   style={{
                     animation: 'shimmer 1.5s infinite linear',
                   }}
              />
            </div>
          </div>
        ) : successData ? (
          // GORGEOUS SUCCESS PREVIEW DASHBOARD
          <div className="flex flex-col md:flex-row gap-6">
            {/* Left Cover Preview Column */}
            <div className="w-[160px] shrink-0 mx-auto md:mx-0 flex flex-col items-center gap-2">
              <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted-foreground)] self-start">Cover Image</span>
              
              <div className="relative w-full aspect-[3/4] rounded-xl overflow-hidden shadow-xl border border-[var(--border)] bg-[var(--secondary)]">
                {successData.cover_image ? (
                  <img
                    src={successData.cover_image}
                    alt="Novel Updates Cover"
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div 
                    className="w-full h-full p-4 flex flex-col justify-between items-center text-center select-none"
                    style={{ background: getTitleGradient(successData.title) }}
                  >
                    <div className="w-6 h-0.5 bg-white/30 rounded-full mt-2" />
                    <div className="w-12 h-12 rounded-full bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center text-sm font-black text-white">
                      {getInitials(successData.title)}
                    </div>
                    <div className="w-full mb-1">
                      <p className="text-[9px] font-black text-white/95 uppercase tracking-widest line-clamp-2 px-1 leading-tight">
                        {successData.title}
                      </p>
                    </div>
                  </div>
                )}
                <div className="absolute top-2 right-2 px-1 py-0.5 rounded bg-black/40 backdrop-blur-md text-[7px] font-black text-white uppercase tracking-wider">
                  {successData.cover_image ? 'Scraped' : 'Generated'}
                </div>
              </div>
              
              {/* Scraping Status Badges */}
              <div className="w-full mt-2 flex flex-col gap-1.5">
                {successData.status && (
                  <div className="flex justify-between items-center p-1.5 rounded-lg bg-[var(--secondary)] border border-[var(--border)] text-[9px]">
                    <span className="text-[var(--muted-foreground)] font-semibold">Status:</span>
                    <span className="font-bold text-[var(--primary)]">{successData.status}</span>
                  </div>
                )}
                {successData.status_coo && (
                  <div className="flex flex-col gap-0.5 p-1.5 rounded-lg bg-[var(--secondary)] border border-[var(--border)] text-[9px]">
                    <span className="text-[var(--muted-foreground)] font-semibold">Status in COO:</span>
                    <span className="font-bold text-[var(--foreground)] line-clamp-1">{successData.status_coo}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Right Details Column */}
            <div className="flex-1 flex flex-col gap-4 overflow-hidden">
              <div>
                <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">Official English Title</span>
                <h4 className="text-base font-black tracking-tight text-[var(--foreground)] leading-tight mt-0.5">
                  {successData.title}
                </h4>
                {successData.author && (
                  <p className="text-xs text-[var(--muted-foreground)] mt-1 font-semibold">
                    Author: {successData.author}
                  </p>
                )}
                <p className="text-[10px] text-[var(--primary)] font-bold mt-1 flex items-center gap-1">
                  <Sparkles size={10} /> AI Cleaned Original Title: {successData.original_title}
                </p>
              </div>

              {/* Genres Pills */}
              {successData.genres && (
                <div>
                  <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted-foreground)] block mb-1">Genres</span>
                  <div className="flex flex-wrap gap-1">
                    {successData.genres.split(',').map((g: string, idx: number) => (
                      <span key={idx} className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20 shadow-sm">
                        {g.trim()}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Tags Pills */}
              {successData.tags && (
                <div>
                  <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted-foreground)] block mb-1">Tags</span>
                  <div className="flex flex-wrap gap-1 max-h-[70px] overflow-y-auto pr-1 select-none custom-scrollbar">
                    {successData.tags.split(',').slice(0, 15).map((t: string, idx: number) => (
                      <span key={idx} className="text-[8px] font-semibold px-1.5 py-0.5 rounded bg-[var(--secondary)] text-[var(--muted-foreground)] border border-[var(--border)]">
                        {t.trim()}
                      </span>
                    ))}
                    {successData.tags.split(',').length > 15 && (
                      <span className="text-[8px] font-bold px-1.5 py-0.5 text-[var(--muted-foreground)]">
                        +{successData.tags.split(',').length - 15} more
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Synopsis Box */}
              {successData.synopsis && (
                <div className="flex-1 flex flex-col min-h-[100px]">
                  <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted-foreground)] block mb-1">Synopsis</span>
                  <div className="flex-1 p-3 rounded-xl bg-[var(--secondary)]/40 border border-[var(--border)] overflow-y-auto text-[11px] leading-relaxed text-[var(--muted-foreground)] max-h-[160px] custom-scrollbar italic whitespace-pre-line">
                    {successData.synopsis}
                  </div>
                </div>
              )}

              {/* Success Confirmation Banner */}
              <div className="flex items-center gap-2 p-2.5 bg-green-500/10 border border-green-500/20 text-green-400 rounded-lg text-[10px] font-semibold">
                <Check size={12} className="shrink-0" />
                <span>Successfully synced all metadata and updated the local SQLite database!</span>
              </div>
            </div>
          </div>
        ) : showSelection ? (
          // BEAUTIFUL CANDIDATE SELECTION LAYOUT
          <div className="flex flex-col md:flex-row gap-6 h-[440px]">
            {/* Left Column - Scrollable Candidate Cards */}
            <div className="w-full md:w-[280px] shrink-0 flex flex-col gap-2 overflow-hidden h-full">
              <span className="text-[10px] font-black uppercase tracking-widest text-[var(--muted-foreground)] block">
                Matching Candidates ({candidates.length})
              </span>
              <div className="flex-1 overflow-y-auto pr-1 flex flex-col gap-2 custom-scrollbar">
                {candidates.map((cand, idx) => {
                  const isSelected = selectedCandidate?.detail_url === cand.detail_url;
                  return (
                    <div
                      key={idx}
                      onClick={() => setSelectedCandidate(cand)}
                      className={`p-3 rounded-xl border transition-all duration-200 cursor-pointer flex gap-3 items-center ${
                        isSelected
                          ? 'bg-[var(--primary)]/10 border-[var(--primary)] shadow-md'
                          : 'bg-[var(--secondary)]/40 border-[var(--border)] hover:bg-[var(--secondary)]/70'
                      }`}
                    >
                      {/* Mini Cover Thumbnail */}
                      <div className="w-10 h-14 shrink-0 rounded-md overflow-hidden bg-[var(--secondary)] border border-[var(--border)] relative">
                        {cand.cover_image ? (
                          <img
                            src={cand.cover_image}
                            alt="Cover thumbnail"
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div 
                            className="w-full h-full flex items-center justify-center text-[10px] font-bold text-white"
                            style={{ background: getTitleGradient(cand.title) }}
                          >
                            {getInitials(cand.title)}
                          </div>
                        )}
                      </div>

                      {/* Info snippet */}
                      <div className="flex-1 min-w-0">
                        <h4 className="text-xs font-bold truncate text-[var(--foreground)] leading-tight">
                          {cand.title}
                        </h4>
                        {cand.author && (
                          <p className="text-[10px] text-[var(--muted-foreground)] truncate mt-0.5">
                            by {cand.author}
                          </p>
                        )}
                        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                          {idx === 0 && (
                            <span className="text-[8px] font-black px-1 py-0.5 rounded bg-[var(--primary)]/20 text-[var(--primary)] uppercase tracking-wider">
                              Recommended
                            </span>
                          )}
                          {cand.status && (
                            <span className="text-[8px] font-semibold px-1 py-0.5 rounded bg-[var(--secondary)] text-[var(--muted-foreground)] border border-[var(--border)]">
                              {cand.status.includes('Yes') || cand.status.includes('Completed') ? 'Complete' : 'Ongoing'}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right Column - Highlighted Candidate Metadata Details */}
            <div className="flex-1 flex flex-col border border-[var(--border)] rounded-xl bg-[var(--secondary)]/20 overflow-hidden h-full">
              {selectedCandidate ? (
                <div className="flex-1 p-4 overflow-y-auto custom-scrollbar flex flex-col gap-4">
                  {/* Title + Cover Header */}
                  <div className="flex gap-4 items-start">
                    <div className="w-[70px] aspect-[3/4] rounded-lg overflow-hidden border border-[var(--border)] bg-[var(--secondary)] shrink-0 shadow-md">
                      {selectedCandidate.cover_image ? (
                        <img
                          src={selectedCandidate.cover_image}
                          alt="Cover"
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div 
                          className="w-full h-full flex items-center justify-center text-xs font-black text-white"
                          style={{ background: getTitleGradient(selectedCandidate.title) }}
                        >
                          {getInitials(selectedCandidate.title)}
                        </div>
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-black leading-tight text-[var(--foreground)] break-words">
                        {selectedCandidate.title}
                      </h4>
                      {selectedCandidate.author && (
                        <p className="text-xs text-[var(--muted-foreground)] mt-0.5 font-semibold">
                          Author: {selectedCandidate.author}
                        </p>
                      )}
                      <p className="text-[10px] text-[var(--primary)] font-bold mt-1 flex items-center gap-1">
                        <Sparkles size={10} /> Clean Original Title: {selectedCandidate.original_title}
                      </p>
                      {selectedCandidate.detail_url && (
                        <a
                          href={selectedCandidate.detail_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[10px] text-[var(--primary)] hover:underline mt-1.5 inline-flex items-center gap-1 font-bold"
                        >
                          Open page link <ExternalLink size={10} />
                        </a>
                      )}
                    </div>
                  </div>

                  {/* Status panels */}
                  <div className="grid grid-cols-2 gap-2">
                    {selectedCandidate.status && (
                      <div className="p-2 rounded-lg bg-[var(--secondary)] border border-[var(--border)] text-[10px]">
                        <span className="text-[var(--muted-foreground)] font-semibold block">Status:</span>
                        <span className="font-bold text-[var(--primary)]">{selectedCandidate.status}</span>
                      </div>
                    )}
                    {selectedCandidate.status_coo && (
                      <div className="p-2 rounded-lg bg-[var(--secondary)] border border-[var(--border)] text-[10px]">
                        <span className="text-[var(--muted-foreground)] font-semibold block">Status in COO:</span>
                        <span className="font-bold text-[var(--foreground)] line-clamp-1">{selectedCandidate.status_coo}</span>
                      </div>
                    )}
                  </div>

                  {/* Genres */}
                  {selectedCandidate.genres && (
                    <div>
                      <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted-foreground)] block mb-1">Genres</span>
                      <div className="flex flex-wrap gap-1">
                        {selectedCandidate.genres.split(',').map((g: string, idx: number) => (
                          <span key={idx} className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20">
                            {g.trim()}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tags */}
                  {selectedCandidate.tags && (
                    <div>
                      <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted-foreground)] block mb-1">Tags</span>
                      <div className="flex flex-wrap gap-1 max-h-[80px] overflow-y-auto pr-1 custom-scrollbar">
                        {selectedCandidate.tags.split(',').map((t: string, idx: number) => (
                          <span key={idx} className="text-[8px] font-semibold px-1.5 py-0.5 rounded bg-[var(--secondary)] text-[var(--muted-foreground)] border border-[var(--border)]">
                            {t.trim()}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Synopsis */}
                  {selectedCandidate.synopsis && (
                    <div>
                      <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--muted-foreground)] block mb-1">Synopsis</span>
                      <div className="p-3 rounded-lg bg-[var(--secondary)]/40 border border-[var(--border)] text-[10.5px] leading-relaxed text-[var(--muted-foreground)] italic whitespace-pre-line">
                        {selectedCandidate.synopsis}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center text-[var(--muted-foreground)] p-6 select-none">
                  <Info size={20} className="mb-1 opacity-50" />
                  <p className="text-xs">Choose a candidate from the left list to inspect details.</p>
                </div>
              )}
            </div>
          </div>
        ) : (
          // SETTINGS & TRIGGER INPUT STATE
          <div className="flex flex-col gap-4">
            {/* Metadata Source Selection */}
            <div className="flex flex-col gap-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                Metadata Source
              </span>
              <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-[var(--secondary)] border border-[var(--border)]">
                <button
                  type="button"
                  onClick={() => {
                    setSource('novelupdates');
                    setOriginalTitleInput(threadOriginalTitle || threadTitle || '');
                  }}
                  className={`flex items-center justify-center gap-2 py-2 px-3 text-xs font-bold rounded-lg transition-all duration-200 ${
                    source === 'novelupdates'
                      ? 'bg-[var(--primary)] text-[var(--primary-foreground)] shadow-md'
                      : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)]/60'
                  }`}
                >
                  <Globe size={14} />
                  Novel Updates
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setSource('sfacg');
                    setOriginalTitleInput(threadOriginalTitle && threadOriginalTitle.includes('sfacg.com') ? threadOriginalTitle : '');
                  }}
                  className={`flex items-center justify-center gap-2 py-2 px-3 text-xs font-bold rounded-lg transition-all duration-200 ${
                    source === 'sfacg'
                      ? 'bg-[var(--primary)] text-[var(--primary-foreground)] shadow-md'
                      : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--secondary)]/60'
                  }`}
                >
                  <span>🍍</span>
                  SFACG (菠萝包)
                </button>
              </div>
            </div>

            {/* Novel Updates Specific Options */}
            {source === 'novelupdates' && (
              <div className="flex flex-col gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                  Search Query Type
                </span>
                <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-[var(--secondary)] border border-[var(--border)]">
                  <button
                    type="button"
                    onClick={() => setSearchBy('original')}
                    className={`flex items-center justify-center gap-1.5 py-1.5 px-3 text-[11px] font-semibold rounded-lg transition-all duration-200 ${
                      searchBy === 'original'
                        ? 'bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20 shadow-sm'
                        : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
                    }`}
                  >
                    🇨🇳 Original Title (Hanzi)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSearchBy('translated')}
                    className={`flex items-center justify-center gap-1.5 py-1.5 px-3 text-[11px] font-semibold rounded-lg transition-all duration-200 ${
                      searchBy === 'translated'
                        ? 'bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20 shadow-sm'
                        : 'text-[var(--muted-foreground)] hover:text-[var(--foreground)]'
                    }`}
                  >
                    🇬🇧 Translated Title (English)
                  </button>
                </div>
              </div>
            )}

            {/* Context Info Banner */}
            <div className="flex gap-2.5 p-3 rounded-lg bg-[var(--secondary)] border border-[var(--border)] text-[10.5px] leading-relaxed text-[var(--muted-foreground)]">
              <Info size={16} className="text-[var(--primary)] shrink-0 mt-0.5" />
              <p>
                {source === 'novelupdates' ? (
                  searchBy === 'original' ? (
                    <>
                      Novel Updates maps records based on the <strong>original language title</strong> (Chinese characters). 
                      To ensure correct results, please enter or confirm the Chinese title below. We will use local AI to extract clean title characters.
                      <br/>
                      <strong className="text-[var(--foreground)]">Pro tip:</strong> You can also paste a direct Novel Updates link (e.g. <code>https://www.novelupdates.com/series/...</code>) below to load it instantly.
                    </>
                  ) : (
                    <>
                      Searching Novel Updates using the <strong>translated/English title</strong>.
                      This is helpful if the Chinese characters are messy or unavailable.
                      <br/>
                      <strong className="text-[var(--foreground)]">Pro tip:</strong> You can also paste a direct Novel Updates link (e.g. <code>https://www.novelupdates.com/series/...</code>) below to load it instantly.
                    </>
                  )
                ) : (
                  <>
                    Directly scraping metadata from <strong>SFACG (book.sfacg.com)</strong>.
                    Please paste the SFACG URL or enter the Novel ID below. We will fetch the raw Chinese title, synopsis, genres, and cover directly.
                  </>
                )}
              </p>
            </div>

            {/* Original Title Form Input */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="original-title-input" className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted-foreground)]">
                {source === 'novelupdates' 
                  ? 'Novel Title or Direct Novel Updates URL'
                  : 'SFACG Book URL or Novel ID'
                }
              </label>
              <div className="relative">
                <input
                  id="original-title-input"
                  type="text"
                  value={originalTitleInput}
                  onChange={(e) => {
                    setOriginalTitleInput(e.target.value);
                    setErrorMsg(null);
                  }}
                  placeholder={source === 'novelupdates'
                    ? 'e.g. 我怎么可能是圣女？ or paste https://www.novelupdates.com/series/... link'
                    : 'e.g. https://book.sfacg.com/Novel/529683/ or 529683'
                  }
                  className="w-full bg-[var(--secondary)] border border-[var(--border)] focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] rounded-xl py-2 px-3.5 pr-10 text-xs text-[var(--foreground)] placeholder:text-[var(--muted-foreground)]/60 outline-none transition-all duration-200"
                />
                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--primary)]">
                  <Sparkles size={14} className="animate-pulse" />
                </div>
              </div>
            </div>

            {/* Checkbox controls */}
            <div className="flex items-center gap-2.5 p-3 rounded-xl bg-[var(--secondary)]/40 border border-[var(--border)]">
              <input
                id="update-cover-checkbox"
                type="checkbox"
                checked={includeCover}
                onChange={(e) => setIncludeCover(e.target.checked)}
                className="w-4 h-4 rounded border-[var(--border)] text-[var(--primary)] focus:ring-[var(--primary)] bg-[var(--secondary)]"
              />
              <label htmlFor="update-cover-checkbox" className="text-xs font-semibold text-[var(--foreground)] cursor-pointer select-none">
                Update book cover image with {source === 'sfacg' ? 'SFACG' : 'Novel Updates'} cover
              </label>
            </div>

            {/* Error Message */}
            {errorMsg && (
              <div className="flex items-start gap-2 p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-lg text-xs">
                <AlertCircle size={14} className="mt-0.5 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}
          </div>
        )}
      </DialogContent>

      {/* Footer Actions */}
      <DialogActions className="px-6 py-4 border-t border-[var(--border)] flex justify-end gap-2 bg-[var(--secondary)]/10">
        {successData ? (
          <Button
            onClick={onClose}
            className="text-xs h-9 font-bold bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 flex items-center gap-1.5 px-6 rounded-lg"
          >
            <Check size={14} />
            Done
          </Button>
        ) : showSelection ? (
          <>
            <Button
              variant="outline"
              onClick={() => setCandidates([])}
              className="text-xs h-9 font-semibold border-[var(--border)] rounded-lg mr-auto flex items-center gap-1"
            >
              <ArrowLeft size={12} />
              Back
            </Button>
            <Button
              variant="outline"
              onClick={onClose}
              className="text-xs h-9 font-semibold border-[var(--border)] rounded-lg"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveMetadata}
              disabled={!selectedCandidate}
              className="text-xs h-9 font-bold bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 flex items-center gap-1.5 rounded-lg px-6"
            >
              <Check size={14} />
              Apply Metadata
            </Button>
          </>
        ) : (
          <>
            <Button
              variant="outline"
              onClick={onClose}
              disabled={isLoading}
              className="text-xs h-9 font-semibold border-[var(--border)] rounded-lg"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSearchCandidates}
              disabled={isLoading || !originalTitleInput.trim()}
              className="text-xs h-9 font-bold bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 flex items-center gap-1.5 rounded-lg px-4"
            >
              <Search size={14} />
              Search Candidates
            </Button>
          </>
        )}
      </DialogActions>

      {/* CSS Shimmer Animation for loading simulation */}
      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(300%); }
        }
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: var(--border);
          border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: var(--muted-foreground);
        }
      `}</style>
    </Dialog>
  );
}

