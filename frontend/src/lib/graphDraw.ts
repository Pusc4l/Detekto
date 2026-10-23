import type { GraphMapNode, NodeKind } from "@/lib/types";

export const KIND_COLOR: Record<NodeKind, string> = {
  buzzer_a: "#FF0033",
  buzzer_b: "#FF0033",
  organic: "#00CC66",
  group: "#FFE600",
  post: "#F4F0EA",
  target: "#FF4D00",
  discovered: "#FF007A",
};
export const INK = "#000000";
export const CANVAS_BG = "#F4F0EA";

export interface PositionedNode extends GraphMapNode {
  x?: number;
  y?: number;
}

/** Hapus karakter bidi-override / kontrol agar label kanvas tidak bisa dimanipulasi urutannya. */
export const safeLabel = (s: string): string => s.replace(/[\u0000-\u001F\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]/g, "").slice(0, 28);
export const edgeKey = (a: string, b: string): string => (a < b ? `${a}|${b}` : `${b}|${a}`);

export function nodeSize(n: GraphMapNode): number {
  const base = n.label === "Group" ? 9 : n.label === "Post" ? 5 : 6;
  return base + 9 * n.centrality + (n.is_patient_zero ? 8 : 0);
}

export function drawNodeShape(ctx: CanvasRenderingContext2D, node: PositionedNode, scale: number, selected: boolean, dimmed: boolean): void {
  const x = node.x ?? 0;
  const y = node.y ?? 0;
  const size = nodeSize(node);
  ctx.globalAlpha = dimmed ? 0.22 : 1;

  if (node.is_patient_zero) {
    const ring = size + 10 / scale;
    ctx.lineWidth = 5 / scale;
    ctx.strokeStyle = "#FF4D00";
    ctx.strokeRect(x - ring / 2 - 2 / scale, y - ring / 2 - 2 / scale, ring + 4 / scale, ring + 4 / scale);
  }
  ctx.fillStyle = KIND_COLOR[node.kind] ?? "#FFFFFF";
  ctx.fillRect(x - size / 2, y - size / 2, size, size);
  ctx.lineWidth = (selected ? 4 : 2) / scale;
  ctx.strokeStyle = selected ? "#FF007A" : CANVAS_BG;
  ctx.strokeRect(x - size / 2, y - size / 2, size, size);

  const showLabel = node.is_patient_zero || selected || (node.centrality >= 0.45 && scale >= 0.6) || scale >= 2.5;
  if (showLabel) {
    const text = node.is_patient_zero ? `PATIENT ZERO · ${safeLabel(node.name)}` : safeLabel(node.name);
    ctx.font = `700 ${12 / scale}px monospace`;
    const w = ctx.measureText(text).width;
    ctx.fillStyle = node.is_patient_zero ? "#FFE600" : INK;
    ctx.fillRect(x + size / 2 + 3 / scale, y - 8 / scale, w + 6 / scale, 14 / scale);
    ctx.lineWidth = 1.5 / scale;
    ctx.strokeStyle = CANVAS_BG;
    ctx.strokeRect(x + size / 2 + 3 / scale, y - 8 / scale, w + 6 / scale, 14 / scale);
    ctx.fillStyle = node.is_patient_zero ? INK : CANVAS_BG;
    ctx.textBaseline = "middle";
    ctx.fillText(text, x + size / 2 + 6 / scale, y - 1 / scale);
  }
  ctx.globalAlpha = 1;
}

export function drawLinkShape(
  ctx: CanvasRenderingContext2D,
  a: { x?: number; y?: number },
  b: { x?: number; y?: number },
  type: string,
  onPath: boolean,
  dimmed: boolean,
  animate: boolean,
  scale: number,
  now: number,
): void {
  ctx.globalAlpha = dimmed ? 0.1 : 1;
  ctx.beginPath();
  ctx.moveTo(a.x ?? 0, a.y ?? 0);
  ctx.lineTo(b.x ?? 0, b.y ?? 0);
  if (onPath || type === "AMPLIFIES") {
    ctx.setLineDash([8 / scale, 6 / scale]);
    ctx.lineDashOffset = animate ? -(now / 45) / scale : 0; // garis putus-putus "mengalir" menuju Patient Zero
    ctx.strokeStyle = "#FF007A";
    ctx.lineWidth = 3.5 / scale;
  } else {
    ctx.setLineDash(type === "POSSIBLE_ALT" ? [3 / scale, 3 / scale] : []);
    ctx.strokeStyle = type === "LINKS_TO" ? "#FFE600" : type === "COPY_PASTE" ? "#FF4D00" : CANVAS_BG;
    ctx.lineWidth = 2 / scale;
  }
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.globalAlpha = 1;
}
