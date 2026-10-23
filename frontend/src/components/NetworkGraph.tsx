"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { BrutalButton } from "@/components/BrutalButton";
import type { GraphMap, GraphMapNode, NodeKind } from "@/lib/types";

// react-force-graph-2d menyentuh window/canvas saat import -> WAJIB client-only (aman untuk SSR Next.js & static export Tauri).
const ForceGraphCanvas = dynamic(() => import("@/components/ForceGraphCanvas"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[560px] items-center justify-center border-4 border-ink bg-ink font-mono text-sm font-bold uppercase text-acid">MEMUAT KANVAS GRAF...</div>
  ),
});

const LEGEND: ReadonlyArray<{ kind: NodeKind | "pz"; label: string; color: string }> = [
  { kind: "buzzer_a", label: "BUZZER TYPE A/B", color: "bg-crimson" },
  { kind: "organic", label: "ORGANIC (C)", color: "bg-emerald" },
  { kind: "group", label: "GRUP / TAUTAN SINDIKAT", color: "bg-acid" },
  { kind: "discovered", label: "AKUN TEMUAN", color: "bg-magenta" },
  { kind: "target", label: "TARGET BELUM DINILAI", color: "bg-hazard" },
  { kind: "post", label: "POST", color: "bg-canvas" },
];

const edgeKey = (a: string, b: string): string => (a < b ? `${a}|${b}` : `${b}|${a}`);

export function NetworkGraph({ map }: { map: GraphMap }) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(900);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusToken, setFocusToken] = useState(0);
  const [show, setShow] = useState({ group: true, organic: true, discovered: true, post: true });

  useEffect(() => {
    const el = boxRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => {
      if (e) setWidth(Math.max(320, Math.floor(e.contentRect.width)));
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const { nodes, links } = useMemo(() => {
    const keep = (n: GraphMapNode): boolean =>
      n.is_patient_zero ||
      (n.kind === "group" ? show.group : n.kind === "organic" ? show.organic : n.kind === "discovered" ? show.discovered : n.kind === "post" ? show.post : true);
    const ns = map.nodes.filter(keep);
    const ids = new Set(ns.map((n) => n.id));
    return { nodes: ns, links: map.links.filter((l) => ids.has(l.source) && ids.has(l.target)) };
  }, [map, show]);

  const selected = useMemo(() => map.nodes.find((n) => n.id === selectedId) ?? null, [map, selectedId]);
  const path = selectedId ? map.paths[selectedId] : undefined;

  const { highlightIds, pathEdges } = useMemo(() => {
    const ids = new Set<string>();
    const edges = new Set<string>();
    if (selectedId) {
      ids.add(selectedId);
      if (path) {
        path.forEach((id) => ids.add(id));
        for (let i = 0; i + 1 < path.length; i++) {
          const a = path[i];
          const b = path[i + 1];
          if (a !== undefined && b !== undefined) edges.add(edgeKey(a, b));
        }
      }
    }
    return { highlightIds: ids, pathEdges: edges };
  }, [selectedId, path]);

  const nameOf = (id: string): string => map.nodes.find((n) => n.id === id)?.name ?? id;
  const pz = map.patient_zero;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-4 border-ink bg-canvas p-3 font-mono text-[11px] font-bold uppercase">
        {LEGEND.map((l) => (
          <span key={l.kind} className="flex items-center gap-1">
            <span className={`inline-block h-4 w-4 rounded-none border-2 border-ink ${l.color}`} />
            {l.label}
          </span>
        ))}
        <span className="flex items-center gap-1">
          <span className="inline-block h-4 w-4 rounded-none border-4 border-hazard bg-canvas" />
          PATIENT ZERO
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-1 w-6 border-t-4 border-dashed border-magenta" />
          AMPLIFIES / JALUR
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-4 font-mono text-xs font-bold uppercase">
        {(["group", "organic", "discovered", "post"] as const).map((k) => (
          <label key={k} className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              className="h-5 w-5 rounded-none border-4 border-ink accent-ink"
              checked={show[k]}
              onChange={(e) => setShow((s) => ({ ...s, [k]: e.target.checked }))}
            />
            {k}
          </label>
        ))}
        <BrutalButton size="sm" tone="acid" onClick={() => setFocusToken((t) => t + 1)}>
          FIT VIEW
        </BrutalButton>
        {pz && (
          <BrutalButton
            size="sm"
            tone="hazard"
            onClick={() => {
              setSelectedId(pz.id);
              setFocusToken((t) => t + 1);
            }}
          >
            FOKUS PATIENT ZERO
          </BrutalButton>
        )}
        <span className="rounded-none border-4 border-ink bg-ink px-2 py-1 text-acid">
          {nodes.length}/{map.nodes.length} NODE · {links.length} EDGE
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div ref={boxRef} className="overflow-hidden rounded-none border-8 border-ink bg-ink shadow-brutal">
          <ForceGraphCanvas
            nodes={nodes}
            links={links}
            width={width}
            height={560}
            selectedId={selectedId}
            highlightIds={highlightIds}
            pathEdges={pathEdges}
            onSelect={setSelectedId}
            focusToken={focusToken}
            focusId={selectedId}
          />
        </div>

        <aside className="flex flex-col gap-3 rounded-none border-8 border-ink bg-canvas p-3 shadow-brutal" aria-live="polite">
          <h4 className="font-display text-xl font-bold uppercase">DETAIL NODE</h4>
          {selected ? (
            <div className="flex flex-col gap-2 font-mono text-xs font-bold">
              <p className="break-all font-display text-lg leading-tight">{selected.name}</p>
              <p className="uppercase">
                {selected.label} · {selected.kind.replace("_", " ")} {selected.platform ? `· ${selected.platform}` : ""}
              </p>
              {selected.verdict && (
                <p className={`border-4 border-ink p-1 uppercase ${selected.verdict === "BUZZER" ? "bg-crimson text-canvas" : "bg-emerald"}`}>
                  {selected.verdict} TYPE {selected.buzzer_type} · SKOR {selected.score?.toFixed(1)}%
                </p>
              )}
              <p className="uppercase">
                SENTRALITAS {selected.centrality.toFixed(2)} · PAGERANK {selected.pagerank.toFixed(3)} · DERAJAT {selected.degree}
              </p>
              {selected.is_patient_zero && <p className="border-4 border-ink bg-hazard p-1 uppercase">KANDIDAT PUSAT JARINGAN (PATIENT ZERO)</p>}
              {path && path.length > 1 && (
                <p className="break-words border-4 border-ink bg-white p-1 uppercase">JALUR → PATIENT ZERO: {path.map(nameOf).join(" → ")}</p>
              )}
              <BrutalButton size="sm" tone="canvas" onClick={() => setSelectedId(null)}>
                LEPAS PILIHAN
              </BrutalButton>
            </div>
          ) : (
            <p className="font-mono text-xs font-bold uppercase">KLIK NODE UNTUK MELIHAT DETAIL & JALUR BENANG MERAH KE PATIENT ZERO.</p>
          )}
        </aside>
      </div>
    </div>
  );
}
