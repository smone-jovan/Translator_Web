/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, useEffect } from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import LinearProgress from '@mui/material/LinearProgress';
import IconButton from '@mui/material/IconButton';
import Collapse from '@mui/material/Collapse';
import Badge from '@mui/material/Badge';
import Button from '@mui/material/Button';

import AutoAwesome from '@mui/icons-material/AutoAwesome';
import KeyboardArrowDown from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUp from '@mui/icons-material/KeyboardArrowUp';
import CheckCircle from '@mui/icons-material/CheckCircle';
import Sync from '@mui/icons-material/Sync';
import StopCircle from '@mui/icons-material/StopCircle';
import Error from '@mui/icons-material/Error';
import { getApiUrl } from '@/lib/api';

interface BatchStatus {
  active: boolean;
  thread_id: number | null;
  thread_title: string;
  total: number;
  completed: number;
  current_chapter_id: number | null;
  current_chapter_title: string;
  failed_ids: number[];
}

export default function BulkStatusCenter() {
  const [isOpen, setIsOpen] = useState(true);
  const [status, setStatus] = useState<BatchStatus>({
    active: false,
    thread_id: null,
    thread_title: '',
    total: 0,
    completed: 0,
    current_chapter_id: null,
    current_chapter_title: '',
    failed_ids: []
  });
  const [showFinished, setShowFinished] = useState(false);

  // Poll active batch status from backend
  useEffect(() => {
    let intervalId: any = null;

    const checkStatus = async () => {
      try {
        const res = await fetch(getApiUrl('/api/threads/active-batch'));
        if (res.ok) {
          const data = await res.json();
          if (data.active) {
            setStatus(data);
            setShowFinished(false);
          } else {
            // If it was active but now not, check if we just completed it
            setStatus(prev => {
              if (prev.active && prev.total > 0) {
                // Mark as fully completed for presentation
                setShowFinished(true);
                // Dispatch event so LibraryPage/ReaderPage can silently refresh
                window.dispatchEvent(new CustomEvent('batch-completed', {
                  detail: { thread_id: prev.thread_id }
                }));
                return {
                  ...prev,
                  active: false,
                  completed: prev.total,
                  current_chapter_title: 'All tasks completed successfully!'
                };
              }
              return {
                active: false,
                thread_id: null,
                thread_title: '',
                total: 0,
                completed: 0,
                current_chapter_id: null,
                current_chapter_title: '',
                failed_ids: []
              };
            });
          }
        }
      } catch (err) {
        console.error('Error checking active batch:', err);
      }
    };

    // Initial check
    checkStatus();

    // Poll every 2 seconds
    intervalId = setInterval(checkStatus, 2000);

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, []);

  // Auto-hide completed status after 10 seconds
  useEffect(() => {
    if (showFinished) {
      const timer = setTimeout(() => {
        setShowFinished(false);
        setStatus(prev => ({
          ...prev,
          total: 0,
          completed: 0
        }));
      }, 10000);
      return () => clearTimeout(timer);
    }
  }, [showFinished]);

  const handleStop = async () => {
    if (!status.thread_id) return;
    if (!confirm('Are you sure you want to stop the batch translation? The current chapter will finish translating, and subsequent chapters will be cancelled.')) return;
    
    try {
      const res = await fetch(getApiUrl(`/api/threads/${status.thread_id}/batch-stop`), {
        method: 'POST'
      });
      if (res.ok) {
        setStatus({
          active: false,
          thread_id: null,
          thread_title: '',
          total: 0,
          completed: 0,
          current_chapter_id: null,
          current_chapter_title: '',
          failed_ids: []
        });
        setShowFinished(false);
      }
    } catch (err) {
      console.error('Failed to stop batch translation:', err);
    }
  };

  const isBatchActive = status.active || showFinished;
  if (!isBatchActive || status.total === 0) return null;

  const progress = status.total > 0 ? (status.completed / status.total) * 100 : 0;
  const isFinished = status.completed === status.total || showFinished;

  return (
    <Box sx={{ 
      position: 'fixed', 
      bottom: { xs: 88, md: 24 }, 
      right: { xs: 12, md: 24 },
      left: { xs: 12, md: 'auto' },
      zIndex: 2000,
      width: { xs: 'auto', md: 360 },
      pointerEvents: 'auto'
    }}>
      <Paper sx={{ 
        background: 'var(--card)',
        backdropFilter: 'blur(24px)',
        border: isFinished ? '1.5px solid rgba(76, 175, 80, 0.4)' : '1.5px solid var(--primary)',
        borderRadius: '24px',
        overflow: 'hidden',
        boxShadow: '0 12px 40px rgba(0,0,0,0.3)',
        color: 'var(--foreground)',
        transition: 'all 0.3s ease'
      }}>
        {/* Header Area */}
        <Box sx={{ 
          p: 2, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          background: isFinished ? 'rgba(76, 175, 80, 0.08)' : 'rgba(0,0,0,0.15)',
          cursor: 'pointer',
          borderBottom: '1px solid var(--border)'
        }} onClick={() => setIsOpen(!isOpen)}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, minWidth: 0 }}>
            <Badge 
              overlap="circular"
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              badgeContent={
                isFinished ? 
                <CheckCircle sx={{ fontSize: 15, color: '#4caf50' }} /> : 
                <Sync sx={{ fontSize: 15, color: 'var(--primary)', animation: 'spin 2s linear infinite' }} />
              }
            >
              <AutoAwesome sx={{ color: isFinished ? '#4caf50' : 'var(--primary)', fontSize: 20 }} />
            </Badge>
            <Box sx={{ minWidth: 0 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 800, color: 'var(--foreground)', fontSize: '0.85rem', lineHeight: 1.2 }}>
                {isFinished ? 'Translation Done' : 'Batch Translating'}
              </Typography>
              <Typography variant="caption" sx={{ 
                color: 'var(--muted-foreground)', 
                fontSize: '0.7rem', 
                display: 'block',
                maxWidth: { xs: 190, sm: 260, md: 230 },
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {status.thread_title}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexShrink: 0 }}>
            {status.active && (
              <IconButton 
                size="small" 
                onClick={(e) => { e.stopPropagation(); handleStop(); }}
                title="Stop Batch"
                sx={{ color: '#ef4444', '&:hover': { background: 'rgba(239, 68, 68, 0.1)' } }}
              >
                <StopCircle sx={{ fontSize: 18 }} />
              </IconButton>
            )}
            <IconButton size="small" sx={{ color: 'var(--foreground)', flexShrink: 0 }}>
              {isOpen ? <KeyboardArrowDown /> : <KeyboardArrowUp />}
            </IconButton>
          </Box>
        </Box>

        {/* Expandable Area */}
        <Collapse in={isOpen}>
          <Box sx={{ p: 2.5 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.2 }}>
              <Typography variant="caption" sx={{ opacity: 0.8, fontWeight: 600 }}>
                {isFinished ? 'All chapters translated' : `Progress: ${status.completed}/${status.total} chapters`}
              </Typography>
              <Typography variant="caption" sx={{ fontWeight: 900, color: isFinished ? '#4caf50' : 'var(--primary)' }}>
                {Math.round(progress)}%
              </Typography>
            </Box>
            
            <LinearProgress 
              variant="determinate" 
              value={progress} 
              sx={{ 
                height: 8, 
                borderRadius: 4,
                background: 'var(--secondary)',
                border: '1px solid var(--border)',
                '& .MuiLinearProgress-bar': {
                  background: isFinished ? '#4caf50' : 'linear-gradient(90deg, var(--primary), #8a2be2)',
                  borderRadius: 4
                }
              }} 
            />

            {/* Error badge for failed chapters */}
            {status.failed_ids.length > 0 && (
              <Box sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 1, 
                mt: 1.5, 
                px: 1.5, 
                py: 0.8, 
                borderRadius: '8px', 
                background: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.2)',
                color: '#ef4444'
              }}>
                <Error sx={{ fontSize: 16 }} />
                <Typography variant="caption" sx={{ fontWeight: 700 }}>
                  {status.failed_ids.length} chapter(s) failed to translate.
                </Typography>
              </Box>
            )}

            <Typography variant="caption" sx={{ 
              display: 'block', 
              mt: 2, 
              color: 'var(--muted-foreground)', 
              fontWeight: 500,
              fontSize: '0.75rem',
              whiteSpace: 'nowrap', 
              overflow: 'hidden', 
              textOverflow: 'ellipsis' 
            }}>
              {isFinished ? 'Feel free to read your translated book now!' : `Now: ${status.current_chapter_title}`}
            </Typography>

            {isFinished && (
              <Button 
                fullWidth 
                size="small" 
                variant="outlined" 
                onClick={() => {
                  setShowFinished(false);
                  setStatus(prev => ({ ...prev, total: 0, completed: 0 }));
                }}
                sx={{ 
                  mt: 2, 
                  borderColor: 'var(--border)', 
                  color: 'var(--foreground)', 
                  borderRadius: '10px',
                  fontWeight: 700,
                  fontSize: '0.7rem',
                  '&:hover': {
                    borderColor: 'var(--primary)',
                    background: 'rgba(255,255,255,0.05)'
                  }
                }}
              >
                Dismiss
              </Button>
            )}
          </Box>
        </Collapse>
      </Paper>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </Box>
  );
}
