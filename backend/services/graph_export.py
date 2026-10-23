"""DETEKTO :: services/graph_export.py — Memgraph-Ready Relation Export

Menghasilkan GraphBatch (nodes/edges), skrip Cypher (MERGE idempoten, literal di-escape), pernyataan berparameter
untuk driver Bolt, dan JSON {nodes, links} kompatibel react-force-graph (identik dengan keluaran fallback NetworkX).
"""
from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from core.config import Settings
from models.interrogation import TargetEntity
from models.swarm import GraphBatch, GraphEdge, GraphNode, PropValue, SyndicateLink, TargetDossier

_GROUP_KINDS = {"group", "channel", "invite"}
_LABEL_RE = re.compile(r"^[A-Za-z]+$")


def account_key(platform: str, username: str) -> str:
    return f"{platform}:{username.lower()}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_graph(
    session_id: str,
    platform: str,
    dossiers: list[TargetDossier],
    phase3_targets: list[TargetEntity],
) -> GraphBatch:
    nodes: dict[tuple[str, str], GraphNode] = {}
    edges: dict[tuple[str, str, str, str], GraphEdge] = {}

    def add_node(label: str, key: str, props: dict[str, PropValue]) -> None:
        existing = nodes.get((label, key))
        if existing:
            existing.props.update({k: v for k, v in props.items() if v is not None})
        else:
            nodes[(label, key)] = GraphNode(label=label, key=key, props=props)  # type: ignore[arg-type]

    def add_edge(etype: str, fl: str, fk: str, tl: str, tk: str, props: dict[str, PropValue]) -> None:
        edges.setdefault((etype, fk, tk, fl + tl), GraphEdge(type=etype, from_label=fl, from_key=fk, to_label=tl, to_key=tk, props=props))  # type: ignore[arg-type]

    p3 = {t.username: t for t in phase3_targets}
    group_members: dict[str, set[str]] = defaultdict(set)

    for d in dossiers:
        me = account_key(d.platform, d.username)
        t3 = p3.get(d.username)
        prof, vis = d.profile, d.vision
        add_node(
            "Account", me,
            {
                "username": d.username, "platform": d.platform, "is_target": True, "state": d.state,
                "follower_count": prof.follower_count if prof else None,
                "following_count": prof.following_count if prof else None,
                "creation_date": prof.account_creation_date if prof else None,
                "username_changes": prof.username_change_count if prof else None,
                "fft_score": vis.profile_photo.score if vis and vis.profile_photo else None,
                "feed_uniformity": vis.feed.cluster_ratio if vis and vis.feed else None,
                "comment_count": t3.comment_count if t3 else None,
                "injection_flag": t3.injection_flag if t3 else None,
            },
        )
        for link in d.syndicate_links:
            _link_edges(add_node, add_edge, d, me, link, group_members)
        for cand in d.candidate_accounts + (d.reverse_image.matches if d.reverse_image else []):
            ck = f"{cand.platform}:{cand.handle.lower()}"
            add_node("Account", ck, {"username": cand.handle, "platform": cand.platform, "is_target": False, "discovered": True, "url": cand.url})
            add_edge("POSSIBLE_ALT", "Account", me, "Account", ck, {"evidence": cand.evidence})
        for cp in d.copy_paste:
            ok = account_key(d.platform, cp.other_username)
            add_node("Account", ok, {"username": cp.other_username, "platform": d.platform, "is_target": cp.other_username in p3})
            add_edge("COPY_PASTE", "Account", me, "Account", ok, {"similarity": cp.similarity, "basis": cp.basis})

    # Relasi antar-target dari Fase 3: akun yang muncul di screenshot yang sama = CO_COMMENTED
    names = sorted(p3)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            shared = sorted(set(p3[a].image_indexes) & set(p3[b].image_indexes))
            if shared:
                add_edge("CO_COMMENTED", "Account", account_key(platform, a), "Account", account_key(platform, b), {"weight": len(shared), "basis": "same_screenshot"})

    # Akun yang menautkan grup yang sama -> SAME_GROUP_LINK (sinyal koordinasi)
    for gkey, members in group_members.items():
        ordered = sorted(members)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                add_edge("SAME_GROUP_LINK", "Account", a, "Account", b, {"group_key": gkey})

    return GraphBatch(session_id=session_id, generated_at=_now(), nodes=list(nodes.values()), edges=list(edges.values()))


def _link_edges(add_node: Any, add_edge: Any, d: TargetDossier, me: str, link: SyndicateLink, group_members: dict[str, set[str]]) -> None:
    if link.kind in _GROUP_KINDS:
        gkey = f"{link.platform}:{link.identifier.lower()}"
        add_node("Group", gkey, {"platform": link.platform, "kind": link.kind, "url": link.url})
        add_edge("LINKS_TO", "Account", me, "Group", gkey, {"source": link.source})
        group_members[gkey].add(me)
    elif link.kind == "profile":
        pkey = f"{link.platform}:{link.identifier.lower()}"
        add_node("Account", pkey, {"username": link.identifier, "platform": link.platform, "is_target": False, "discovered": True, "url": link.url})
        add_edge("PROMOTES_PROFILE", "Account", me, "Account", pkey, {"source": link.source})
    else:
        pkey = f"{link.platform}:{link.identifier.lower()}"
        add_node("Post", pkey, {"platform": link.platform, "url": link.url})
        add_edge("SHARES_POST", "Account", me, "Post", pkey, {"source": link.source})


# -------------------------------------------------------------------- Cypher
def _lit(v: PropValue) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    esc = v.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")
    return f"'{esc}'"


def _map(props: dict[str, PropValue]) -> str:
    return "{" + ", ".join(f"{k}: {_lit(v)}" for k, v in props.items() if _LABEL_RE.match(k.replace('_', 'a'))) + "}"


def to_cypher(batch: GraphBatch) -> str:
    """Skrip Cypher MERGE idempoten (aman dijalankan ulang). Label/tipe dari enum tetap; nilai di-escape."""
    out = [f"// DETEKTO graph batch — session {batch.session_id} — {batch.generated_at}"]
    for label in ("Account", "Group", "Post"):
        out.append(f"CREATE INDEX ON :{label}(key);")
    for n in batch.nodes:
        out.append(f"MERGE (n:{n.label} {{key: {_lit(n.key)}}}) SET n += {_map(n.props)};")
    for e in batch.edges:
        out.append(
            f"MATCH (a:{e.from_label} {{key: {_lit(e.from_key)}}}), (b:{e.to_label} {{key: {_lit(e.to_key)}}}) "
            f"MERGE (a)-[r:{e.type}]->(b) SET r += {_map(e.props)};"
        )
    return "\n".join(out) + "\n"


def to_param_statements(batch: GraphBatch) -> list[tuple[str, dict[str, Any]]]:
    """Versi berparameter (UNWIND) untuk driver Bolt: tanpa interpolasi string data -> kebal Cypher injection."""
    stmts: list[tuple[str, dict[str, Any]]] = []
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for n in batch.nodes:
        by_label[n.label].append({"key": n.key, "props": {k: v for k, v in n.props.items() if v is not None}})
    for label, rows in by_label.items():
        stmts.append((f"UNWIND $rows AS row MERGE (n:{label} {{key: row.key}}) SET n += row.props", {"rows": rows}))
    by_edge: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for e in batch.edges:
        by_edge[(e.type, e.from_label, e.to_label)].append(
            {"from_key": e.from_key, "to_key": e.to_key, "props": {k: v for k, v in e.props.items() if v is not None}}
        )
    for (etype, fl, tl), rows in by_edge.items():
        stmts.append(
            (
                f"UNWIND $rows AS row MATCH (a:{fl} {{key: row.from_key}}) MATCH (b:{tl} {{key: row.to_key}}) "
                f"MERGE (a)-[r:{etype}]->(b) SET r += row.props",
                {"rows": rows},
            )
        )
    return stmts


def to_force_graph(batch: GraphBatch) -> dict[str, list[dict[str, PropValue]]]:
    """{nodes, links} untuk react-force-graph-2d; format sama persis dengan keluaran fallback NetworkX."""
    nodes: list[dict[str, PropValue]] = [
        {"id": n.key, "group": n.label, "name": str(n.props.get("username") or n.key), **{k: v for k, v in n.props.items() if k != "username"}}
        for n in batch.nodes
    ]
    links: list[dict[str, PropValue]] = [{"source": e.from_key, "target": e.to_key, "type": e.type, **e.props} for e in batch.edges]
    return {"nodes": nodes, "links": links}


async def push_to_memgraph(batch: GraphBatch, s: Settings) -> bool:
    """Tulis batch ke Memgraph via Bolt. False bila driver/kontainer tidak tersedia (-> mode NetworkX)."""
    try:
        from neo4j import AsyncGraphDatabase
    except ImportError:
        return False
    driver = AsyncGraphDatabase.driver(f"bolt://{s.memgraph_host}:{s.memgraph_port}", auth=None, encrypted=False, connection_timeout=3.0)
    try:
        async with driver.session() as session:
            for label in ("Account", "Group", "Post"):
                try:
                    await session.run(f"CREATE INDEX ON :{label}(key)")
                except Exception:
                    continue  # indeks sudah ada
            for query, params in to_param_statements(batch):
                await asyncio.wait_for((await session.run(query, params)).consume(), timeout=10)
        return True
    except Exception:
        return False
    finally:
        await driver.close()
