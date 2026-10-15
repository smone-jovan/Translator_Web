import { useRef, useEffect, useState, useMemo } from "react";
import ForceGraph2D from "react-force-graph-2d";
import {
  X,
  Trash2,
  Edit2,
  RotateCcw,
  Plus,
  ScanSearch,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface Relationship {
  id: number;
  source_term: string;
  target_term: string;
  relationship_type: string;
  notes?: string;
}

interface GraphNode {
  id: string;
  group: number;
  val: number;
}

interface GraphLink {
  id: number;
  source: string;
  target: string;
  label: string;
  notes?: string;
  color: string;
}

export interface RelationshipFormPayload {
  id?: number | null;
  source_term: string;
  target_term: string;
  relationship_type: string;
  notes?: string;
}

interface RelationshipGraphProps {
  relationships: Relationship[];
  isScanning?: boolean;
  onScan?: () => void;
  onSaveRelationship?: (
    payload: RelationshipFormPayload
  ) => Promise<void> | void;
  onDeleteRelationship?: (relId: number) => Promise<void> | void;
  onClearAll?: () => Promise<void> | void;
}

export default function RelationshipGraph({
  relationships,
  isScanning = false,
  onScan,
  onSaveRelationship,
  onDeleteRelationship,
  onClearAll,
}: RelationshipGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fgRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 560 });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [viewMode, setViewMode] = useState<"graph" | "table">("graph");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({
    source_term: "",
    target_term: "",
    relationship_type: "",
    notes: "",
  });

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      if (entries[0]) {
        const { width, height } = entries[0].contentRect;
        if (width > 0 && height > 0) setDimensions({ width, height });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [viewMode]);

  const getRelationColor = (relType: string): string => {
    const lower = (relType || "").toLowerCase();
    if (
      lower.includes("enem") ||
      lower.includes("musuh") ||
      lower.includes("rival") ||
      lower.includes("hostile")
    )
      return "#ef4444";
    if (
      lower.includes("master") ||
      lower.includes("guru") ||
      lower.includes("disciple") ||
      lower.includes("murid") ||
      lower.includes("mentor")
    )
      return "#eab308";
    if (
      lower.includes("lover") ||
      lower.includes("wife") ||
      lower.includes("husband") ||
      lower.includes("kekasih") ||
      lower.includes("istri") ||
      lower.includes("suami") ||
      lower.includes("fianc")
    )
      return "#ec4899";
    return "#3b82f6";
  };

  const graphData = useMemo(() => {
    const nodesMap = new Map<string, GraphNode>();
    const links: GraphLink[] = [];

    relationships.forEach((rel) => {
      if (!nodesMap.has(rel.source_term)) {
        nodesMap.set(rel.source_term, {
          id: rel.source_term,
          group: 1,
          val: 1,
        });
      }
      if (!nodesMap.has(rel.target_term)) {
        nodesMap.set(rel.target_term, {
          id: rel.target_term,
          group: 2,
          val: 1,
        });
      }
      nodesMap.get(rel.source_term)!.val += 0.5;
      nodesMap.get(rel.target_term)!.val += 0.5;

      links.push({
        id: rel.id,
        source: rel.source_term,
        target: rel.target_term,
        label: rel.relationship_type,
        notes: rel.notes,
        color: getRelationColor(rel.relationship_type),
      });
    });

    return { nodes: Array.from(nodesMap.values()), links };
  }, [relationships]);

  const selectedRelations = useMemo(() => {
    if (!selectedNode) return [];
    return relationships.filter(
      (r) =>
        r.source_term === selectedNode.id || r.target_term === selectedNode.id
    );
  }, [relationships, selectedNode]);

  const startEdit = (rel: Relationship) => {
    setEditingId(rel.id);
    setForm({
      source_term: rel.source_term,
      target_term: rel.target_term,
      relationship_type: rel.relationship_type,
      notes: rel.notes || "",
    });
    setShowForm(true);
  };

  const handleSubmit = async () => {
    if (!onSaveRelationship) return;
    await onSaveRelationship({
      id: editingId,
      source_term: form.source_term,
      target_term: form.target_term,
      relationship_type: form.relationship_type,
      notes: form.notes,
    });
    setShowForm(false);
    setEditingId(null);
    setForm({
      source_term: "",
      target_term: "",
      relationship_type: "",
      notes: "",
    });
  };

  return (
    <div className="space-y-4 h-full flex flex-col">
      {(onScan || onSaveRelationship || onClearAll) && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-bold tracking-tight">
              Jejaring Relasi Karakter ({relationships.length})
            </h3>
            <p className="text-xs text-[var(--muted-foreground)]">
              Hubungan antar tokoh yang digunakan AI untuk menentukan sapaan &
              pronomina yang tepat.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center bg-[var(--card)] border border-[var(--border)] rounded-xl p-0.5">
              <button
                type="button"
                onClick={() => setViewMode("graph")}
                className={cn(
                  "px-2.5 py-1 rounded-lg text-xs font-semibold cursor-pointer transition-colors",
                  viewMode === "graph"
                    ? "bg-[var(--primary)] text-white"
                    : "text-[var(--muted-foreground)]"
                )}
              >
                Graph 2D
              </button>
              <button
                type="button"
                onClick={() => setViewMode("table")}
                className={cn(
                  "px-2.5 py-1 rounded-lg text-xs font-semibold cursor-pointer transition-colors",
                  viewMode === "table"
                    ? "bg-[var(--primary)] text-white"
                    : "text-[var(--muted-foreground)]"
                )}
              >
                Tabel ({relationships.length})
              </button>
            </div>

            {onSaveRelationship && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setEditingId(null);
                  setForm({
                    source_term: "",
                    target_term: "",
                    relationship_type: "",
                    notes: "",
                  });
                  setShowForm(!showForm);
                }}
                className="rounded-xl gap-1.5 h-9 text-xs font-semibold cursor-pointer"
              >
                <Plus size={14} /> Add Relation
              </Button>
            )}

            {onScan && (
              <Button
                size="sm"
                onClick={onScan}
                disabled={isScanning}
                className="rounded-xl gap-1.5 h-9 text-xs font-bold shadow-lg shadow-[var(--primary)]/20 cursor-pointer"
              >
                {isScanning ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <ScanSearch size={14} />
                )}
                Scan Characters
              </Button>
            )}

            {onClearAll && relationships.length > 0 && (
              <Button
                size="sm"
                variant="ghost"
                onClick={onClearAll}
                className="rounded-xl h-9 text-xs text-rose-500 hover:bg-rose-500/10 cursor-pointer"
                title="Bersihkan seluruh relasi pada novel ini"
              >
                <Trash2 size={14} />
              </Button>
            )}
          </div>
        </div>
      )}

      {showForm && onSaveRelationship && (
        <Card className="border-[var(--primary)] bg-[var(--accent)]/5">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-sm">
                {editingId
                  ? "Edit Relasi Karakter"
                  : "Tambah Relasi Karakter Manual"}
              </h4>
              <button
                type="button"
                onClick={() => {
                  setShowForm(false);
                  setEditingId(null);
                }}
                className="p-1 rounded hover:bg-[var(--secondary)] cursor-pointer"
              >
                <X size={15} />
              </button>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <input
                value={form.source_term}
                onChange={(e) =>
                  setForm({ ...form, source_term: e.target.value })
                }
                placeholder="Tokoh 1 (mis. Xiao Yan)"
                className="bg-[var(--card)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs outline-none"
              />
              <input
                value={form.target_term}
                onChange={(e) =>
                  setForm({ ...form, target_term: e.target.value })
                }
                placeholder="Tokoh 2 (mis. Yao Lao)"
                className="bg-[var(--card)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs outline-none"
              />
              <input
                value={form.relationship_type}
                onChange={(e) =>
                  setForm({ ...form, relationship_type: e.target.value })
                }
                placeholder="Relasi (mis. Guru-Murid / Musuh)"
                className="bg-[var(--card)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs outline-none"
              />
              <input
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                placeholder="Catatan singkat (opsional)"
                className="bg-[var(--card)] border border-[var(--border)] rounded-xl px-3 py-2 text-xs outline-none"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setShowForm(false)}
                className="h-8 text-xs rounded-lg"
              >
                Batal
              </Button>
              <Button
                size="sm"
                onClick={handleSubmit}
                className="h-8 text-xs rounded-lg px-4"
              >
                Simpan Relasi
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {viewMode === "table" ? (
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--secondary)]/40 text-[10px] font-bold uppercase text-[var(--muted-foreground)]">
                <th className="p-3">Tokoh Asal</th>
                <th className="p-3">Hubungan</th>
                <th className="p-3">Tokoh Tujuan</th>
                <th className="p-3">Catatan</th>
                <th className="p-3 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {relationships.map((rel) => (
                <tr key={rel.id} className="hover:bg-[var(--secondary)]/30">
                  <td className="p-3 font-bold">{rel.source_term}</td>
                  <td className="p-3">
                    <span className="px-2 py-0.5 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] font-semibold text-[11px]">
                      {rel.relationship_type}
                    </span>
                  </td>
                  <td className="p-3 font-bold">{rel.target_term}</td>
                  <td className="p-3 text-[var(--muted-foreground)]">
                    {rel.notes || "—"}
                  </td>
                  <td className="p-3 text-right">
                    <div className="inline-flex items-center gap-1">
                      {onSaveRelationship && (
                        <button
                          type="button"
                          onClick={() => startEdit(rel)}
                          className="p-1 text-amber-500 hover:bg-amber-500/15 rounded cursor-pointer"
                        >
                          <Edit2 size={13} />
                        </button>
                      )}
                      {onDeleteRelationship && (
                        <button
                          type="button"
                          onClick={() => onDeleteRelationship(rel.id)}
                          className="p-1 text-rose-500 hover:bg-rose-500/15 rounded cursor-pointer"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          ref={containerRef}
          className="w-full flex-1 min-h-[380px] sm:min-h-[500px] bg-[var(--secondary)]/20 rounded-2xl sm:rounded-[2rem] overflow-hidden border border-[var(--border)] relative shadow-inner"
        >
          {relationships.length > 0 && (
            <div className="absolute top-3 left-3 right-3 flex flex-wrap items-center justify-between gap-2 z-10 pointer-events-none">
              <div className="flex flex-wrap items-center gap-2 bg-[var(--card)]/90 backdrop-blur-md px-3 py-1.5 rounded-full border border-[var(--border)] text-[10px] font-semibold text-[var(--muted-foreground)] shadow-sm">
                <span className="inline-flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-blue-500" />{" "}
                  Sekutu/Keluarga
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-yellow-500" />{" "}
                  Guru/Murid
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-pink-500" /> Romansa
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-500" />{" "}
                  Musuh/Rival
                </span>
              </div>

              <div className="flex items-center gap-2 pointer-events-auto">
                <button
                  type="button"
                  onClick={() => fgRef.current?.zoomToFit?.(400, 40)}
                  className="text-[10px] font-bold bg-[var(--card)]/90 backdrop-blur-md px-2.5 py-1 rounded-full border border-[var(--border)] text-[var(--foreground)] hover:border-[var(--primary)] transition-colors flex items-center gap-1 cursor-pointer shadow-sm"
                >
                  <RotateCcw size={11} /> Reset View
                </button>
                <span className="hidden sm:inline-block text-[10px] font-semibold bg-[var(--card)]/90 backdrop-blur-md px-2.5 py-1 rounded-full border border-[var(--border)] text-[var(--muted-foreground)] shadow-sm">
                  💡 Klik node untuk detail & edit
                </span>
              </div>
            </div>
          )}

          {relationships.length === 0 ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center opacity-50 p-4 text-center">
              <p className="font-bold text-base sm:text-lg">
                Belum ada relasi karakter.
              </p>
              <p className="text-xs sm:text-sm mt-1">
                Klik &ldquo;Scan Characters&rdquo; untuk ekstraksi AI atau
                &ldquo;+ Add Relation&rdquo; untuk menambah manual.
              </p>
            </div>
          ) : (
            <ForceGraph2D
              ref={fgRef}
              width={dimensions.width}
              height={dimensions.height}
              graphData={graphData}
              nodeLabel="id"
              nodeColor={(node: GraphNode) =>
                selectedNode?.id === node.id
                  ? "#f59e0b"
                  : node.group === 1
                    ? "#3b82f6"
                    : "#10b981"
              }
              nodeRelSize={6}
              linkColor="color"
              linkDirectionalArrowLength={3.5}
              linkDirectionalArrowRelPos={1}
              linkLabel={(link: GraphLink) =>
                `${link.label}${link.notes ? `\n\nNotes: ${link.notes}` : ""}`
              }
              linkCurvature={0.2}
              onNodeClick={(node: GraphNode) => setSelectedNode(node)}
            />
          )}

          {selectedNode && (
            <div className="absolute bottom-3 left-3 right-3 sm:left-auto sm:right-3 sm:w-88 bg-[var(--card)]/95 backdrop-blur-md border border-[var(--border)] rounded-2xl p-4 shadow-xl z-20 animate-in fade-in slide-in-from-bottom-2 duration-200">
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-[var(--border)]">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="w-3 h-3 rounded-full bg-amber-500 shrink-0" />
                  <h4 className="font-bold text-sm text-[var(--foreground)] truncate">
                    {selectedNode.id}
                  </h4>
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--secondary)] text-[var(--muted-foreground)] font-mono">
                    {selectedRelations.length} relasi
                  </span>
                </div>
                <button
                  onClick={() => setSelectedNode(null)}
                  className="p-1 rounded-lg text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)] transition-colors cursor-pointer"
                  aria-label="Close"
                >
                  <X size={14} />
                </button>
              </div>
              <div className="space-y-1.5 max-h-52 overflow-y-auto text-xs pr-1 custom-scrollbar">
                {selectedRelations.map((r) => {
                  const isSource = r.source_term === selectedNode.id;
                  const other = isSource ? r.target_term : r.source_term;
                  const direction = isSource ? "→" : "←";
                  return (
                    <div
                      key={r.id}
                      className="p-2.5 rounded-xl bg-[var(--secondary)]/40 border border-[var(--border)]/60 flex flex-col gap-1"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-[var(--foreground)] truncate">
                          <span className="opacity-60 mr-1">{direction}</span>
                          {other}
                        </span>
                        <div className="flex items-center gap-1 shrink-0">
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--card)] font-medium text-[var(--primary)] border border-[var(--border)]">
                            {r.relationship_type}
                          </span>
                          {onSaveRelationship && (
                            <button
                              type="button"
                              onClick={() => startEdit(r)}
                              className="p-1 rounded hover:bg-[var(--card)] text-[var(--muted-foreground)] hover:text-amber-500 transition-colors cursor-pointer"
                              title="Edit relasi"
                            >
                              <Edit2 size={11} />
                            </button>
                          )}
                          {onDeleteRelationship && (
                            <button
                              type="button"
                              onClick={() => onDeleteRelationship(r.id)}
                              className="p-1 rounded hover:bg-[var(--card)] text-[var(--muted-foreground)] hover:text-rose-500 transition-colors cursor-pointer"
                              title="Hapus relasi"
                            >
                              <Trash2 size={11} />
                            </button>
                          )}
                        </div>
                      </div>
                      {r.notes && (
                        <p className="text-[11px] text-[var(--muted-foreground)] line-clamp-2">
                          {r.notes}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
