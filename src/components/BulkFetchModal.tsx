/* eslint-disable react-hooks/exhaustive-deps */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/ban-ts-comment */
/* eslint-disable react-hooks/set-state-in-effect */
import { useState, useEffect } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
// import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Slider from '@mui/material/Slider';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
// import Tooltip from '@mui/material/Tooltip';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';

import CloudDownload from '@mui/icons-material/CloudDownload';
import PlayArrow from '@mui/icons-material/PlayArrow';
import Close from '@mui/icons-material/Close';
import ListAlt from '@mui/icons-material/ListAlt';
import InfoOutlined from '@mui/icons-material/InfoOutlined';

interface Chapter {
  id: number;
  order: number;
  title_original: string | null;
  word_count?: number;
}

interface BulkFetchModalProps {
  isOpen: boolean;
  onClose: () => void;
  threadId: number;
  threadTitle: string;
  chapters: Chapter[];
  onStartBatch: (chapterIds: number[], fetchOnly: boolean) => void;
}

export default function BulkFetchModal({ 
  isOpen, onClose, threadTitle, chapters, onStartBatch
}: BulkFetchModalProps) {
  const [range, setRange] = useState<number>(5);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [isStarting, setIsStarting] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);

  // Chapters that are missing content (word_count is 0 or undefined)
  const missingChapters = chapters.filter(c => !c.word_count || c.word_count === 0);

  const updateSelection = (quantity: number) => {
    const result = missingChapters.slice(0, quantity).map(c => c.id);
    setSelectedIds(result);
  };

  useEffect(() => {
    if (isOpen) {
      if (!hasInitialized) {
        updateSelection(range);
        setHasInitialized(true);
      }
    } else {
      setHasInitialized(false);
    }
  }, [isOpen, chapters, hasInitialized]);

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

  const handleStart = async () => {
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

  return (
    <Dialog 
      open={isOpen} 
      onClose={onClose}
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
        m: 0, p: 4, pb: 1, display: 'flex', alignItems: 'center', gap: 3 
      }}>
        <Box sx={{ 
          width: 56, height: 56, borderRadius: '18px', 
          background: '#3b82f6',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 8px 20px rgba(59, 130, 246, 0.4)',
          flexShrink: 0
        }}>
          <CloudDownload sx={{ color: '#fff', fontSize: 28 }} />
        </Box>
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 900, color: 'var(--foreground)', letterSpacing: '-0.5px' }}>
            Bulk Fetch Raw
          </Typography>
          <Typography variant="body2" sx={{ color: 'var(--muted-foreground)', fontWeight: 500 }}>
            {threadTitle || 'Download chapter texts without translation'}
          </Typography>
        </Box>
        <IconButton
          onClick={onClose}
          sx={{
            color: 'rgba(255,255,255,0.2)',
            '&:hover': { color: '#fff', background: 'rgba(255,255,255,0.05)' }
          }}
        >
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ px: 4, pt: 2, pb: 0 }}>
        
        {/* Info Box */}
        <Box sx={{ p: 2, mb: 3, borderRadius: '16px', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.2)', display: 'flex', gap: 1.5 }}>
          <InfoOutlined sx={{ color: '#3b82f6', mt: 0.5 }} />
          <Typography variant="body2" sx={{ color: 'var(--muted-foreground)', fontWeight: 500, lineHeight: 1.5 }}>
            This will download the raw text sequentially to bypass bot protections. 
            It will <strong>skip</strong> AI Translation, saving you API limit and time. 
            Chapters with existing text are ignored.
          </Typography>
        </Box>

        <Box sx={{ px: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
            <Typography variant="overline" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: '#3b82f6', fontWeight: 900 }}>
              <PlayArrow sx={{ fontSize: 16 }} /> Quantity to Fetch
            </Typography>
            <Typography variant="body2" sx={{ fontWeight: 800, color: '#3b82f6' }}>
              {range} Chapters
            </Typography>
          </Box>
          
          <Slider
            value={range}
            onChange={handleRangeChange}
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
              color: '#3b82f6', 
              mt: 1,
              mb: 3,
              height: 6,
              '& .MuiSlider-track': { border: 'none' },
              '& .MuiSlider-thumb': {
                width: 20,
                height: 20,
                backgroundColor: '#fff',
                boxShadow: '0 0 15px #3b82f6',
                '&:hover, &.Mui-focusVisible': {
                  boxShadow: '0 0 0 8px rgba(59, 130, 246, 0.3)'
                }
              }
            }}
          />
        </Box>

        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
            <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, fontWeight: 'bold' }}>
              <ListAlt fontSize="small" sx={{ color: '#3b82f6' }} /> Missing Chapters ({missingChapters.length})
            </Typography>
            <Typography variant="caption" sx={{ color: '#3b82f6', fontWeight: 800 }}>
              {selectedIds.length} Selected
            </Typography>
          </Box>

          {/* Quick action buttons */}
          <Box sx={{ display: 'flex', gap: 1, mb: 1.5 }}>
            <Button 
              size="small" 
              variant="outlined" 
              onClick={selectAllMissing}
              sx={{ 
                fontSize: '0.65rem', borderRadius: '8px', borderColor: '#3b82f6', color: '#3b82f6', fontWeight: 800
              }}
            >
              Select All Missing
            </Button>
            <Button 
              size="small" 
              variant="outlined" 
              onClick={deselectAll}
              sx={{ 
                fontSize: '0.65rem', borderRadius: '8px', borderColor: 'var(--border)', color: 'var(--foreground)', fontWeight: 700
              }}
            >
              Clear All
            </Button>
          </Box>

          {/* Manual Checkbox List */}
          <Box sx={{ 
            maxHeight: 200, 
            overflow: 'auto', 
            background: 'rgba(0,0,0,0.25)', 
            border: '1px solid var(--border)',
            borderRadius: '16px', 
            p: 1 
          }}>
            <List dense sx={{ py: 0 }}>
              {chapters.map(ch => {
                const isFetched = ch.word_count && ch.word_count > 0;
                return (
                <ListItem 
                  key={ch.id} 
                  onClick={() => !isFetched && toggleChapter(ch.id)}
                  sx={{ 
                    borderRadius: '10px', 
                    mb: 0.5,
                    cursor: isFetched ? 'not-allowed' : 'pointer',
                    opacity: isFetched ? 0.4 : 1,
                    background: selectedIds.includes(ch.id) ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                    '&:hover': { background: isFetched ? 'transparent' : 'rgba(255,255,255,0.05)' }
                  }}
                >
                  <Checkbox 
                    checked={selectedIds.includes(ch.id)} 
                    disabled={!!isFetched}
                    size="small"
                    sx={{ color: 'var(--muted-foreground)', '&.Mui-checked': { color: '#3b82f6' } }}
                  />
                  <ListItemText>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>
                      {`Ch ${ch.order}: ${ch.title_original || 'Untitled'}`}
                    </span>
                    {isFetched && (
                      <span style={{ marginLeft: 8, fontSize: '0.6rem', fontWeight: 900, background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                        FETCHED
                      </span>
                    )}
                  </ListItemText>
                </ListItem>
                );
              })}
            </List>
          </Box>
        </Box>

      </DialogContent>

      <DialogActions sx={{ p: 4, pt: 2, borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Button 
          variant="contained" 
          fullWidth
          onClick={handleStart}
          disabled={isStarting || selectedIds.length === 0}
          sx={{ 
            py: 2, 
            borderRadius: '16px',
            fontSize: '1rem',
            fontWeight: 900,
            textTransform: 'none',
            background: '#3b82f6',
            color: '#fff',
            boxShadow: '0 8px 20px rgba(59, 130, 246, 0.3)',
            '&:hover': { background: '#2563eb' }
          }}
        >
          {isStarting ? (
            <CircularProgress size={24} sx={{ color: '#fff' }} />
          ) : (
            `Start Fetching ${selectedIds.length} Chapters`
          )}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
