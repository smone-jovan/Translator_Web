import { useRef, useEffect, useState, useMemo } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { X } from "lucide-react";

interface Relationship {
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
  source: string;
  target: string;
  label: string;
  notes?: string;
  color: string;
}

interface RelationshipGraphProps {
  relationships: Relationship[];
}

export default function RelationshipGraph({
  relationships,
}: RelationshipGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      if (entries[0]) {
        const { width, height } = entries[0].contentRect;
        setDimensions({ width, height });
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const graphData = useMemo(() => {
    const nodesMap = new Map<
      string,
      { id: string; group: number; val: number }
    >();
    const links: GraphLink[] = [];

    relationships.forEach((rel) => {
      // Create nodes if they don't exist
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

      // Increase node weight
      const srcNode = nodesMap.get(rel.source_term)!;
      srcNode.val += 0.5;
      const tgtNode = nodesMap.get(rel.target_term)!;
      tgtNode.val += 0.5;

      // Add link
      links.push({
        source: rel.source_term,
        target: rel.target_term,
        label: rel.relationship_type,
        notes: rel.notes,
        color: rel.relationship_type.toLowerCase().includes("enem")
          ? "#ef4444"
          : rel.relationship_type.toLowerCase().includes("master")
            ? "#eab308"
            : "#3b82f6",
      });
    });

    return {
      nodes: Array.from(nodesMap.values()),
      links: links,
    };
  }, [relationships]);

  const selectedRelations = useMemo(() => {
    if (!selectedNode) return [];
    return relationships.filter(
      (r) =>
        r.source_term === selectedNode.id || r.target_term === selectedNode.id
    );
  }, [relationships, selectedNode]);

  return (
    <div
      ref={containerRef}
      className="w-full h-full min-h-[380px] sm:min-h-[500px] bg-[var(--secondary)]/20 rounded-2xl sm:rounded-[2rem] overflow-hidden border border-[var(--border)] relative shadow-inner"
    >
      {relationships.length > 0 && (
        <div className="absolute top-3 right-3 pointer-events-none flex justify-end z-10">
          <span className="text-[10px] font-semibold bg-[var(--card)]/90 backdrop-blur-md px-2.5 py-1 rounded-full border border-[var(--border)] text-[var(--muted-foreground)] shadow-sm">
            💡 Sentuh node untuk info • Geser di luar kanvas untuk scroll
          </span>
        </div>
      )}
      {relationships.length === 0 ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center opacity-40 p-4 text-center">
          <p className="font-bold text-base sm:text-lg">
            No relationships found.
          </p>
          <p className="text-xs sm:text-sm mt-1">
            Click 'Scan Relationships' to extract character connections.
          </p>
        </div>
      ) : (
        <ForceGraph2D
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeLabel="id"
          nodeColor={(node: GraphNode) =>
            node.group === 1 ? "#3b82f6" : "#10b981"
          }
          nodeRelSize={6}
          linkColor="color"
          linkDirectionalArrowLength={3.5}
          linkDirectionalArrowRelPos={1}
          linkLabel={(link: GraphLink) =>
            `${link.label}${link.notes ? `\n\nNotes: ${link.notes}` : ""}`
          }
          linkCurvature={0.2}
          onNodeClick={(node: GraphNode) => {
            setSelectedNode(node);
          }}
        />
      )}

      {selectedNode && (
        <div className="absolute bottom-3 left-3 right-3 sm:left-auto sm:right-3 sm:w-80 bg-[var(--card)]/95 backdrop-blur-md border border-[var(--border)] rounded-2xl p-4 shadow-xl z-20 animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-[var(--border)]">
            <div className="flex items-center gap-2 min-w-0">
              <span className="w-3 h-3 rounded-full bg-blue-500 shrink-0" />
              <h4 className="font-bold text-sm text-[var(--foreground)] truncate">
                {selectedNode.id}
              </h4>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="p-1 rounded-lg text-[var(--muted-foreground)] hover:bg-[var(--secondary)] hover:text-[var(--foreground)] transition-colors cursor-pointer"
              aria-label="Close"
            >
              <X size={14} />
            </button>
          </div>
          <div className="space-y-1.5 max-h-48 overflow-y-auto text-xs pr-1">
            {selectedRelations.length === 0 ? (
              <p className="text-[var(--muted-foreground)] italic py-2 text-center">
                Tidak ada koneksi relasi spesifik.
              </p>
            ) : (
              selectedRelations.map((r) => {
                const isSource = r.source_term === selectedNode.id;
                const other = isSource ? r.target_term : r.source_term;
                const direction = isSource ? "→" : "←";
                return (
                  <div
                    key={r.id}
                    className="p-2 rounded-xl bg-[var(--secondary)]/40 border border-[var(--border)]/50 flex flex-col gap-0.5"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-[var(--foreground)] truncate">
                        <span className="opacity-60 mr-1">{direction}</span>
                        {other}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--card)] font-medium text-[var(--primary)] border border-[var(--border)] shrink-0">
                        {r.relationship_type}
                      </span>
                    </div>
                    {r.notes && (
                      <p className="text-[11px] text-[var(--muted-foreground)] line-clamp-2 mt-0.5">
                        {r.notes}
                      </p>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
