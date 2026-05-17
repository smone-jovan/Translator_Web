/* eslint-disable react-hooks/set-state-in-effect */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/ban-ts-comment */
/* eslint-disable react-hooks/exhaustive-deps */
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
import Tooltip from '@mui/material/Tooltip';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';

import AutoAwesome from '@mui/icons-material/AutoAwesome';
import Settings from '@mui/icons-material/Settings';
import ListAlt from '@mui/icons-material/ListAlt';
import PlayArrow from '@mui/icons-material/PlayArrow';
import History from '@mui/icons-material/History';
import Close from '@mui/icons-material/Close';
import Bolt from '@mui/icons-material/Bolt';
import Shield from '@mui/icons-material/Shield';
import Translate from '@mui/icons-material/Translate';

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
  onStartBatch: (chapterIds: number[], aiExtract: boolean, loadMode: 'soft' | 'hard', targetLang: string, overwrite: boolean) => void;
}

export default function BulkTranslateModal({ 
  isOpen, onClose, threadId, threadTitle, chapters, onStartBatch 
}: BulkTranslateModalProps) {
  const [mode, setMode] = useState<'easy' | 'advanced'>('easy');
  const [loadMode, setLoadMode] = useState<'soft' | 'hard'>('soft');
  const [range, setRange] = useState<number>(5);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [aiExtract, setAiExtract] = useState<boolean>(true);
  const [overwrite, setOverwrite] = useState<boolean>(false);
  const [loreCount, setLoreCount] = useState<number>(0);
  const [isStarting, setIsStarting] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);
  const [targetLang, setTargetLang] = useState<'Indonesian' | 'English'>(
    () => (localStorage.getItem('target_language') as 'Indonesian' | 'English') || 'Indonesian'
  );

  // Update selected IDs in Easy Mode
  const updateEasySelection = (quantity: number) => {
    // Find chapters that are not translated yet
    const untranslated = chapters.filter(c => !c.has_translation);
    const baseList = untranslated.length > 0 ? untranslated : chapters;
    
    const result = baseList.slice(0, quantity).map(c => c.id);
    setSelectedIds(result);
  };

  useEffect(() => {
    if (isOpen) {
      if (!hasInitialized) {
        // Fetch lorebook count to determine recommendation
        fetch(`http://localhost:8000/api/threads/${threadId}/lorebook`)
          .then(res => res.json())
          .then(data => {
            const count = data.length || 0;
            setLoreCount(count);
            // If already has some entries, don't force extraction
            if (count > 20) setAiExtract(false);
            else setAiExtract(true);
          })
          .catch(() => setLoreCount(0));

        // Initial selection for Easy Mode
        updateEasySelection(range);
        setHasInitialized(true);
      }
    } else {
      setHasInitialized(false);
    }
  }, [isOpen, threadId, chapters, hasInitialized]);

  const handleRangeChange = (_: any, newValue: number | number[]) => {
    const val = newValue as number;
    setRange(val);
    if (mode === 'easy') {
      updateEasySelection(val);
    }
  };

  const toggleChapter = (id: number) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const selectAllUntranslated = () => {
    const untranslated = chapters.filter(c => !c.has_translation).map(c => c.id);
    setSelectedIds(untranslated);
  };

  const selectAll = () => {
    const all = chapters.map(c => c.id);
    setSelectedIds(all);
  };

  const deselectAll = () => {
    setSelectedIds([]);
  };

  const handleStart = async () => {
    if (selectedIds.length === 0) {
      alert('Please select at least 1 chapter to translate!');
      return;
    }
    setIsStarting(true);
    try {
      await onStartBatch(selectedIds, aiExtract, loadMode, targetLang, overwrite);
      onClose();
    } finally {
      setIsStarting(false);
    }
  };

  // 15 Chapters AI Extract = ~3,750 tokens (~250 tokens per chapter)
  // 1 Chapter Translation (2k words input + output segments) = ~6,500 tokens
  const getEstimatedTokens = () => {
    const count = selectedIds.length;
    if (count === 0) return 0;
    
    const baseTranslateTokens = 6500;
    const extractTokens = aiExtract ? 250 : 0;
    
    return count * (baseTranslateTokens + extractTokens);
  };

  const estTokens = getEstimatedTokens();

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
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          overflow: 'hidden'
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
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 900, color: 'var(--foreground)', letterSpacing: '-0.5px' }}>
            Batch Translation Studio
          </Typography>
          <Typography variant="body2" sx={{ color: 'var(--muted-foreground)', fontWeight: 500 }}>
            {threadTitle || 'Novel batch processor'}
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
        {/* Toggle Mode Mode Selector */}
        <Box sx={{ mb: 3.5, display: 'flex', justifyContent: 'center' }}>
          <ToggleButtonGroup
            value={mode}
            exclusive
            onChange={(_, val) => {
              if (val) {
                setMode(val);
                if (val === 'easy') {
                  updateEasySelection(range);
                }
              }
            }}
            sx={{ 
              background: 'rgba(0,0,0,0.3)',
              p: 0.5,
              borderRadius: '16px',
              border: '1px solid rgba(255,255,255,0.05)',
              '& .MuiToggleButton-root': {
                color: 'var(--muted-foreground)',
                border: 'none',
                px: 3.5,
                py: 0.8,
                borderRadius: '12px',
                fontSize: '0.75rem',
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
            <ToggleButton value="easy">Easy Selection</ToggleButton>
            <ToggleButton value="advanced">Custom Checkbox</ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* 1. EASY MODE CONTENT */}
        {mode === 'easy' && (
          <Box sx={{ px: 1 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
              <Typography variant="overline" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'var(--primary)', fontWeight: 900 }}>
                <PlayArrow sx={{ fontSize: 16 }} /> Quantity to Translate
              </Typography>
              <Typography variant="body2" sx={{ fontWeight: 800, color: 'var(--primary)' }}>
                {range} Chapters
              </Typography>
            </Box>
            
            <Slider
              value={range}
              onChange={handleRangeChange}
              min={1}
              max={30}
              step={1}
              marks={[
                { value: 1, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>1</span> },
                { value: 5, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>5</span> },
                { value: 10, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>10</span> },
                { value: 20, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>20</span> },
                { value: 30, label: <span style={{ color: 'var(--muted-foreground)', fontSize: '10px', fontWeight: 600 }}>30</span> }
              ]}
              sx={{ 
                color: 'var(--primary)', 
                mt: 1,
                mb: 3,
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
        )}

        {/* 2. ADVANCED MODE CONTENT */}
        {mode === 'advanced' && (
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
              <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, fontWeight: 'bold' }}>
                <ListAlt fontSize="small" sx={{ color: 'var(--primary)' }} /> Select Chapters Manually
              </Typography>
              <Typography variant="caption" sx={{ color: 'var(--primary)', fontWeight: 800 }}>
                {selectedIds.length} Selected
              </Typography>
            </Box>

            {/* Quick action buttons */}
            <Box sx={{ display: 'flex', gap: 1, mb: 1.5 }}>
              <Button 
                size="small" 
                variant="outlined" 
                onClick={selectAllUntranslated}
                sx={{ 
                  fontSize: '0.65rem', 
                  borderRadius: '8px', 
                  borderColor: 'var(--primary)', 
                  color: 'var(--primary)',
                  fontWeight: 800
                }}
              >
                Untranslated Only
              </Button>
              <Button 
                size="small" 
                variant="outlined" 
                onClick={selectAll}
                sx={{ 
                  fontSize: '0.65rem', 
                  borderRadius: '8px', 
                  borderColor: 'var(--border)', 
                  color: 'var(--foreground)',
                  fontWeight: 700
                }}
              >
                Select All
              </Button>
              <Button 
                size="small" 
                variant="outlined" 
                onClick={deselectAll}
                sx={{ 
                  fontSize: '0.65rem', 
                  borderRadius: '8px', 
                  borderColor: 'var(--border)', 
                  color: 'var(--foreground)',
                  fontWeight: 700
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
                {chapters.map(ch => (
                  <ListItem 
                    key={ch.id} 
                    onClick={() => toggleChapter(ch.id)}
                    sx={{ 
                      borderRadius: '10px', 
                      mb: 0.5,
                      cursor: 'pointer',
                      background: selectedIds.includes(ch.id) ? 'rgba(var(--primary-rgb), 0.08)' : 'transparent',
                      '&:hover': { background: 'rgba(255,255,255,0.03)' }
                    }}
                  >
                    <Checkbox 
                      checked={selectedIds.includes(ch.id)} 
                      size="small"
                      sx={{ color: 'var(--muted-foreground)', '&.Mui-checked': { color: 'var(--primary)' } }}
                    />
                    <ListItemText>
                      <span style={{ fontSize: '0.8rem', fontWeight: 600, opacity: ch.has_translation ? 0.5 : 1 }}>
                        {`Ch ${ch.order}: ${ch.title_original || 'Untitled'}`}
                      </span>
                    </ListItemText>
                    {ch.has_translation && (
                      <Tooltip title="Already translated. Re-translating will overwrite it.">
                        <History sx={{ fontSize: 16, opacity: 0.5, color: 'var(--primary)' }} />
                      </Tooltip>
                    )}
                  </ListItem>
                ))}
              </List>
            </Box>
          </Box>
        )}

        {/* Target Language Selection */}
        <Box sx={{ mb: 3.5 }}>
          <Typography variant="overline" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'var(--primary)', fontWeight: 900, mb: 1.5 }}>
            <Translate sx={{ fontSize: 16 }} /> Target Language
          </Typography>

          <Box sx={{ display: 'flex', gap: 2 }}>
            {['Indonesian', 'English'].map((lang) => {
              const active = targetLang === lang;
              return (
                <button
                  key={lang}
                  type="button"
                  onClick={() => setTargetLang(lang as 'Indonesian' | 'English')}
                  style={{
                    flex: 1,
                    padding: '12px 16px',
                    borderRadius: '16px',
                    fontSize: '0.75rem',
                    fontWeight: 800,
                    border: active ? '1px solid var(--primary)' : '1px solid var(--border)',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    background: active ? 'var(--primary)' : 'rgba(0, 0, 0, 0.2)',
                    color: active ? 'var(--primary-foreground)' : 'var(--muted-foreground)',
                  }}
                  onMouseEnter={(e) => {
                    if (!active) {
                      e.currentTarget.style.borderColor = 'var(--primary)';
                      e.currentTarget.style.color = 'var(--foreground)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active) {
                      e.currentTarget.style.borderColor = 'var(--border)';
                      e.currentTarget.style.color = 'var(--muted-foreground)';
                    }
                  }}
                >
                  {lang.toUpperCase()}
                </button>
              );
            })}
          </Box>
        </Box>

        {/* Safety Engine Settings */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="overline" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'var(--primary)', fontWeight: 900, mb: 1.5 }}>
            <Settings sx={{ fontSize: 16 }} /> Engine Core Speed
          </Typography>

          <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
            <ToggleButtonGroup
              value={loadMode}
              exclusive
              onChange={(_, val) => val && setLoadMode(val)}
              sx={{ 
                background: 'rgba(0,0,0,0.3)',
                p: 0.5,
                borderRadius: '16px',
                border: '1px solid rgba(255,255,255,0.05)',
                width: '100%',
                '& .MuiToggleButton-root': {
                  color: 'var(--muted-foreground)',
                  border: 'none',
                  flexGrow: 1,
                  py: 1,
                  borderRadius: '12px',
                  fontSize: '0.75rem',
                  fontWeight: 900,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 1,
                }
              }}
            >
              <ToggleButton value="soft" sx={{
                '&.Mui-selected': {
                  background: 'rgba(76, 175, 80, 0.15) !important',
                  color: '#81c784 !important',
                  border: '1px solid var(--border)',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                  '&:hover': { background: 'rgba(76, 175, 80, 0.25) !important' }
                }
              }}>
                <Shield sx={{ fontSize: 16 }} /> SEQUENTIAL MODE (🛡️ SAFE)
              </ToggleButton>
              <ToggleButton value="hard" sx={{
                '&.Mui-selected': {
                  background: 'rgba(239, 68, 68, 0.15) !important',
                  color: '#ef5350 !important',
                  border: '1px solid var(--border)',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                  '&:hover': { background: 'rgba(239, 68, 68, 0.25) !important' }
                }
              }}>
                <Bolt sx={{ fontSize: 16 }} /> PARALLEL MODE (⚡ SPEED)
              </ToggleButton>
            </ToggleButtonGroup>
          </Box>

          <Typography variant="caption" sx={{ display: 'block', opacity: 0.6, fontStyle: 'italic', textAlign: 'center', px: 1, color: 'var(--muted-foreground)', minHeight: 32 }}>
            {loadMode === 'soft' 
              ? '🛡️ Sequential Mode: Translates chapters one by one. Fully safe for GPUs with low VRAM.' 
              : '⚡ Parallel Mode: Forces high-concurrency translation segment pipelines. Extremely fast, but may crash on limited VRAM.'}
          </Typography>
        </Box>

        {/* Overwrite Translations Panel */}
        <Box sx={{ 
          p: 2.5, 
          background: 'rgba(0,0,0,0.3)', 
          borderRadius: '20px', 
          border: '1px solid var(--border)',
          mb: 3
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
            <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'var(--foreground)', fontWeight: 'bold' }}>
              <History fontSize="small" sx={{ color: 'var(--primary)' }} /> Overwrite Translate
            </Typography>
            {overwrite ? (
              <Box sx={{ px: 1.5, py: 0.5, borderRadius: '8px', background: 'rgba(239, 68, 68, 0.12)', color: '#ef5350', fontSize: '0.65rem', fontWeight: 900 }}>
                FORCE OVERWRITE
              </Box>
            ) : (
              <Box sx={{ px: 1.5, py: 0.5, borderRadius: '8px', background: 'rgba(255,255,255,0.05)', color: 'var(--muted-foreground)', fontSize: '0.65rem', fontWeight: 900 }}>
                SKIP TRANSLATED
              </Box>
            )}
          </Box>
          
          <FormControlLabel
            control={
              <Checkbox 
                checked={overwrite} 
                onChange={(e) => setOverwrite(e.target.checked)}
                sx={{ color: 'var(--muted-foreground)', '&.Mui-checked': { color: 'var(--primary)' } }}
              />
            }
            label={
              <Box>
                <Typography variant="body2" sx={{ color: 'var(--foreground)', fontWeight: 'bold' }}>Force Overwrite Existing</Typography>
                <Typography variant="caption" sx={{ opacity: 0.5, display: 'block', color: 'var(--muted-foreground)' }}>
                  Re-translate chapters that already have saved translations.
                </Typography>
              </Box>
            }
          />
        </Box>

        {/* AI Terminology Scan Panel */}
        <Box sx={{ 
          p: 2.5, 
          background: 'rgba(0,0,0,0.3)', 
          borderRadius: '20px', 
          border: '1px solid var(--border)',
          mb: 3
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justify: 'space-between', justifyContent: 'space-between', mb: 1.5 }}>
            <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'var(--foreground)', fontWeight: 'bold' }}>
              <AutoAwesome fontSize="small" sx={{ color: 'var(--primary)' }} /> AI Glossary Extraction
            </Typography>
            {loreCount > 30 ? (
              <Box sx={{ px: 1.5, py: 0.5, borderRadius: '8px', background: 'rgba(76, 175, 80, 0.12)', color: '#81c784', fontSize: '0.65rem', fontWeight: 900 }}>
                LORE ACTIVE ({loreCount})
              </Box>
            ) : (
              <Box sx={{ px: 1.5, py: 0.5, borderRadius: '8px', background: 'rgba(255, 152, 0, 0.12)', color: '#ffb74d', fontSize: '0.65rem', fontWeight: 900 }}>
                RECOMMENDED
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
                <Typography variant="body2" sx={{ color: 'var(--foreground)', fontWeight: 'bold' }}>Glossary Scan First</Typography>
                <Typography variant="caption" sx={{ opacity: 0.5, display: 'block', color: 'var(--muted-foreground)' }}>
                  Extract fresh character names & terminology before translation runs.
                </Typography>
              </Box>
            }
          />
        </Box>

        {/* HONEST TOKEN ESTIMATOR BADGE */}
        {selectedIds.length > 0 && (
          <Box sx={{ 
            p: 2.5, 
            borderRadius: '20px', 
            background: loadMode === 'hard' ? 'rgba(239, 68, 68, 0.05)' : 'rgba(76, 175, 80, 0.05)', 
            border: loadMode === 'hard' ? '1px solid rgba(239, 68, 68, 0.2)' : '1px solid rgba(76, 175, 80, 0.2)',
            display: 'flex',
            gap: 2,
            alignItems: 'flex-start',
            mb: 2
          }}>
            <Box sx={{ 
              p: 1, 
              borderRadius: '12px', 
              background: loadMode === 'hard' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(76, 175, 80, 0.1)', 
              display: 'flex' 
            }}>
              <Bolt sx={{ color: loadMode === 'hard' ? '#ef5350' : '#81c784', fontSize: 20 }} />
            </Box>
            <Box sx={{ flexGrow: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle2" sx={{ color: loadMode === 'hard' ? '#ef5350' : '#81c784', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  {loadMode === 'hard' ? 'Parallel Burst Mode Active' : 'Sequential Safety Mode Active'}
                </Typography>
                <Typography variant="caption" sx={{ fontWeight: 900, color: 'var(--foreground)', background: 'rgba(255,255,255,0.08)', px: 1, py: 0.2, borderRadius: '6px' }}>
                  {selectedIds.length} Chapters
                </Typography>
              </Box>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', display: 'block', mt: 0.5, lineHeight: 1.4 }}>
                Estimated total context input & output:
              </Typography>
              <Typography variant="subtitle1" sx={{ color: 'var(--foreground)', fontWeight: 900, mt: 0.5, fontSize: '1rem', display: 'flex', alignItems: 'center', gap: 1 }}>
                ~{estTokens.toLocaleString()} tokens
                {aiExtract && (
                  <span style={{ fontSize: '0.65rem', fontWeight: 700, opacity: 0.6, color: 'var(--primary)' }}>
                    (Includes Glossary Scan)
                  </span>
                )}
              </Typography>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.4)', display: 'block', mt: 0.8, fontSize: '0.65rem' }}>
                *Actual tokens depend on chapter lengths and LLM system context size.
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
          disabled={isStarting || selectedIds.length === 0}
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
          {isStarting ? 'INITIALIZING...' : `TRANSLATE ${selectedIds.length} CHAPTERS`}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
