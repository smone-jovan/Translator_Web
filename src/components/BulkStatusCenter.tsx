import React, { useState, useEffect } from 'react';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import LinearProgress from '@mui/material/LinearProgress';
import IconButton from '@mui/material/IconButton';
import Collapse from '@mui/material/Collapse';
import Badge from '@mui/material/Badge';
import CircularProgress from '@mui/material/CircularProgress';
import Button from '@mui/material/Button';

import AutoAwesome from '@mui/icons-material/AutoAwesome';
import KeyboardArrowDown from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUp from '@mui/icons-material/KeyboardArrowUp';
import Close from '@mui/icons-material/Close';
import CheckCircle from '@mui/icons-material/CheckCircle';
import Sync from '@mui/icons-material/Sync';

interface BatchStatus {
  active: boolean;
  total: number;
  completed: number;
  currentTitle: string;
}

export default function BulkStatusCenter() {
  const [isOpen, setIsOpen] = useState(true);
  const [status, setStatus] = useState<BatchStatus>({
    active: false,
    total: 0,
    completed: 0,
    currentTitle: ''
  });

  // Polling for global status
  // In a real app, use WebSockets. Here we poll the background_translator status via a new endpoint if needed.
  // For now, we'll simulate listening to events or polling a generic status endpoint.
  useEffect(() => {
    const interval = setInterval(() => {
      // Logic to check how many chapters are in "processing" state
      // This is a simplified mockup. Ideally backend should have a /api/batch/status
      fetch('http://localhost:8000/api/threads') // We use thread progress or we could add a specific batch status API
        .then(res => res.json())
        .then(threads => {
          // Check if any thread has "processing" chapters
          // This is a bit expensive, but works for MVP
        });
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // For demonstration, let's assume we use a window event to trigger status
  useEffect(() => {
    const handleBatchStart = (e: any) => {
      setStatus({
        active: true,
        total: e.detail.total,
        completed: 0,
        currentTitle: 'Initializing...'
      });
      setIsOpen(true);
    };

    const handleBatchUpdate = (e: any) => {
      setStatus(prev => ({
        ...prev,
        completed: e.detail.completed,
        currentTitle: e.detail.currentTitle
      }));
    };

    const handleBatchEnd = () => {
        setTimeout(() => {
            setStatus(prev => ({ ...prev, active: false }));
        }, 3000);
    };

    window.addEventListener('batch-start', handleBatchStart);
    window.addEventListener('batch-update', handleBatchUpdate);
    window.addEventListener('batch-end', handleBatchEnd);
    return () => {
      window.removeEventListener('batch-start', handleBatchStart);
      window.removeEventListener('batch-update', handleBatchUpdate);
      window.removeEventListener('batch-end', handleBatchEnd);
    };
  }, []);

  if (!status.active && status.completed === 0) return null;

  const progress = status.total > 0 ? (status.completed / status.total) * 100 : 0;

  return (
    <Box sx={{ 
      position: 'fixed', 
      bottom: 24, 
      right: 24, 
      zIndex: 2000,
      width: 320,
      pointerEvents: 'auto'
    }}>
      <Paper sx={{ 
        background: 'var(--card)',
        backdropFilter: 'blur(20px)',
        border: '1px solid var(--primary)',
        borderRadius: '20px',
        overflow: 'hidden',
        boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
        color: 'var(--foreground)'
      }}>
        <Box sx={{ 
          p: 2, 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          background: 'var(--secondary)',
          cursor: 'pointer',
          color: 'var(--foreground)'
        }} onClick={() => setIsOpen(!isOpen)}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Badge 
              overlap="circular"
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              badgeContent={
                status.completed === status.total ? 
                <CheckCircle sx={{ fontSize: 14, color: 'var(--primary)' }} /> : 
                <Sync sx={{ fontSize: 14, color: 'var(--primary)', animation: 'spin 2s linear infinite' }} />
              }
            >
              <AutoAwesome sx={{ color: 'var(--primary)' }} />
            </Badge>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: 'var(--foreground)' }}>
              Batch Progress
            </Typography>
          </Box>
          <Box>
            <IconButton size="small" sx={{ color: 'var(--foreground)' }}>
              {isOpen ? <KeyboardArrowDown /> : <KeyboardArrowUp />}
            </IconButton>
          </Box>
        </Box>

        <Collapse in={isOpen}>
          <Box sx={{ p: 2, pt: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="caption" sx={{ opacity: 0.7 }}>
                {status.completed === status.total ? 'Batch Complete' : `Processing: ${status.completed}/${status.total}`}
              </Typography>
              <Typography variant="caption" sx={{ fontWeight: 'bold', color: '#00f2fe' }}>
                {Math.round(progress)}%
              </Typography>
            </Box>
            
            <LinearProgress 
              variant="determinate" 
              value={progress} 
              sx={{ 
                height: 6, 
                borderRadius: 3,
                background: 'var(--secondary)',
                '& .MuiLinearProgress-bar': {
                  background: 'var(--primary)',
                }
              }} 
            />

            <Typography variant="caption" sx={{ 
              display: 'block', 
              mt: 1.5, 
              opacity: 0.5, 
              whiteSpace: 'nowrap', 
              overflow: 'hidden', 
              textOverflow: 'ellipsis' 
            }}>
              Current: {status.currentTitle}
            </Typography>

            {status.completed === status.total && (
                <Button 
                    fullWidth 
                    size="small" 
                    variant="outlined" 
                    onClick={() => setStatus({ active: false, total: 0, completed: 0, currentTitle: '' })}
                    sx={{ mt: 2, borderColor: 'var(--primary)', color: 'var(--primary)', borderRadius: '8px' }}
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
