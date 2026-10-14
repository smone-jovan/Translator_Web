import { useState } from "react";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import Button from "@mui/material/Button";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import CircularProgress from "@mui/material/CircularProgress";
import Close from "@mui/icons-material/Close";
import { Trash2 } from "lucide-react";
import { getApiUrl, invalidateThreadCache } from "@/lib/api";
import { toast } from "sonner";

export interface TocChapter {
  title: string;
  url: string;
}

interface TocImportModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  novelTitle: string;
  chapters: TocChapter[];
  threadId: string | number | null;
  baseUrl?: string;
  onSuccess?: (threadId: number) => void;
}

export function TocImportModal({
  open,
  onOpenChange,
  novelTitle,
  chapters: initialChapters,
  threadId,
  baseUrl,
  onSuccess,
}: TocImportModalProps) {
  const [chapters, setChapters] = useState<TocChapter[]>(initialChapters);
  const [isImporting, setIsImporting] = useState(false);
  const [genres, setGenres] = useState("");

  const [prevInitialChapters, setPrevInitialChapters] =
    useState(initialChapters);
  const [prevOpen, setPrevOpen] = useState(open);

  if (initialChapters !== prevInitialChapters || open !== prevOpen) {
    setChapters(initialChapters);
    setGenres("");
    setPrevInitialChapters(initialChapters);
    setPrevOpen(open);
  }

  const removeChapter = (index: number) => {
    setChapters((prev) => prev.filter((_, i) => i !== index));
  };

  const handleImport = async () => {
    if (chapters.length === 0) return;
    setIsImporting(true);

    try {
      interface ImportPayload {
        chapters: TocChapter[];
        thread_id?: number;
        title?: string;
        base_url?: string;
        genres?: string;
      }
      const payload: ImportPayload = { chapters };
      if (threadId && threadId !== "new") {
        payload.thread_id =
          typeof threadId === "number"
            ? threadId
            : parseInt(threadId as string);
      } else {
        payload.title = novelTitle;
        if (baseUrl) payload.base_url = baseUrl;
        if (genres.trim()) payload.genres = genres.trim();
      }

      const res = await fetch(getApiUrl("/api/threads/bulk-import-toc"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("Failed to import chapters");

      const data = await res.json();
      invalidateThreadCache(data.thread_id);
      toast.success(`Successfully imported ${data.imported_count} chapters!`);
      onOpenChange(false);
      if (onSuccess) onSuccess(data.thread_id);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : "Import failed";
      toast.error(errorMsg);
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={() => !isImporting && onOpenChange(false)}
      fullWidth
      maxWidth="md"
      {...({
        PaperProps: {
          sx: {
            background: "var(--card)",
            border: "1px solid var(--border)",
            borderRadius: { xs: "0px", sm: "24px" },
            color: "var(--foreground)",
            m: { xs: 0, sm: 2 },
            maxHeight: { xs: "100dvh", sm: "90vh" },
            height: { xs: "100%", sm: "auto" },
          },
        },
      } as Record<string, unknown>)}
    >
      <DialogTitle
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          p: { xs: 2, sm: 3 },
        }}
      >
        <Box sx={{ minWidth: 0, pr: 1 }}>
          <Typography
            variant="h6"
            sx={{
              fontWeight: "bold",
              fontSize: { xs: "1.05rem", sm: "1.25rem" },
            }}
          >
            Import Table of Contents
          </Typography>
          <Typography
            variant="body2"
            sx={{
              color: "var(--muted-foreground)",
              fontSize: { xs: "0.75rem", sm: "0.875rem" },
            }}
          >
            Found {chapters.length} chapters for <strong>{novelTitle}</strong>.
          </Typography>
        </Box>
        <IconButton
          onClick={() => onOpenChange(false)}
          disabled={isImporting}
          sx={{ color: "var(--muted-foreground)", flexShrink: 0 }}
        >
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent
        dividers
        sx={{ borderColor: "var(--border)", p: 0, flex: 1 }}
      >
        {(!threadId || threadId === "new") && (
          <Box
            sx={{
              p: { xs: 1.5, sm: 2 },
              borderBottom: "1px solid var(--border)",
              display: "flex",
              flexDirection: "column",
              gap: 1,
            }}
          >
            <Typography
              variant="caption"
              sx={{
                fontWeight: "bold",
                textTransform: "uppercase",
                color: "var(--muted-foreground)",
              }}
            >
              Genres (comma-separated)
            </Typography>
            <input
              type="text"
              placeholder="e.g. Fantasy, Xianxia, Romance"
              value={genres}
              onChange={(e) => setGenres(e.target.value)}
              className="w-full bg-[var(--input)] border border-[var(--border)] rounded-xl py-2 px-3 text-xs sm:text-sm text-[var(--foreground)] focus:outline-none focus:border-[var(--primary)]"
              disabled={isImporting}
            />
          </Box>
        )}
        <List
          dense
          sx={{
            maxHeight: { xs: "calc(100vh - 280px)", sm: "50vh" },
            overflow: "auto",
            p: 1,
          }}
        >
          {chapters.length === 0 ? (
            <Typography
              sx={{
                textAlign: "center",
                p: 4,
                color: "var(--muted-foreground)",
              }}
            >
              No chapters selected.
            </Typography>
          ) : (
            chapters.map((chap, idx) => (
              <ListItem
                key={idx}
                secondaryAction={
                  <IconButton
                    edge="end"
                    onClick={() => removeChapter(idx)}
                    title="Remove"
                    sx={{ color: "rgba(239, 68, 68, 0.7)" }}
                  >
                    <Trash2 size={18} />
                  </IconButton>
                }
                sx={{
                  borderBottom: "1px solid rgba(255,255,255,0.05)",
                  "&:hover": { background: "rgba(255,255,255,0.02)" },
                }}
              >
                <ListItemText
                  primary={
                    <Box
                      sx={{
                        fontWeight: 600,
                        color: "var(--foreground)",
                        fontSize: { xs: "0.8rem", sm: "0.9rem" },
                      }}
                    >
                      {chap.title}
                    </Box>
                  }
                  secondary={
                    <Box
                      sx={{
                        color: "var(--primary)",
                        fontSize: "0.75rem",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {chap.url}
                    </Box>
                  }
                />
              </ListItem>
            ))
          )}
        </List>
      </DialogContent>

      <DialogActions
        sx={{
          p: { xs: 2, sm: 2.5 },
          display: "flex",
          flexDirection: { xs: "column-reverse", sm: "row" },
          alignItems: { xs: "stretch", sm: "center" },
          justifyContent: "space-between",
          gap: 1.5,
        }}
      >
        <Typography
          variant="body2"
          sx={{
            color: "var(--muted-foreground)",
            textAlign: { xs: "center", sm: "left" },
          }}
        >
          Total to import: <strong>{chapters.length}</strong>
        </Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Button
            onClick={() => onOpenChange(false)}
            disabled={isImporting}
            sx={{
              flex: { xs: 1, sm: "initial" },
              color: "var(--foreground)",
              borderRadius: "12px",
            }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleImport}
            disabled={isImporting || chapters.length === 0}
            sx={{
              flex: { xs: 1, sm: "initial" },
              background: "var(--primary)",
              color: "var(--primary-foreground)",
              borderRadius: "12px",
              fontWeight: "bold",
            }}
            startIcon={
              isImporting ? (
                <CircularProgress size={16} color="inherit" />
              ) : null
            }
          >
            {isImporting ? "Importing..." : "Import All"}
          </Button>
        </Box>
      </DialogActions>
    </Dialog>
  );
}
