import React, { useRef, useEffect, useState, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

interface Relationship {
  id: number;
  source_term: string;
  target_term: string;
  relationship_type: string;
  notes?: string;
}

interface RelationshipGraphProps {
  relationships: Relationship[];
}

export default function RelationshipGraph({ relationships }: RelationshipGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });

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
    const nodesMap = new Map<string, { id: string; group: number; val: number }>();
    const links: any[] = [];

    relationships.forEach(rel => {
      // Create nodes if they don't exist
      if (!nodesMap.has(rel.source_term)) {
        nodesMap.set(rel.source_term, { id: rel.source_term, group: 1, val: 1 });
      }
      if (!nodesMap.has(rel.target_term)) {
        nodesMap.set(rel.target_term, { id: rel.target_term, group: 2, val: 1 });
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
        color: rel.relationship_type.toLowerCase().includes('enem') ? '#ef4444' : 
               rel.relationship_type.toLowerCase().includes('master') ? '#eab308' : 
               '#3b82f6'
      });
    });

    return {
      nodes: Array.from(nodesMap.values()),
      links: links
    };
  }, [relationships]);

  return (
    <div ref={containerRef} className="w-full h-full min-h-[500px] bg-[var(--secondary)]/20 rounded-[2rem] overflow-hidden border border-[var(--border)] relative shadow-inner">
      {relationships.length === 0 ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center opacity-40">
          <p className="font-bold text-lg">No relationships found.</p>
          <p className="text-sm">Click 'Scan Relationships' to extract character connections.</p>
        </div>
      ) : (
        <ForceGraph2D
          width={dimensions.width}
          height={dimensions.height}
          graphData={graphData}
          nodeLabel="id"
          nodeColor={(node: any) => node.group === 1 ? '#3b82f6' : '#10b981'}
          nodeRelSize={6}
          linkColor="color"
          linkDirectionalArrowLength={3.5}
          linkDirectionalArrowRelPos={1}
          linkLabel={(link: any) => `${link.label}${link.notes ? `\n\nNotes: ${link.notes}` : ''}`}
          linkCurvature={0.2}
          onNodeClick={(node: any, event) => {
            // Keep it simple for now
            console.log(node);
          }}
        />
      )}
    </div>
  );
}
