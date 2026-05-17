import { useState, useEffect } from 'react';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Button from '@mui/material/Button';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import Slider from '@mui/material/Slider';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import Tooltip from '@mui/material/Tooltip';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';

import AutoAwesome from '@mui/icons-material/AutoAwesome';
import Settings from '@mui/icons-material/Settings';
import ListAlt from '@mui/icons-material/ListAlt';
import PlayArrow from '@mui/icons-material/PlayArrow';
import History from '@mui/icons-material/History';
import Close from '@mui/icons-material/Close';

interface Chapter {
  id: number;
  order: number;
  title_original: string | null;
  title_translated?: string | null;
  has_translation: boolean;
}

interface BulkTranslateModalProps {
  isOpen: boolean;
  onClose: () => void;
  threadId: number;
  threadTitle: string;
  chapters: Chapter[];
  onStartBatch: (chapterIds: number[], aiExtract: boolean, loadMode: 'soft' | 'hard') => void;
}

export default function BulkTranslateModal({ 
  isOpen, onClose, threadId, threadTitle, chapters, onStartBatch 
}: BulkTranslateModalProps) {
  const [mode, setMode] = useState<'easy' | 'advanced'>('easy');
  const [loadMode, setLoadMode] = useState<'soft' | 'hard'>('soft');
  const [range, setRange] = useState<number>(5);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [aiExtract, setAiExtract] = useState<boolean>(true);
  const [loreCount, setLoreCount] = useState<number>(0);
  const [isStarting, setIsStarting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      // Fetch lorebook count to determine recommendation
      fetch(`http://localhost:8000/api/threads/${threadId}/lorebook`)
        .then(res => res.json())
        .then(data => {
          const count = data.length || 0;
          setLoreCount(count);
          if (count > 40) setAiExtract(false);
          else setAiExtract(true);
        })
        .catch(() => setLoreCount(0));

      // Initial selection for Easy Mode based on loadMode
      updateSelection(range, loadMode);
    }
  }, [isOpen, threadId, chapters, loadMode]);

  const updateSelection = (val: number, lMode: 'soft' | 'hard') => {
    let filtered = chapters;
    if (lMode === 'soft') {
      // Soft load is one-by-one focus
      filtered = chapters.filter(c => !c.has_translation);
      const result = filtered.slice(0, 1).map(c => c.id);
      setSelectedIds(result);
    } else {
      // Hard load is bulk processing
      const result = filtered.slice(0, val).map(c => c.id);
      setSelectedIds(result);
    }
  };

  const handleRangeChange = (_: any, newValue: number | number[]) => {
    const val = newValue as number;
    setRange(val);
    if (mode === 'easy') {
      updateSelection(val, loadMode);
    }
  };

  const toggleChapter = (id: number) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const handleStart = async () => {
    setIsStarting(true);
    try {
      await onStartBatch(selectedIds, aiExtract, loadMode);
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
          backgroundImage: 'radial-gradient(circle at top left, var(--primary), transparent)',
          border: '1px solid var(--border)',
          borderRadius: '28px',
          color: 'var(--foreground)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
        }
      }}
    >
      <DialogTitle sx={{ 
        m: 0, 
        p: 4, 
        pb: 1, 
        display: 'flex', 
        alignItems: 'center', 
        gap: 3 
      }}>
        <Box sx={{ 
          width: 56, 
          height: 56, 
          borderRadius: '18px', 
          background: 'var(--primary)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 8px 20px var(--primary)',
          flexShrink: 0
        }}>
          <AutoAwesome sx={{ color: 'var(--primary-foreground)', fontSize: 28 }} />
        </Box>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 900, color: 'var(--foreground)', letterSpacing: '-0.5px' }}>
            Batch Translation Studio
          </Typography>
          <Typography variant="body2" sx={{ color: 'var(--muted-foreground)', fontWeight: 500 }}>
            Advanced Chapter Processing for {threadTitle || 'this novel'}
          </Typography>
        </Box>
        <IconButton
          onClick={onClose}
          sx={{
            position: 'absolute',
            right: 24,
            top: 24,
            color: 'rgba(255,255,255,0.2)',
            '&:hover': { color: '#fff', background: 'rgba(255,255,255,0.05)' }
          }}
        >
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ px: 4, pt: 2 }}>

        <Box sx={{ mb: 4, display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'center' }}>
            <ToggleButtonGroup
              value={mode}
              exclusive
              onChange={(_, val) => val && setMode(val)}
              sx={{ 
                background: 'rgba(0,0,0,0.4)',
                p: 0.6,
                borderRadius: '18px',
                border: '1px solid rgba(255,255,255,0.05)',
                '& .MuiToggleButton-root': {
                  color: 'rgba(255,255,255,0.4)',
                  border: 'none',
                  px: 4,
                  py: 1,
                  borderRadius: '14px',
                  fontSize: '0.8rem',
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  transition: 'all 0.2s ease',
                  '&.Mui-selected': {
                    background: 'var(--primary)',
                    color: 'var(--primary-foreground)',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                    '&:hover': { background: 'var(--primary)' }
                  }
                }
              }}
            >
              <ToggleButton value="easy">Easy Mode</ToggleButton>
              <ToggleButton value="advanced">Custom</ToggleButton>
            </ToggleButtonGroup>
          </Box>
        </Box>

        {mode === 'easy' ? (
          <Box sx={{ px: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
                <ToggleButtonGroup
                value={loadMode}
                exclusive
                onChange={(_, val) => val && setLoadMode(val)}
                sx={{ 
                    background: 'rgba(0,0,0,0.2)',
                    p: 0.5,
                    borderRadius: '14px',
                    '& .MuiToggleButton-root': {
                    color: 'rgba(255,255,255,0.3)',
                    border: 'none',
                    px: 2.5,
                    py: 0.6,
                    borderRadius: '10px',
                    fontSize: '0.7rem',
                    fontWeight: 900,
                    '&.Mui-selected': {
                        background: 'var(--primary)',
                        color: 'var(--primary-foreground)',
                        border: '1px solid var(--border)',
                        '&:hover': { background: 'var(--primary)' }
                    }
                    }
                }}
                >
                <ToggleButton value="soft">SOFT LOAD</ToggleButton>
                <ToggleButton value="hard">HARD LOAD</ToggleButton>
                </ToggleButtonGroup>
            </Box>
            <Typography variant="overline" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'var(--primary)', fontWeight: 900, mb: 1 }}>
              <PlayArrow sx={{ fontSize: 16 }} /> {loadMode === 'soft' ? 'Safety Sequence' : 'Batch Depth'}
            </Typography>
            <Slider
              value={loadMode === 'soft' ? 1 : range}
              onChange={handleRangeChange}
              min={1}
              max={20}
              disabled={loadMode === 'soft'}
              step={1}
              marks={[
                { value: 1, label: <span style={{ color: '#666', fontSize: '10px' }}>1</span> },
                { value: 5, label: <span style={{ color: '#666', fontSize: '10px' }}>5</span> },
                { value: 10, label: <span style={{ color: '#666', fontSize: '10px' }}>10</span> },
                { value: 20, label: <span style={{ color: '#666', fontSize: '10px' }}>20+</span> }
              ]}
              sx={{ 
                color: 'var(--primary)', 
                mt: 2,
                height: 6,
                '& .MuiSlider-track': { border: 'none' },
                '& .MuiSlider-thumb': {
                  width: 20,
                  height: 20,
                  backgroundColor: 'var(--primary-foreground)',
                  boxShadow: '0 0 15px var(--primary)',
                  '&:hover, &.Mui-focusVisible': {
                    boxShadow: '0 0 0 8px var(--primary)'
                  }
                }
              }}
            />
            <Typography variant="body2" sx={{ display: 'block', mt: 4, opacity: 0.5, fontStyle: 'italic', color: 'var(--foreground)' }}>
              {loadMode === 'soft' 
                ? 'Soft Load: Sequential processing ensures stability for local VRAM.' 
                : 'Hard Load: Massive parallel-ready batch processing for speed.'}
            </Typography>
          </Box>
        ) : (
          <Box>
             <Box sx={{ px: 2, mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
                    <ToggleButtonGroup
                    value={loadMode}
                    exclusive
                    onChange={(_, val) => val && setLoadMode(val)}
                    sx={{ 
                        background: 'rgba(0,0,0,0.2)',
                        p: 0.5,
                        borderRadius: '14px',
                        '& .MuiToggleButton-root': {
                        color: 'rgba(255,255,255,0.3)',
                        border: 'none',
                        px: 2.5,
                        py: 0.6,
                        borderRadius: '10px',
                        fontSize: '0.7rem',
                        fontWeight: 900,
                        '&.Mui-selected': {
                            background: 'var(--primary)',
                            color: 'var(--primary-foreground)',
                            border: '1px solid var(--border)',
                            '&:hover': { background: 'var(--primary)' }
                        }
                        }
                    }}
                    >
                    <ToggleButton value="soft">SOFT LOAD</ToggleButton>
                    <ToggleButton value="hard">HARD LOAD</ToggleButton>
                    </ToggleButtonGroup>
                </Box>
                <Typography variant="overline" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'var(--primary)', fontWeight: 900, mb: 1 }}>
                  <PlayArrow sx={{ fontSize: 16 }} /> Selection Range
                </Typography>
                <Slider
                  value={range}
                  onChange={handleRangeChange}
                  min={1}
                  max={20}
                  step={1}
                  marks={[
                    { value: 1, label: <span style={{ color: '#666', fontSize: '10px' }}>1</span> },
                    { value: 5, label: <span style={{ color: '#666', fontSize: '10px' }}>5</span> },
                    { value: 10, label: <span style={{ color: '#666', fontSize: '10px' }}>10</span> },
                    { value: 20, label: <span style={{ color: '#666', fontSize: '10px' }}>20+</span> }
                  ]}
                  sx={{ 
                    color: 'var(--primary)', 
                    mt: 2,
                    height: 6,
                    '& .MuiSlider-track': { border: 'none' },
                    '& .MuiSlider-thumb': {
                      width: 20,
                      height: 20,
                      backgroundColor: 'var(--primary-foreground)',
                      boxShadow: '0 0 15px var(--primary)',
                      '&:hover, &.Mui-focusVisible': {
                        boxShadow: '0 0 0 8px var(--primary)'
                      }
                    }
                  }}
                />
             </Box>
             <Typography variant="subtitle2" sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
              <ListAlt fontSize="small" /> Select Chapters Manualy
            </Typography>
            <Box sx={{ maxHeight: 250, overflow: 'auto', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', p: 1 }}>
              <List dense>
                {chapters.map(ch => (
                  // @ts-ignore
                  <ListItem 
                    key={ch.id} 
                    button 
                    onClick={() => toggleChapter(ch.id)}
                    sx={{ 
                      borderRadius: '8px', 
                      mb: 0.5,
                      background: selectedIds.includes(ch.id) ? 'var(--secondary)' : 'transparent'
                    }}
                  >
                    <Checkbox 
                      checked={selectedIds.includes(ch.id)} 
                      size="small"
                      sx={{ color: 'var(--muted-foreground)', '&.Mui-checked': { color: 'var(--primary)' } }}
                    />
                    <ListItemText>
                      <span style={{ fontSize: '0.85rem', opacity: ch.has_translation ? 0.5 : 1 }}>
                        {`Ch ${ch.order}: ${ch.title_translated || ch.title_original}`}
                      </span>
                    </ListItemText>
                    {ch.has_translation && (
                      <Tooltip title="Already translated. Will be overwritten.">
                        <History sx={{ fontSize: 16, opacity: 0.5 }} />
                      </Tooltip>
                    )}
                  </ListItem>
                ))}
              </List>
            </Box>
          </Box>
        )}

        <Divider sx={{ my: 3, borderColor: 'rgba(255,255,255,0.1)' }} />

        <Box sx={{ p: 2.5, background: 'rgba(0,0,0,0.3)', borderRadius: '20px', border: '1px solid rgba(255,255,255,0.05)' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
            <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'var(--foreground)', fontWeight: 'bold' }}>
              <Settings fontSize="small" sx={{ color: 'var(--primary)' }} /> AI Terminology Scan
            </Typography>
            {loreCount > 40 && (
              <Box sx={{ px: 1.5, py: 0.5, borderRadius: '8px', background: 'rgba(76, 175, 80, 0.1)', color: '#81c784', fontSize: '0.65rem', fontWeight: 900 }}>
                LORE READY
              </Box>
            )}
          </Box>
          
          <FormControlLabel
            control={
              <Checkbox 
                checked={aiExtract} 
                onChange={(e) => setAiExtract(e.target.checked)}
                sx={{ color: 'var(--muted-foreground)', '&.Mui-checked': { color: 'var(--primary)' } }}
              />
            }
            label={
              <Box>
                <Typography variant="body2" sx={{ color: 'var(--foreground)', fontWeight: 'bold' }}>AI Extract First</Typography>
                <Typography variant="caption" sx={{ opacity: 0.5, display: 'block', color: 'var(--muted-foreground)' }}>
                  Analyze names & lore before translating to ensure quality.
                </Typography>
              </Box>
            }
          />
        </Box>

        {selectedIds.length > 0 && (
        <Box sx={{ 
          mt: 4, 
          p: 2.5, 
          borderRadius: '20px', 
          background: 'rgba(255, 152, 0, 0.05)', 
          border: '1px solid rgba(255, 152, 0, 0.15)',
          display: 'flex',
          gap: 2,
          alignItems: 'flex-start'
        }}>
          <Box sx={{ p: 1, borderRadius: '12px', background: 'rgba(255, 152, 0, 0.1)', display: 'flex' }}>
            <AutoAwesome sx={{ color: '#ffb74d', fontSize: 20 }} />
          </Box>
          <Box>
            <Typography variant="subtitle2" sx={{ color: '#ffb74d', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Consistency Protocol Active
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', display: 'block', mt: 0.5, lineHeight: 1.4 }}>
              System will overwrite **{loadMode === 'soft' ? '1 chapter' : `${range} chapters`}** using latest lorebook rules. 
              This ensures names and terms remain consistent.
            </Typography>
          </Box>
        </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ p: 4, pt: 2 }}>
        <Button
          fullWidth
          variant="contained"
          onClick={handleStart}
          disabled={isStarting}
          startIcon={isStarting ? <CircularProgress size={20} color="inherit" /> : <PlayArrow />}
          sx={{
            py: 2,
            borderRadius: '16px',
            background: 'var(--primary)',
            color: 'var(--primary-foreground)',
            fontWeight: 900,
            fontSize: '1rem',
            letterSpacing: '1px',
            boxShadow: '0 10px 25px var(--primary)',
            transition: 'all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
            '&:hover': {
              transform: 'translateY(-2px)',
              boxShadow: '0 15px 35px var(--primary)',
              opacity: 0.9
            },
            '&:active': {
              transform: 'translateY(1px)',
            },
            '&.Mui-disabled': {
              background: 'rgba(255,255,255,0.05)',
              color: 'rgba(255,255,255,0.2)'
            }
          }}
        >
          {isStarting ? 'PREPARING ENGINE...' : `START ${loadMode === 'soft' ? '1 CHAPTER' : `${range} CHAPTERS`}`}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
