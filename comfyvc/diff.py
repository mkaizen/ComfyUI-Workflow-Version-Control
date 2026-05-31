from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .models import Snapshot


@dataclass
class NodeChange:
    node_id: int
    node_type: str
    changes: Dict[str, Tuple[Any, Any]]  # field -> (before, after)


@dataclass
class DiffResult:
    snapshot_a: Snapshot
    snapshot_b: Snapshot
    added_nodes: List[dict] = field(default_factory=list)
    removed_nodes: List[dict] = field(default_factory=list)
    modified_nodes: List[NodeChange] = field(default_factory=list)
    added_links: List = field(default_factory=list)
    removed_links: List = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added_nodes or self.removed_nodes
            or self.modified_nodes or self.added_links or self.removed_links
        )

    @property
    def summary(self) -> str:
        parts = []
        if self.added_nodes:
            parts.append(f"+{len(self.added_nodes)} node{'s' if len(self.added_nodes) != 1 else ''}")
        if self.removed_nodes:
            parts.append(f"-{len(self.removed_nodes)} node{'s' if len(self.removed_nodes) != 1 else ''}")
        if self.modified_nodes:
            parts.append(f"~{len(self.modified_nodes)} modified")
        if self.added_links:
            parts.append(f"+{len(self.added_links)} link{'s' if len(self.added_links) != 1 else ''}")
        if self.removed_links:
            parts.append(f"-{len(self.removed_links)} link{'s' if len(self.removed_links) != 1 else ''}")
        return ", ".join(parts) if parts else "Identical"


def diff_snapshots(a: Snapshot, b: Snapshot) -> DiffResult:
    result = DiffResult(snapshot_a=a, snapshot_b=b)

    nodes_a = _index_nodes(a.workflow)
    nodes_b = _index_nodes(b.workflow)
    ids_a = set(nodes_a)
    ids_b = set(nodes_b)

    result.added_nodes = [nodes_b[i] for i in ids_b - ids_a]
    result.removed_nodes = [nodes_a[i] for i in ids_a - ids_b]

    for nid in ids_a & ids_b:
        changes = _diff_node(nodes_a[nid], nodes_b[nid])
        if changes:
            result.modified_nodes.append(
                NodeChange(
                    node_id=nid,
                    node_type=nodes_b[nid].get("type", "Unknown"),
                    changes=changes,
                )
            )

    links_a = {_link_key(l): l for l in a.workflow.get("links", [])}
    links_b = {_link_key(l): l for l in b.workflow.get("links", [])}
    result.added_links = [links_b[k] for k in set(links_b) - set(links_a)]
    result.removed_links = [links_a[k] for k in set(links_a) - set(links_b)]

    return result


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _index_nodes(workflow: dict) -> Dict[int, dict]:
    return {n.get("id", i): n for i, n in enumerate(workflow.get("nodes", []))}


def _link_key(link) -> str:
    if isinstance(link, list) and len(link) >= 5:
        return f"{link[1]}:{link[2]}->{link[3]}:{link[4]}"
    return str(link)


def _diff_node(a: dict, b: dict) -> Dict[str, Tuple[Any, Any]]:
    SKIP = {"id"}
    changes = {}
    for key in (set(a) | set(b)) - SKIP:
        va, vb = a.get(key), b.get(key)
        if va != vb:
            changes[key] = (va, vb)
    return changes
