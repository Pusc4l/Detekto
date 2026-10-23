"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";
import ForceGraph2D, { type ForceGraphMethods, type LinkObject, type NodeObject } from "react-force-graph-2d";
import { INK, drawLinkShape, drawNodeShape, edgeKey, nodeSize } from "@/lib/graphDraw";
import type { GraphMapLink, GraphMapNode } from "@/lib/types";

type GNode = NodeObject<GraphMapNode>;
// source/target dibuat dari tipe pustaka (string | objek node) — setelah init force-graph menggantinya menjadi objek node.
type LinkExtra = Omit<GraphMapLink, "source" | "target">;
type GLink = LinkObject<GraphMapNode, LinkExtra>;

const HEAVY_GRAPH_NODES = 400;

interface Props {
  nodes: GraphMapNode[];
  links: GraphMapLink[];
  width: number;
  height: number;
  selectedId: string | null;
  highlightIds: ReadonlySet<string>;
  pathEdges: ReadonlySet<string>;
  onSelect: (id: string | null) => void;
  focusToken: number;
  focusId: string | null;
}

/** Kanvas 2D Neo-Brutalist: node persegi tajam, garis tegas, latar hitam. Dirender hanya di klien (dimuat via next/dynamic ssr:false). */
export default function ForceGraphCanvas({ nodes, links, width, height, selectedId, highlightIds, pathEdges, onSelect, focusToken, focusId }: Props) {
  const fgRef = useRef<ForceGraphMethods<GraphMapNode, LinkExtra> | undefined>(undefined);
  const wrapRef = useRef<HTMLDivElement>(null);
  const heavy = nodes.length > HEAVY_GRAPH_NODES;
  const animate = !heavy && (highlightIds.size > 0 || links.some((l) => l.type === "AMPLIFIES"));

  // force-graph memutasi objek data (menambah x/y, mengganti source/target) -> beri salinan agar state React tetap murni.
  const graphData = useMemo(
    () => ({ nodes: nodes.map((n) => ({ ...n }) as GNode), links: links.map((l) => ({ ...l }) as GLink) }),
    [nodes, links],
  );

  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([entry]) => {
      if (entry?.isIntersecting) fgRef.current?.resumeAnimation();
      else fgRef.current?.pauseAnimation(); // jangan membakar CPU saat graf di luar layar
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (focusToken === 0) return;
    const fg = fgRef.current;
    if (!fg) return;
    const target = focusId ? graphData.nodes.find((n) => n.id === focusId) : undefined;
    if (target && typeof target.x === "number" && typeof target.y === "number") {
      fg.centerAt(target.x, target.y, 500);
      fg.zoom(2.6, 500);
    } else {
      fg.zoomToFit(500, 40);
    }
  }, [focusToken, focusId, graphData]);

  const dimmed = highlightIds.size > 0;

  const drawNode = useCallback(
    (node: GNode, ctx: CanvasRenderingContext2D, scale: number) => {
      const id = String(node.id ?? "");
      drawNodeShape(ctx, node, scale, id === selectedId, dimmed && !highlightIds.has(id));
    },
    [selectedId, highlightIds, dimmed],
  );

  const hitArea = useCallback((node: GNode, color: string, ctx: CanvasRenderingContext2D) => {
    const size = nodeSize(node) + 4;
    ctx.fillStyle = color;
    ctx.fillRect((node.x ?? 0) - size / 2, (node.y ?? 0) - size / 2, size, size);
  }, []);

  const drawLink = useCallback(
    (link: GLink, ctx: CanvasRenderingContext2D, scale: number) => {
      const s = link.source;
      const t = link.target;
      if (typeof s !== "object" || typeof t !== "object" || s === null || t === null) return;
      const onPath = pathEdges.has(edgeKey(String(s.id ?? ""), String(t.id ?? "")));
      drawLinkShape(ctx, s, t, link.type, onPath, dimmed && !onPath, animate, scale, performance.now());
    },
    [pathEdges, dimmed, animate],
  );

  return (
    <div ref={wrapRef} style={{ width, height }}>
      <ForceGraph2D<GraphMapNode, LinkExtra>
        ref={fgRef}
        graphData={graphData}
        width={width}
        height={height}
        backgroundColor={INK}
        nodeId="id"
        nodeLabel={() => ""} // tooltip bawaan memakai innerHTML -> dimatikan (anti-XSS); detail tampil di panel React
        nodeCanvasObject={drawNode}
        nodePointerAreaPaint={hitArea}
        linkCanvasObject={drawLink}
        linkCanvasObjectMode={() => "replace"}
        autoPauseRedraw={!animate}
        cooldownTicks={heavy ? 80 : 160}
        warmupTicks={heavy ? 20 : 40}
        d3AlphaDecay={0.04}
        d3VelocityDecay={0.35}
        enableNodeDrag
        onNodeClick={(n) => onSelect(String(n.id ?? ""))}
        onBackgroundClick={() => onSelect(null)}
        onEngineStop={() => {
          if (selectedId === null) fgRef.current?.zoomToFit(400, 40);
        }}
      />
    </div>
  );
}
