"""DETEKTO :: services/graph_mapper.py — Network Graph & Centrality Engine (Task 6.1)

Menggabungkan GraphBatch (Fase 4: Account/Group/Post + LINKS_TO/SAME_GROUP_LINK/COPY_PASTE/POSSIBLE_ALT/...) dengan VerdictSet (Fase 5),
menghitung sentralitas (PageRank + Degree + Betweenness) di NetworkX, menunjuk "Patient Zero" (kandidat pusat jaringan), lalu —bila Memgraph hidup—
menulis balik properti vonis & sentralitas serta edge AMPLIFIES. Memgraph mati => seluruh hasil tetap utuh lewat NetworkX (JSON identik).
"""
from __future__ import annotations

import math
import random
from collections import Counter
from dataclasses import dataclass

import networkx as nx

from core.config import get_settings
from models.graph import GraphMap, GraphMapLink, GraphMapNode, GraphStats, PatientZero
from models.swarm import GraphBatch, GraphEdge, GraphNode, PropValue
from models.verdict import VerdictSet
from services.graph_export import push_to_memgraph

EDGE_WEIGHTS: dict[str, float] = {
    "SAME_GROUP_LINK": 2.0, "COPY_PASTE": 2.0, "POSSIBLE_ALT": 1.5, "LINKS_TO": 1.5,
    "CO_COMMENTED": 1.0, "PROMOTES_PROFILE": 1.0, "SHARES_POST": 0.5,
}
MAX_PATH_HOPS = 4
MAX_PATHS = 400
BETWEENNESS_NODE_LIMIT = 600
MIN_CONNECTED_BUZZERS = 2


@dataclass(frozen=True)
class VerdictInfo:
    verdict: str
    buzzer_type: str
    score: float
    verdict_id: str


def verdict_lookup(vs: VerdictSet | None) -> dict[tuple[str, str], VerdictInfo]:
    if vs is None:
        return {}
    return {(c.platform, c.username.lower()): VerdictInfo(c.verdict, c.buzzer_type, c.score, c.verdict_id) for c in vs.cards}


def _kind(node: GraphNode, info: VerdictInfo | None) -> str:
    if node.label == "Group":
        return "group"
    if node.label == "Post":
        return "post"
    if info is not None:
        return "organic" if info.verdict == "ORGANIC" else ("buzzer_a" if info.buzzer_type == "A" else "buzzer_b")
    return "target" if node.props.get("is_target") else "discovered"


def _weighted_graph(batch: GraphBatch) -> nx.Graph:
    g: nx.Graph = nx.Graph()
    for n in batch.nodes:
        g.add_node(n.key)
    for e in batch.edges:
        if e.from_key == e.to_key:
            continue
        w = EDGE_WEIGHTS.get(e.type, 1.0)
        if e.type == "COPY_PASTE" and isinstance(e.props.get("similarity"), (int, float)):
            w *= max(0.5, float(e.props["similarity"]))
        if e.type == "CO_COMMENTED" and isinstance(e.props.get("weight"), (int, float)):
            w *= min(3.0, float(e.props["weight"]))
        if g.has_edge(e.from_key, e.to_key):
            g[e.from_key][e.to_key]["weight"] += w
        else:
            g.add_edge(e.from_key, e.to_key, weight=w)
    return g


def _centrality(g: nx.Graph) -> tuple[dict[str, float], dict[str, float]]:
    """Kembalikan (skor_gabungan_0..1, pagerank). Gabungan = 0.5 PageRank + 0.3 Degree + 0.2 Betweenness (masing-masing dinormalkan ke maks)."""
    if g.number_of_nodes() == 0:
        return {}, {}
    pr = nx.pagerank(g, alpha=0.85, weight="weight", max_iter=200, tol=1e-8) if g.number_of_edges() else {n: 1.0 / g.number_of_nodes() for n in g}
    deg = nx.degree_centrality(g) if g.number_of_nodes() > 1 else {n: 0.0 for n in g}
    if g.number_of_nodes() <= BETWEENNESS_NODE_LIMIT and g.number_of_edges():
        bet = nx.betweenness_centrality(g, weight=None, normalized=True)
    else:
        bet = {n: 0.0 for n in g}

    def norm(d: dict[str, float]) -> dict[str, float]:
        m = max(d.values()) or 1.0
        return {k: v / m for k, v in d.items()}

    p, d, b = norm(pr), norm(deg), norm(bet)
    return {n: round(0.5 * p[n] + 0.3 * d[n] + 0.2 * b[n], 6) for n in g}, pr


def build_graph_map(batch: GraphBatch, lookup: dict[tuple[str, str], VerdictInfo], mode: str) -> GraphMap:
    g = _weighted_graph(batch)
    score, pagerank = _centrality(g)
    by_key = {n.key: n for n in batch.nodes}

    def info_of(n: GraphNode) -> VerdictInfo | None:
        if n.label != "Account":
            return None
        return lookup.get((str(n.props.get("platform", "")), str(n.props.get("username", "")).lower()))

    infos = {k: info_of(n) for k, n in by_key.items()}
    kinds = {k: _kind(n, infos[k]) for k, n in by_key.items()}

    # --- Patient Zero: kandidat pusat jaringan (bukan akun organik), wajib terhubung <= 4 langkah ke >= 2 akun buzzer.
    # Aturan anti-tuduhan-sewenang-wenang: (1) hub GRUP koordinasi diutamakan bila skornya >= 50% skor teratas atau akun teratas tidak unggul jelas;
    # (2) sebuah AKUN hanya ditunjuk bila unggul >= 5% atas akun lain (pada jaringan simetris tidak ada pusat tunggal => None).
    buzzer_ids = {k for k, kd in kinds.items() if kd in ("buzzer_a", "buzzer_b")}
    ranked = [k for k in sorted(score, key=lambda k: (-score[k], k)) if by_key[k].label != "Post" and kinds[k] != "organic" and g.degree(k) >= 2]
    valid: list[tuple[str, int]] = []
    for key in ranked[:12]:
        reach = nx.single_source_shortest_path_length(g, key, cutoff=MAX_PATH_HOPS)
        n_buzz = len([b for b in buzzer_ids if b != key and b in reach])
        if n_buzz >= MIN_CONNECTED_BUZZERS:
            valid.append((key, n_buzz))
    pz_id: str | None = None
    connected = 0
    if valid:
        top, top_n = valid[0]
        best_group = next(((k, n) for k, n in valid if by_key[k].label == "Group"), None)
        if by_key[top].label == "Group":
            pz_id, connected = top, top_n
        else:
            second = next((k for k, _ in valid[1:] if by_key[k].label == "Account"), None)
            clear_lead = second is None or score[top] >= 1.05 * score[second]
            if best_group and (score[best_group[0]] >= 0.5 * score[top] or not clear_lead):
                pz_id, connected = best_group
            elif clear_lead:
                pz_id, connected = top, top_n

    dist: dict[str, int] = nx.single_source_shortest_path_length(g, pz_id) if pz_id else {}
    paths: dict[str, list[str]] = {}
    amplifies: list[GraphMapLink] = []
    if pz_id:
        for node in sorted(dist, key=lambda k: (dist[k], k)):
            if node == pz_id or dist[node] > MAX_PATH_HOPS or len(paths) >= MAX_PATHS:
                continue
            paths[node] = nx.shortest_path(g, node, pz_id)
            if node in buzzer_ids:
                amplifies.append(GraphMapLink(source=node, target=pz_id, type="AMPLIFIES", weight=round(1.0 / dist[node], 3)))

    nodes: list[GraphMapNode] = []
    for key, n in by_key.items():
        info = infos[key]
        nodes.append(
            GraphMapNode(
                id=key, label=n.label, name=str(n.props.get("username") or n.props.get("url") or key)[:80], kind=kinds[key],  # type: ignore[arg-type]
                platform=str(n.props.get("platform", ""))[:20],
                verdict=info.verdict if info else None, buzzer_type=info.buzzer_type if info else None,  # type: ignore[arg-type]
                score=info.score if info else None, verdict_id=info.verdict_id if info else None,
                centrality=score.get(key, 0.0), pagerank=round(pagerank.get(key, 0.0), 6), degree=int(g.degree(key)),
                is_patient_zero=key == pz_id, distance_to_pz=dist.get(key) if pz_id else None,
            )
        )

    links = [GraphMapLink(source=e.from_key, target=e.to_key, type=e.type, weight=round(EDGE_WEIGHTS.get(e.type, 1.0), 3)) for e in batch.edges] + amplifies  # type: ignore[arg-type]

    pz: PatientZero | None = None
    if pz_id:
        node = by_key[pz_id]
        is_group = node.label == "Group"
        boss: str | None = None
        if is_group:
            accounts = [k for k in g.neighbors(pz_id) if by_key[k].label == "Account" and kinds[k] != "organic"]
            boss = max(accounts, key=lambda k: (score[k], k), default=None)
        pz = PatientZero(
            id=pz_id, name=str(node.props.get("url") or node.props.get("username") or pz_id)[:80], node_type="group" if is_group else "account",
            centrality=score[pz_id], degree=int(g.degree(pz_id)), connected_buzzers=connected,
            reason=(
                f"Skor sentralitas tertinggi ({score[pz_id]:.2f}; PageRank {pagerank[pz_id]:.3f}, derajat {g.degree(pz_id)}), "
                f"terhubung dalam ≤{MAX_PATH_HOPS} langkah ke {connected} akun berstempel BUZZER"
                + (" — simpul ini adalah GRUP koordinasi (hub), bukan akun perorangan." if is_group else ".")
            ),
            boss_account_candidate=boss,
        )

    counts = Counter(kinds.values())
    return GraphMap(
        session_id=batch.session_id, mode=mode, nodes=nodes, links=links, patient_zero=pz, paths=paths,  # type: ignore[arg-type]
        stats=GraphStats(
            nodes=len(nodes), edges=len(links), buzzers=counts["buzzer_a"] + counts["buzzer_b"], organics=counts["organic"], groups=counts["group"],
            algorithm="networkx:0.5*pagerank+0.3*degree+0.2*betweenness",
        ),
    )


def enrich_batch(batch: GraphBatch, gm: GraphMap) -> GraphBatch:
    """Salinan batch + properti vonis/sentralitas pada node Account & edge AMPLIFIES — siap di-MERGE ke Memgraph."""
    meta = {n.id: n for n in gm.nodes}
    nodes: list[GraphNode] = []
    for n in batch.nodes:
        m = meta[n.key]
        props: dict[str, PropValue] = {**n.props, "centrality": m.centrality, "pagerank": m.pagerank, "degree": m.degree, "kind": m.kind, "is_patient_zero": m.is_patient_zero}
        if m.verdict:
            props.update({"verdict": m.verdict, "buzzer_type": m.buzzer_type, "verdict_score": m.score})
        nodes.append(GraphNode(label=n.label, key=n.key, props=props))
    extra = [
        GraphEdge(type="AMPLIFIES", from_label="Account", from_key=l.source, to_label=gm.patient_zero.node_type.capitalize() if gm.patient_zero else "Account", to_key=l.target, props={"weight": l.weight})  # type: ignore[arg-type]
        for l in gm.links if l.type == "AMPLIFIES"
    ]
    return GraphBatch(session_id=batch.session_id, generated_at=batch.generated_at, nodes=nodes, edges=[*batch.edges, *extra])


async def sync_to_memgraph(batch: GraphBatch, gm: GraphMap) -> str:
    """Dorong batch yang sudah diperkaya ke Memgraph. Kembalikan mode aktual: 'memgraph' | 'networkx' (fallback otomatis)."""
    return "memgraph" if await push_to_memgraph(enrich_batch(batch, gm), get_settings()) else "networkx"


# --------------------------------------------------------- generator uji beban
def stress_batch(n_nodes: int, seed: int) -> tuple[GraphBatch, dict[tuple[str, str], VerdictInfo]]:
    """Jaringan sintetis deterministik (Phantom A: 150+ node). Hub grup + akun buzzer/organik + akun temuan + post."""
    rng = random.Random(seed)
    n_nodes = max(20, min(n_nodes, 1000))
    n_groups, n_posts = max(3, n_nodes // 25), max(2, n_nodes // 20)
    n_acc = n_nodes - n_groups - n_posts
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    lookup: dict[tuple[str, str], VerdictInfo] = {}
    groups = [f"telegram:hub{i:02d}" for i in range(n_groups)]
    for i, gk in enumerate(groups):
        nodes.append(GraphNode(label="Group", key=gk, props={"platform": "telegram", "kind": "invite", "url": f"https://t.me/+HUB{i:02d}"}))
    accounts = [f"instagram:akun_{i:04d}" for i in range(n_acc)]
    for i, ak in enumerate(accounts):
        uname = ak.split(":")[1]
        target = i < n_acc * 0.6
        nodes.append(GraphNode(label="Account", key=ak, props={"username": uname, "platform": "instagram", "is_target": target}))
        if target:
            buzz = rng.random() < 0.6
            lookup[("instagram", uname)] = VerdictInfo("BUZZER" if buzz else "ORGANIC", rng.choice("AB") if buzz else "C", round(rng.uniform(65, 99) if buzz else rng.uniform(5, 60), 1), f"{i:032x}")
    posts = [f"instagram:post{i:03d}" for i in range(n_posts)]
    nodes.extend(GraphNode(label="Post", key=p, props={"platform": "instagram", "url": f"https://www.instagram.com/p/POST{i:03d}/"}) for i, p in enumerate(posts))
    for ak in accounts:
        uname = ak.split(":")[1]
        v = lookup.get(("instagram", uname))
        if v and v.verdict == "BUZZER":
            gk = groups[0] if rng.random() < 0.6 else rng.choice(groups)   # hub utama = groups[0] (Patient Zero)
            edges.append(GraphEdge(type="LINKS_TO", from_label="Account", from_key=ak, to_label="Group", to_key=gk, props={}))
        elif rng.random() < 0.15:
            edges.append(GraphEdge(type="LINKS_TO", from_label="Account", from_key=ak, to_label="Group", to_key=rng.choice(groups), props={}))
        if rng.random() < 0.25:
            edges.append(GraphEdge(type="SHARES_POST", from_label="Account", from_key=ak, to_label="Post", to_key=rng.choice(posts), props={}))
    for _ in range(int(n_acc * 0.5)):
        a, b = rng.sample(accounts, 2)
        etype = rng.choice(("CO_COMMENTED", "COPY_PASTE", "SAME_GROUP_LINK", "POSSIBLE_ALT"))
        props: dict[str, PropValue] = {"similarity": round(rng.uniform(0.75, 1.0), 2)} if etype == "COPY_PASTE" else {}
        edges.append(GraphEdge(type=etype, from_label="Account", from_key=a, to_label="Account", to_key=b, props=props))  # type: ignore[arg-type]
    return GraphBatch(session_id="0" * 32, generated_at="stress", nodes=nodes, edges=edges), lookup
