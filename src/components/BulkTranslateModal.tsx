/* eslint-disable react-hooks/set-state-in-effect */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/ban-ts-comment */
/* eslint-disable react-hooks/exhaustive-deps */
import { useState, useEffect, memo, useCallback, useMemo } from 'react';
import { Virtuoso } from 'react-virtuoso';
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
import { getApiUrl } from '@/lib/api';

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
  translation_status?: string;
}

interface BulkTranslateModalProps {
  isOpen: boolean;
  onClose: () => void;
  threadId: number;
  threadTitle: string;
  chapters: Chapter[];
  onStartBatch: (chapterIds: number[], aiExtract: boolean, loadMode: 'soft' | 'hard', targetLang: string, overwrite: boolean, translationMode: 'quality' | 'fast') => void;
  onSuccess?: () => void;
}

const ChapterItem = memo(({ ch, isSelected, onToggle }: { ch: Chapter, isSelected: boolean, onToggle: (id: number) => void }) => (
  <ListItem 
    onClick={() => onToggle(ch.id)}
    sx={{ 
      borderRadius: '10px', 
      mb: 0.5,
      cursor: 'pointer',
      background: isSelected ? 'rgba(var(--primary-rgb), 0.08)' : 'transparent',
      '&:hover': { background: 'rgba(255,255,255,0.03)' }
    }}
  >
    <Checkbox 
      checked={isSelected} 
      size="small"
      sx={{ color: 'var(--muted-foreground)', '&.Mui-checked': { color: 'var(--primary)' } }}
    />
    <ListItemText>
      <span style={{ fontSize: '0.8rem', fontWeight: 600, opacity: ch.has_translation ? 0.5 : 1 }}>
        {`Ch ${ch.order}: ${ch.title_original || 'Untitled'}`}
      </span>
      {ch.translation_status === 'prohibited' && (
        <span style={{ marginLeft: 8, fontSize: '0.6rem', fontWeight: 900, background: 'rgba(239, 68, 68, 0.15)', color: '#ef5350', padding: '2px 6px', borderRadius: '4px' }}>
          PROHIBITED
        </span>
      )}
    </ListItemText>
    {ch.has_translation && (
      <Tooltip title="Already translated. Re-translating will overwrite it.">
        <History sx={{ fontSize: 16, opacity: 0.5, color: 'var(--primary)' }} />
      </Tooltip>
    )}
  </ListItem>
));

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
  const [translationMode, setTranslationMode] = useState<'quality' | 'fast'>(
    () => (localStorage.getItem('translation_mode') as 'quality' | 'fast') || 'quality'
  );
  const [includeProhibited, setIncludeProhibited] = useState<boolean>(false);

  // Update selected IDs in Easy Mode
  const updateEasySelection = (quantity: number, incProhibited = includeProhibited) => {
    const untranslated = chapters.filter(c => {
      // is untranslated AND (we include prohibited/error OR it's neither)
      const valid = !c.has_translation && (incProhibited || (c.translation_status !== 'prohibited' && c.translation_status !== 'error'));
      return valid;
    });

    const baseList = untranslated.length > 0 ? untranslated : chapters.filter(c => incProhibited || (c.translation_status !== 'prohibited' && c.translation_status !== 'error'));
    
    const result = baseList.slice(0, quantity).map(c => c.id);
    setSelectedIds(result);
  };

  useEffect(() => {
    if (isOpen) {
      if (!hasInitialized) {
        // Fetch lorebook count to determine recommendation
        fetch(getApiUrl(`/api/threads/${threadId}/lorebook`))
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

  const toggleChapter = useCallback((id: number) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  }, []);

  const selectedSet = useMemo(() => new Set(selectedIds), [selectedIds]);

  const selectAllUntranslated = () => {
    const untranslated = chapters.filter(c => !c.has_translation && (includeProhibited || (c.translation_status !== 'prohibited' && c.translation_status !== 'error'))).map(c => c.id);
    setSelectedIds(untranslated);
  };

  const selectAll = () => {
    const all = chapters.filter(c => includeProhibited || (c.translation_status !== 'prohibited' && c.translation_status !== 'error')).map(c => c.id);
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
      await onStartBatch(selectedIds, aiExtract, loadMode, targetLang, overwrite, translationMode);
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

            {/* Quick Prohibited Toggle in Easy Mode */}
            {(() => {
              const prohibitedCount = chapters.filter(c => c.translation_status === 'prohibited').length;
              if (prohibitedCount === 0) return null;
              
              return (
                <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', p: 1.5, background: 'rgba(239, 68, 68, 0.1)', borderRadius: '12px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                  <Typography variant="caption" sx={{ color: '#ef5350', fontWeight: 700, display: 'flex', alignItems: 'center' }}>
                    <Shield sx={{ fontSize: 16, mr: 0.5 }} />
                    {prohibitedCount} chapters were previously blocked by AI.
                  </Typography>
                  <Button 
                    size="small" 
                    variant={includeProhibited ? "outlined" : "contained"}
                    onClick={() => {
                      const newVal = !includeProhibited;
                      setIncludeProhibited(newVal);
                      updateEasySelection(range, newVal);
                    }}
                    sx={{ 
                      fontSize: '0.65rem', 
                      fontWeight: 800, 
                      borderRadius: '8px',
                      background: includeProhibited ? 'transparent' : '#ef5350', 
                      borderColor: '#ef5350',
                      color: includeProhibited ? '#ef5350' : '#fff',
                      boxShadow: 'none',
                      '&:hover': { background: '#d32f2f', color: '#fff', borderColor: '#d32f2f' }
                    }}
                  >
                    {includeProhibited ? 'Exclude' : 'Include (+)'}
                  </Button>
                </Box>
              );
            })()}
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
              <Button 
                size="small" 
                variant="outlined" 
                onClick={() => {
                  const prohibited = chapters.filter(c => c.translation_status === 'prohibited').map(c => c.id);
                  setSelectedIds(prev => Array.from(new Set([...prev, ...prohibited])));
                }}
                sx={{ 
                  fontSize: '0.65rem', 
                  borderRadius: '8px', 
                  borderColor: 'rgba(239, 68, 68, 0.5)', 
                  color: '#ef5350',
                  fontWeight: 700
                }}
              >
                Select Prohibited
              </Button>
            </Box>

            {/* Manual Checkbox List */}
            <Box sx={{ 
              height: 210, 
              background: 'rgba(0,0,0,0.25)', 
              border: '1px solid var(--border)',
              borderRadius: '16px', 
              p: 1 
            }}>
              <List dense sx={{ py: 0, height: '100%', p: 0 }}>
                <Virtuoso
                  style={{ height: '100%' }}
                  data={chapters}
                  itemContent={(index, ch) => (
                    <ChapterItem 
                      key={ch.id} 
                      ch={ch} 
                      isSelected={selectedSet.has(ch.id)} 
                      onToggle={toggleChapter} 
                    />
                  )}
                />
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

        {/* Current Model Info */}
        <Box sx={{ mb: 3, p: 2, background: 'rgba(0,0,0,0.2)', borderRadius: '16px', border: '1px solid var(--border)' }}>
          <Typography variant="caption" sx={{ color: 'var(--muted-foreground)', fontWeight: 600, display: 'block', mb: 1 }}>
            Active Model
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
            <Box sx={{ 
              width: 32, height: 32, borderRadius: '10px', 
              background: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '14px', fontWeight: 900, color: 'var(--primary-foreground)'
            }}>
              {(() => {
                const provider = localStorage.getItem('llm_provider') || 'lm_studio';
                if (provider === 'gemini') return 'G';
                if (provider === 'openai') return 'O';
                return 'L';
              })()}
            </Box>
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 800, fontSize: '0.85rem', color: 'var(--foreground)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {localStorage.getItem('gemini_model') || localStorage.getItem('lm_model') || 'Unknown Model'}
              </Typography>
              <Typography variant="caption" sx={{ color: 'var(--muted-foreground)', fontSize: '0.7rem' }}>
                {(() => {
                  const provider = localStorage.getItem('llm_provider') || 'lm_studio';
                  const model = localStorage.getItem('gemini_model') || '';
                  if (provider === 'gemini') {
                    const rpmMap: Record<string, number> = {
                      'gemini-3.1-flash-lite': 15,
                      'gemini-2.5-flash-lite': 10,
                      'gemini-2.5-flash': 5,
                      'gemini-3-flash': 5,
                      'gemini-3.5-flash': 5,
                      'gemma-4-31b': 15,
                      'gemma-4-26b': 15,
                    };
                    const rpm = rpmMap[model] || 0;
                    return `Gemini • ${rpm} RPM${rpm > 0 ? ' (free)' : ''}`;
                  }
                  if (provider === 'openai') return 'OpenAI Cloud';
                  return 'LM Studio (Local)';
                })()}
              </Typography>
            </Box>
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

        {/* Translation Quality Mode */}
        <Box sx={{ mb: 3 }}>
          <Typography variant="overline" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'var(--primary)', fontWeight: 900, mb: 1.5 }}>
            <Translate sx={{ fontSize: 16 }} /> Translation Quality
          </Typography>

          <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
            <ToggleButtonGroup
              value={translationMode}
              exclusive
              onChange={(_, val) => val && setTranslationMode(val)}
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
              <ToggleButton value="quality" sx={{
                '&.Mui-selected': {
                  background: 'rgba(156, 39, 176, 0.15) !important',
                  color: '#ce93d8 !important',
                  border: '1px solid var(--border)',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                  '&:hover': { background: 'rgba(156, 39, 176, 0.25) !important' }
                }
              }}>
                <AutoAwesome sx={{ fontSize: 16 }} /> QUALITY
              </ToggleButton>
              <ToggleButton value="fast" sx={{
                '&.Mui-selected': {
                  background: 'rgba(255, 152, 0, 0.15) !important',
                  color: '#ffb74d !important',
                  border: '1px solid var(--border)',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                  '&:hover': { background: 'rgba(255, 152, 0, 0.25) !important' }
                }
              }}>
                <Bolt sx={{ fontSize: 16 }} /> FAST
              </ToggleButton>
            </ToggleButtonGroup>
          </Box>

          <Typography variant="caption" sx={{ display: 'block', opacity: 0.6, fontStyle: 'italic', textAlign: 'center', px: 1, color: 'var(--muted-foreground)', minHeight: 32 }}>
            {translationMode === 'quality'
              ? '✨ Quality: Full glossary (30 terms), style guide injection, higher token cap. Best for Gemini.'
              : '⚡ Fast: Minimal glossary (10 terms), no style guide, 10K token cap. Best for LM Studio.'}
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

        {/* Prohibited Content Toggle */}
        <Box sx={{ 
          p: 2.5, 
          background: 'rgba(0,0,0,0.3)', 
          borderRadius: '20px', 
          border: '1px solid var(--border)',
          mb: 3
        }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
            <Typography variant="subtitle2" sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'var(--foreground)', fontWeight: 'bold' }}>
              <Shield fontSize="small" sx={{ color: '#ef5350' }} /> Retry Prohibited
            </Typography>
            {includeProhibited ? (
              <Box sx={{ px: 1.5, py: 0.5, borderRadius: '8px', background: 'rgba(239, 68, 68, 0.12)', color: '#ef5350', fontSize: '0.65rem', fontWeight: 900 }}>
                RISKY
              </Box>
            ) : (
              <Box sx={{ px: 1.5, py: 0.5, borderRadius: '8px', background: 'rgba(76, 175, 80, 0.12)', color: '#81c784', fontSize: '0.65rem', fontWeight: 900 }}>
                SAFE (IGNORED)
              </Box>
            )}
          </Box>
          
          <FormControlLabel
            control={
              <Checkbox 
                checked={includeProhibited} 
                onChange={(e) => {
                  const val = e.target.checked;
                  setIncludeProhibited(val);
                  if (mode === 'easy') {
                    updateEasySelection(range, val);
                  }
                }}
                sx={{ color: 'var(--muted-foreground)', '&.Mui-checked': { color: '#ef5350' } }}
              />
            }
            label={
              <Box>
                <Typography variant="body2" sx={{ color: 'var(--foreground)', fontWeight: 'bold' }}>Include Prohibited Content</Typography>
                <Typography variant="caption" sx={{ opacity: 0.5, display: 'block', color: 'var(--muted-foreground)' }}>
                  Translates chapters previously blocked by AI due to adult/violent content. May cause failures.
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
