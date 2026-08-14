/* eslint-disable react-hooks/exhaustive-deps */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/ban-ts-comment */
/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect, useMemo } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Slider from '@mui/material/Slider';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import CircularProgress from '@mui/material/CircularProgress';
import LinearProgress from '@mui/material/LinearProgress';
import IconButton from '@mui/material/IconButton';
import TextField from '@mui/material/TextField';

import CloudDownload from '@mui/icons-material/CloudDownload';
import PlayArrow from '@mui/icons-material/PlayArrow';
import Close from '@mui/icons-material/Close';
import ListAlt from '@mui/icons-material/ListAlt';
import InfoOutlined from '@mui/icons-material/InfoOutlined';
import Sync from '@mui/icons-material/Sync';
import CheckCircle from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import Language from '@mui/icons-material/Language';
import LinkIcon from '@mui/icons-material/Link';

import { getApiUrl } from '@/lib/api';

export interface BulkFetchChapter {
  id: number;
  order: number;
  title_original: string | null;
  word_count?: number;
  source_url?: string | null;
}

interface BulkFetchModalProps {
  isOpen: boolean;
  onClose: () => void;
  threadId: number;
  threadTitle: string;
  chapters: BulkFetchChapter[];
  onStartBatch: (chapterIds: number[], fetchOnly: boolean) => void;
  onCrawlSuccess?: () => void;
  initialTab?: 'missing' | 'crawl';
}

export default function BulkFetchModal({ 
  isOpen, onClose, threadId, threadTitle, chapters, onStartBatch, onCrawlSuccess, initialTab = 'missing'
}: BulkFetchModalProps) {
  const [activeTab, setActiveTab] = useState<'missing' | 'crawl'>(initialTab);
  
  // Tab 1: Missing DB content states
  const [range, setRange] = useState<number>(5);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isStarting, setIsStarting] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);

  // Tab 2: Crawl Next Web Chapters states
  const [crawlRange, setCrawlRange] = useState<number>(10);
  const [customUrl, setCustomUrl] = useState<string>('');
  const [showCustomUrlInput, setShowCustomUrlInput] = useState(false);
  const [isCrawling, setIsCrawling] = useState(false);
  const [crawlProgress, setCrawlProgress] = useState<{ current: number; total: number; latestTitle: string } | null>(null);
  const [crawlLogs, setCrawlLogs] = useState<string[]>([]);
  const [crawlMessage, setCrawlMessage] = useState<string | null>(null);
  const [crawlError, setCrawlError] = useState<string | null>(null);

  // Chapters missing raw text (word_count is 0 or undefined)
  const missingChapters = useMemo(() => {
    return chapters.filter(c => !c.word_count || c.word_count === 0);
  }, [chapters]);

  // Find latest chapter with a valid source_url
  const anchorChapter = useMemo(() => {
    const valid = chapters.filter(c => c.source_url && c.source_url.trim().length > 0);
    if (valid.length === 0) return null;
    return valid.reduce((max, ch) => (ch.order > max.order ? ch : max), valid[0]);
  }, [chapters]);

  const updateSelection = (quantity: number) => {
    const result = missingChapters.slice(0, quantity).map(c => c.id);
    setSelectedIds(result);
  };

  useEffect(() => {
    if (isOpen) {
      if (!hasInitialized) {
        setActiveTab(initialTab);
        updateSelection(range);
        setCrawlMessage(null);
        setCrawlError(null);
        setCrawlProgress(null);
        setCrawlLogs([]);
        setCustomUrl('');
        setShowCustomUrlInput(!anchorChapter);
        setHasInitialized(true);
      }
    } else {
      setHasInitialized(false);
    }
  }, [isOpen, chapters, hasInitialized, initialTab, anchorChapter]);

  const handleRangeChange = (_: any, newValue: number | number[]) => {
    const val = newValue as number;
    setRange(val);
    updateSelection(val);
  };

  const toggleChapter = (id: number) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const selectAllMissing = () => {
    setSelectedIds(missingChapters.map(c => c.id));
  };

  const deselectAll = () => {
    setSelectedIds([]);
  };

  const handleStartMissingFetch = async () => {
    if (selectedIds.length === 0) {
      alert('Please select at least 1 chapter to fetch!');
      return;
    }
    setIsStarting(true);
    try {
      await onStartBatch(selectedIds, true); // fetchOnly = true
      onClose();
    } finally {
      setIsStarting(false);
    }
  };

  const handleStartCrawl = async () => {
    const effectiveCustomUrl = customUrl.trim();
    if (!anchorChapter && !effectiveCustomUrl) {
      alert('Silakan masukkan link URL awal chapter atau pilih chapter dengan URL sumber.');
      return;
    }

    setIsCrawling(true);
    setCrawlError(null);
    setCrawlMessage(null);
    setCrawlLogs([]);
    setCrawlProgress({ current: 0, total: crawlRange, latestTitle: 'Connecting to web source...' });

    try {
      const payload: Record<string, any> = {
        count: crawlRange,
      };

      if (effectiveCustomUrl) {
        payload.custom_start_url = effectiveCustomUrl;
      } else if (anchorChapter) {
        payload.start_chapter_id = anchorChapter.id;
      }

      const res = await fetch(getApiUrl(`/api/threads/${threadId}/crawl-next`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Failed to start crawler');
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('Response body is not readable');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith('data: ')) continue;
          const dataStr = trimmed.replace(/^data: /, '').trim();
          if (dataStr === '[DONE]') break;

          try {
            const evt = JSON.parse(dataStr);
            if (evt.type === 'start') {
              setCrawlProgress({ current: 0, total: evt.target_count, latestTitle: 'Starting chained crawl...' });
            } else if (evt.type === 'progress') {
              setCrawlProgress({
                current: evt.current,
                total: evt.total,
                latestTitle: evt.chapter ? `Ch ${evt.chapter.order}: ${evt.chapter.title}` : '',
              });
              if (evt.chapter) {
                const logLabel = evt.status === 'skipped_existing'
                  ? `⏩ [Ch ${evt.chapter.order}] Already in DB (${evt.chapter.title})`
                  : `📥 [Ch ${evt.chapter.order}] ${evt.chapter.title}${evt.chapter.is_vip ? ' [VIP LOCKED]' : ' (Saved)'}`;
                setCrawlLogs(prev => [...prev, logLabel]);
              }
            } else if (evt.type === 'complete') {
              setCrawlMessage(evt.message);
              onCrawlSuccess?.();
            } else if (evt.type === 'error') {
              setCrawlError(evt.message);
            }
          } catch {
            // ignore parse err
          }
        }
      }
    } catch (err: any) {
      setCrawlError(err.message || 'Crawl failed due to network error');
    } finally {
      setIsCrawling(false);
      onCrawlSuccess?.();
    }
  };

  const canStartCrawl = (anchorChapter && !showCustomUrlInput) || (showCustomUrlInput && customUrl.trim().startsWith('http'));

  return (
    <Dialog 
      open={isOpen} 
      onClose={isCrawling ? undefined : onClose}
      fullWidth
      maxWidth="sm"
      // @ts-ignore
      PaperProps={{
        sx: {
          background: 'var(--card)', 
          backgroundImage: 'radial-gradient(circle at top left, rgba(59, 130, 246, 0.15), transparent)',
          border: '1px solid var(--border)',
          borderRadius: '28px',
          color: 'var(--foreground)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          overflow: 'hidden'
        }
      }}
    >
      <DialogTitle sx={{ 
        m: 0, p: 3, pb: 1, display: 'flex', alignItems: 'center', gap: 2.5 
      }}>
        <Box sx={{ 
          width: 50, height: 50, borderRadius: '16px', 
          background: activeTab === 'crawl' ? 'linear-gradient(135deg, #0284c7, #3b82f6)' : '#3b82f6',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 8px 20px rgba(59, 130, 246, 0.4)',
          flexShrink: 0
        }}>
          {activeTab === 'crawl' ? (
            <Language sx={{ color: '#fff', fontSize: 26 }} />
          ) : (
            <CloudDownload sx={{ color: '#fff', fontSize: 26 }} />
          )}
        </Box>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 900, color: 'var(--foreground)', letterSpacing: '-0.5px' }}>
            {activeTab === 'crawl' ? 'Bulk Web Chapter Crawler' : 'Bulk Fetch Missing Raw'}
          </Typography>
          <Typography variant="caption" sx={{ color: 'var(--muted-foreground)', fontWeight: 500 }}>
            {threadTitle || 'Download chapter texts without translation'}
          </Typography>
        </Box>
        {!isCrawling && (
          <IconButton
            onClick={onClose}
            sx={{
              color: 'rgba(255,255,255,0.3)',
              '&:hover': { color: '#fff', background: 'rgba(255,255,255,0.08)' }
            }}
          >
            <Close />
          </IconButton>
        )}
      </DialogTitle>

      {/* Mode Navigation Tabs */}
      <Box sx={{ px: 3, pt: 1, pb: 0 }}>
        <Box sx={{ 
          display: 'flex', 
          p: 0.5, 
          borderRadius: '14px', 
          background: 'rgba(0,0,0,0.25)', 
          border: '1px solid var(--border)' 
        }}>
          <Button
            size="small"
            fullWidth
            onClick={() => !isCrawling && setActiveTab('missing')}
            disabled={isCrawling}
            sx={{
              py: 1,
              borderRadius: '10px',
              fontSize: '0.8rem',
              fontWeight: 800,
              textTransform: 'none',
              color: activeTab === 'missing' ? '#fff' : 'var(--muted-foreground)',
              background: activeTab === 'missing' ? '#3b82f6' : 'transparent',
              boxShadow: activeTab === 'missing' ? '0 4px 12px rgba(59, 130, 246, 0.3)' : 'none',
              '&:hover': {
                background: activeTab === 'missing' ? '#2563eb' : 'rgba(255,255,255,0.05)'
              }
            }}
          >
            📥 Fill Missing Content ({missingChapters.length})
          </Button>

          <Button
            size="small"
            fullWidth
            onClick={() => !isCrawling && setActiveTab('crawl')}
            disabled={isCrawling}
            sx={{
              py: 1,
              borderRadius: '10px',
              fontSize: '0.8rem',
              fontWeight: 800,
              textTransform: 'none',
              color: activeTab === 'crawl' ? '#fff' : 'var(--muted-foreground)',
              background: activeTab === 'crawl' ? 'linear-gradient(135deg, #0284c7, #3b82f6)' : 'transparent',
              boxShadow: activeTab === 'crawl' ? '0 4px 12px rgba(2, 132, 199, 0.3)' : 'none',
              '&:hover': {
                background: activeTab === 'crawl' ? '#0369a1' : 'rgba(255,255,255,0.05)'
              }
            }}
          >
            🌐 Crawl Next Web Chapters
          </Button>
        </Box>
      </Box>

      <DialogContent sx={{ px: 3, pt: 2, pb: 1 }}>
        {activeTab === 'missing' ? (
          /* TAB 1: Fill Missing Content */
          <>
            {/* Info Box */}
            <Box sx={{ p: 2, mb: 2.5, borderRadius: '16px', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.2)', display: 'flex', gap: 1.5 }}>
              <InfoOutlined sx={{ color: '#3b82f6', mt: 0.2, fontSize: 20 }} />
              <Typography variant="caption" sx={{ color: 'var(--muted-foreground)', fontWeight: 500, lineHeight: 1.5 }}>
                Mengunduh teks mentah untuk bab yang sudah terdaftar di database tetapi masih kosong (0 kata). <strong>Melewati AI translation</strong> untuk menghemat kuota.
              </Typography>
            </Box>

            <Box sx={{ px: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                <Typography variant="overline" sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: '#3b82f6', fontWeight: 900 }}>
                  <PlayArrow sx={{ fontSize: 14 }} /> Jumlah Bab yang Di-fetch
                </Typography>
                <Typography variant="body2" sx={{ fontWeight: 800, color: '#3b82f6' }}>
                  {range} Bab
                </Typography>
              </Box>
              
              <Slider
                value={range}
                onChange={handleRangeChange}
                min={1}
                max={Math.max(missingChapters.length, 10)}
                step={1}
                marks={[
                  { value: 1, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>1</span> },
                  { value: 10, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>10</span> },
                  { value: 25, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>25</span> },
                  { value: Math.max(missingChapters.length, 50), label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>Max</span> }
                ]}
                sx={{ 
                  color: '#3b82f6', 
                  mt: 0.5,
                  mb: 2.5,
                  height: 6,
                  '& .MuiSlider-track': { border: 'none' },
                  '& .MuiSlider-thumb': {
                    width: 18,
                    height: 18,
                    backgroundColor: '#fff',
                    boxShadow: '0 0 12px #3b82f6',
                  }
                }}
              />
            </Box>

            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, fontWeight: 'bold', fontSize: '0.85rem' }}>
                  <ListAlt fontSize="small" sx={{ color: '#3b82f6' }} /> Bab Kosong ({missingChapters.length})
                </Typography>
                <Typography variant="caption" sx={{ color: '#3b82f6', fontWeight: 800 }}>
                  {selectedIds.length} Terpilih
                </Typography>
              </Box>

              {/* Quick action buttons */}
              <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                <Button 
                  size="small" 
                  variant="outlined" 
                  onClick={selectAllMissing}
                  sx={{ 
                    fontSize: '0.65rem', borderRadius: '8px', borderColor: '#3b82f6', color: '#3b82f6', fontWeight: 800
                  }}
                >
                  Pilih Semua ({missingChapters.length})
                </Button>
                <Button 
                  size="small" 
                  variant="outlined" 
                  onClick={deselectAll}
                  sx={{ 
                    fontSize: '0.65rem', borderRadius: '8px', borderColor: 'var(--border)', color: 'var(--foreground)', fontWeight: 700
                  }}
                >
                  Bersihkan
                </Button>
              </Box>

              {/* Manual Checkbox List */}
              <Box sx={{ 
                maxHeight: 160, 
                overflow: 'auto', 
                background: 'rgba(0,0,0,0.25)', 
                border: '1px solid var(--border)', 
                borderRadius: '14px', 
                p: 0.5 
              }}>
                <List dense sx={{ py: 0 }}>
                  {chapters.map(ch => {
                    const isFetched = ch.word_count && ch.word_count > 0;
                    return (
                      <ListItem 
                        key={ch.id} 
                        onClick={() => !isFetched && toggleChapter(ch.id)}
                        sx={{ 
                          borderRadius: '8px', 
                          py: 0.2,
                          cursor: isFetched ? 'not-allowed' : 'pointer',
                          opacity: isFetched ? 0.35 : 1,
                          background: selectedIds.includes(ch.id) ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                          '&:hover': { background: isFetched ? 'transparent' : 'rgba(255,255,255,0.05)' }
                        }}
                      >
                        <Checkbox 
                          checked={selectedIds.includes(ch.id)} 
                          disabled={!!isFetched}
                          size="small"
                          sx={{ p: 0.5, color: 'var(--muted-foreground)', '&.Mui-checked': { color: '#3b82f6' } }}
                        />
                        <ListItemText>
                          <span style={{ fontSize: '0.75rem', fontWeight: 600 }}>
                            {`Ch ${ch.order}: ${ch.title_original || 'Untitled'}`}
                          </span>
                          {isFetched && (
                            <span style={{ marginLeft: 6, fontSize: '0.6rem', fontWeight: 900, background: 'rgba(255,255,255,0.1)', padding: '1px 5px', borderRadius: '4px' }}>
                              TERISI
                            </span>
                          )}
                        </ListItemText>
                      </ListItem>
                    );
                  })}
                </List>
              </Box>
            </Box>
          </>
        ) : (
          /* TAB 2: Crawl Next Web Chapters */
          <>
            {/* Info Box */}
            <Box sx={{ p: 2, mb: 2, borderRadius: '16px', background: 'rgba(2, 132, 199, 0.1)', border: '1px solid rgba(2, 132, 199, 0.25)', display: 'flex', gap: 1.5 }}>
              <Language sx={{ color: '#0284c7', mt: 0.2, fontSize: 20 }} />
              <Typography variant="caption" sx={{ color: 'var(--muted-foreground)', fontWeight: 500, lineHeight: 1.5 }}>
                Sistem akan secara otomatis menelusuri link <strong>"下一章 / Next Chapter"</strong> secara berantai dari bab web sumber, mengekstrak teks mentah, dan menyimpannya langsung ke database dengan delay anti-bot yang aman.
              </Typography>
            </Box>

            {/* Anchor Chapter / Custom URL Selector */}
            {anchorChapter && !showCustomUrlInput ? (
              <Box sx={{ 
                p: 2, 
                mb: 2, 
                borderRadius: '14px', 
                background: 'rgba(0,0,0,0.3)', 
                border: '1px solid var(--border)',
                display: 'flex',
                flexDirection: 'column',
                gap: 0.8
              }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="caption" sx={{ color: '#38bdf8', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    Titik Awal Crawl (Terdeteksi dari Bab Terakhir):
                  </Typography>
                  <Button 
                    size="small" 
                    onClick={() => setShowCustomUrlInput(true)}
                    sx={{ fontSize: '0.65rem', textTransform: 'none', color: 'var(--muted-foreground)', p: 0 }}
                  >
                    Ganti URL Manual
                  </Button>
                </Box>
                <Typography variant="body2" sx={{ fontWeight: 700, color: 'var(--foreground)' }}>
                  Ch {anchorChapter.order}: {anchorChapter.title_original || 'Untitled'}
                </Typography>
                {anchorChapter.source_url && (
                  <Typography variant="caption" sx={{ color: 'var(--muted-foreground)', wordBreak: 'break-all', fontSize: '0.65rem' }}>
                    🔗 {anchorChapter.source_url}
                  </Typography>
                )}
              </Box>
            ) : (
              <Box sx={{ 
                p: 2, 
                mb: 2, 
                borderRadius: '14px', 
                background: 'rgba(2, 132, 199, 0.08)', 
                border: '1px solid rgba(2, 132, 199, 0.3)', 
                display: 'flex', 
                flexDirection: 'column', 
                gap: 1.5 
              }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography variant="caption" sx={{ color: '#38bdf8', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <LinkIcon sx={{ fontSize: 16 }} /> Masukkan URL Web Bab Awal:
                  </Typography>
                  {anchorChapter && (
                    <Button 
                      size="small" 
                      onClick={() => setShowCustomUrlInput(false)}
                      sx={{ fontSize: '0.65rem', textTransform: 'none', color: '#38bdf8', p: 0 }}
                    >
                      Gunakan Bab Terakhir
                    </Button>
                  )}
                </Box>
                <TextField
                  fullWidth
                  size="small"
                  placeholder="https://example.com/novel/chapter-1.html"
                  value={customUrl}
                  onChange={(e) => setCustomUrl(e.target.value)}
                  sx={{
                    '& .MuiInputBase-root': {
                      borderRadius: '10px',
                      background: 'rgba(0,0,0,0.3)',
                      color: 'var(--foreground)',
                      fontSize: '0.8rem',
                    },
                    '& .MuiOutlinedInput-notchedOutline': {
                      borderColor: 'var(--border)',
                    }
                  }}
                />
                <Typography variant="caption" sx={{ color: 'var(--muted-foreground)', fontSize: '0.65rem' }}>
                  Crawler akan membuka URL ini dan menelusuri bab-bab selanjutnya secara otomatis.
                </Typography>
              </Box>
            )}

            {/* Slider */}
            {!isCrawling && !crawlMessage && (
              <Box sx={{ px: 1, mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                  <Typography variant="overline" sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: '#38bdf8', fontWeight: 900 }}>
                    <PlayArrow sx={{ fontSize: 14 }} /> Jumlah Bab Baru yang Ingin Di-Crawl
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 800, color: '#38bdf8' }}>
                    {crawlRange} Bab
                  </Typography>
                </Box>
                
                <Slider
                  value={crawlRange}
                  onChange={(_, val) => setCrawlRange(val as number)}
                  min={1}
                  max={50}
                  step={1}
                  marks={[
                    { value: 1, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>1</span> },
                    { value: 10, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>10</span> },
                    { value: 25, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>25</span> },
                    { value: 50, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>50</span> }
                  ]}
                  sx={{ 
                    color: '#0284c7', 
                    mt: 0.5,
                    height: 6,
                    '& .MuiSlider-track': { border: 'none' },
                    '& .MuiSlider-thumb': {
                      width: 18,
                      height: 18,
                      backgroundColor: '#fff',
                      boxShadow: '0 0 12px #0284c7',
                    }
                  }}
                />
              </Box>
            )}

            {/* Live Progress Bar & Logs */}
            {isCrawling && crawlProgress && (
              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                  <Typography variant="caption" sx={{ fontWeight: 800, color: '#38bdf8', display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Sync className="animate-spin" sx={{ fontSize: 16 }} /> Crawling ({crawlProgress.current}/{crawlProgress.total})
                  </Typography>
                  <Typography variant="caption" sx={{ fontWeight: 800, color: 'var(--foreground)' }}>
                    {Math.round((crawlProgress.current / crawlProgress.total) * 100)}%
                  </Typography>
                </Box>

                <LinearProgress 
                  variant="determinate" 
                  value={(crawlProgress.current / crawlProgress.total) * 100}
                  sx={{
                    height: 8,
                    borderRadius: 4,
                    backgroundColor: 'rgba(255,255,255,0.08)',
                    '& .MuiLinearProgress-bar': {
                      background: 'linear-gradient(90deg, #0284c7, #3b82f6)'
                    }
                  }}
                />

                {crawlProgress.latestTitle && (
                  <Typography variant="caption" sx={{ display: 'block', mt: 1, color: 'var(--muted-foreground)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    Sedang memproses: {crawlProgress.latestTitle}
                  </Typography>
                )}
              </Box>
            )}

            {/* Crawl Logs Box */}
            {crawlLogs.length > 0 && (
              <Box sx={{ 
                maxHeight: 130, 
                overflow: 'auto', 
                background: 'rgba(0,0,0,0.35)', 
                border: '1px solid var(--border)', 
                borderRadius: '12px', 
                p: 1.5,
                mb: 1.5,
                fontSize: '0.75rem',
                fontFamily: 'monospace',
                display: 'flex',
                flexDirection: 'column',
                gap: 0.5
              }}>
                {crawlLogs.map((log, i) => (
                  <span key={i} style={{ color: 'var(--foreground)' }}>{log}</span>
                ))}
              </Box>
            )}

            {/* Error Banner */}
            {crawlError && (
              <Box sx={{ p: 2, mb: 1.5, borderRadius: '12px', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.4)', display: 'flex', gap: 1 }}>
                <ErrorIcon sx={{ color: '#ef4444', fontSize: 18, mt: 0.2 }} />
                <Typography variant="caption" sx={{ color: '#ef4444', fontWeight: 700 }}>
                  {crawlError}
                </Typography>
              </Box>
            )}

            {/* Success Banner */}
            {crawlMessage && (
              <Box sx={{ p: 2, mb: 1.5, borderRadius: '12px', background: 'rgba(34, 197, 94, 0.15)', border: '1px solid rgba(34, 197, 94, 0.4)', display: 'flex', gap: 1 }}>
                <CheckCircle sx={{ color: '#22c55e', fontSize: 18, mt: 0.2 }} />
                <Typography variant="caption" sx={{ color: '#22c55e', fontWeight: 700 }}>
                  {crawlMessage}
                </Typography>
              </Box>
            )}
          </>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 3, pt: 1, borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        {activeTab === 'missing' ? (
          <Button 
            variant="contained" 
            fullWidth
            onClick={handleStartMissingFetch}
            disabled={isStarting || selectedIds.length === 0}
            sx={{ 
              py: 1.8, 
              borderRadius: '14px',
              fontSize: '0.95rem',
              fontWeight: 900,
              textTransform: 'none',
              background: '#3b82f6',
              color: '#fff',
              boxShadow: '0 8px 20px rgba(59, 130, 246, 0.3)',
              '&:hover': { background: '#2563eb' }
            }}
          >
            {isStarting ? (
              <CircularProgress size={22} sx={{ color: '#fff' }} />
            ) : (
              `Start Fetching ${selectedIds.length} Chapters`
            )}
          </Button>
        ) : (
          /* Crawl Tab Action Button */
          crawlMessage ? (
            <Button 
              variant="contained" 
              fullWidth
              onClick={onClose}
              sx={{ 
                py: 1.8, 
                borderRadius: '14px',
                fontSize: '0.95rem',
                fontWeight: 900,
                textTransform: 'none',
                background: '#22c55e',
                color: '#fff',
                boxShadow: '0 8px 20px rgba(34, 197, 94, 0.3)',
                '&:hover': { background: '#16a34a' }
              }}
            >
              Done & Refresh Chapters
            </Button>
          ) : (
            <Button 
              variant="contained" 
              fullWidth
              onClick={handleStartCrawl}
              disabled={!canStartCrawl || isCrawling}
              sx={{ 
                py: 1.8, 
                borderRadius: '14px',
                fontSize: '0.95rem',
                fontWeight: 900,
                textTransform: 'none',
                background: 'linear-gradient(135deg, #0284c7, #3b82f6)',
                color: '#fff',
                boxShadow: '0 8px 20px rgba(2, 132, 199, 0.4)',
                '&:hover': { background: '#0369a1' }
              }}
            >
              {isCrawling ? (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CircularProgress size={20} sx={{ color: '#fff' }} />
                  <span>Crawling {crawlRange} Chapters from Web...</span>
                </Box>
              ) : (
                `Start Crawling Next ${crawlRange} Web Chapters`
              )}
            </Button>
          )
        )}
      </DialogActions>
    </Dialog>
  );
}
