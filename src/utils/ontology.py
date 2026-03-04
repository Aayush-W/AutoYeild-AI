"""
Centralized defect ontology for AutoYield-AI.

Provides a single source of truth for:
- Canonical (snake_case) defect class names
- Alias mapping from raw model outputs → canonical names
- A normalize_class() helper used by root-cause agent, eval script, etc.

Adding a new defect class:
1. Add the canonical snake_case name to CANONICAL_CLASSES.
2. Add all expected raw label variants to ALIAS_MAP.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Canonical class list  (snake_case, all lower)
# ---------------------------------------------------------------------------
CANONICAL_CLASSES: list[str] = [
    "center",
    "donut",
    "edge_loc",
    "edge_ring",
    "local",
    "near_full",
    "none",          # clean / no defect
    "random",
    "scratch",
    "clean",         # alias kept for legacy labels
]

# ---------------------------------------------------------------------------
# Alias map  raw_label (lowercased, stripped) → canonical
# ---------------------------------------------------------------------------
# Keys must be: label.lower().strip() forms — spaces, hyphens, etc.
ALIAS_MAP: dict[str, str] = {
    # center
    "center": "center",
    "centre": "center",
    # donut
    "donut": "donut",
    "doughnut": "donut",
    # edge_loc / edge-loc
    "edge_loc": "edge_loc",
    "edge loc": "edge_loc",
    "edgeloc": "edge_loc",
    "edge-loc": "edge_loc",
    # edge_ring / edge ring / edge-ring
    "edge_ring": "edge_ring",
    "edge ring": "edge_ring",
    "edgering": "edge_ring",
    "edge-ring": "edge_ring",
    # local
    "local": "local",
    # near_full
    "near_full": "near_full",
    "near full": "near_full",
    "nearfull": "near_full",
    "near-full": "near_full",
    # none / clean
    "none": "none",
    "clean": "clean",
    "no defect": "clean",
    "normal": "clean",
    # random
    "random": "random",
    # scratch
    "scratch": "scratch",
    "scratches": "scratch",
}


def normalize_class(label: str) -> str:
    """
    Return the canonical snake_case class name for *label*.

    Steps:
    1. Lowercase + strip whitespace.
    2. Look up in ALIAS_MAP.
    3. If not found, replace spaces with underscores and return as-is
       (graceful degradation for future / unseen classes).

    Examples
    --------
    >>> normalize_class("Edge ring")
    'edge_ring'
    >>> normalize_class("Center")
    'center'
    >>> normalize_class("Local")
    'local'
    >>> normalize_class("Edge Ring")
    'edge_ring'
    """
    normalized = label.lower().strip()
    if normalized in ALIAS_MAP:
        return ALIAS_MAP[normalized]
    # Fallback: replace spaces with underscores
    return normalized.replace(" ", "_").replace("-", "_")
