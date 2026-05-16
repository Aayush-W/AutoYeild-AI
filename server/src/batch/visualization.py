"""
visualization.py — Wafer-map payload generation for 2D and pseudo-3D views.

Produces a normalized grid structure that the frontend renders as a 2D heat map
or as stacked pseudo-3D bars (no extra frontend dependencies required).
"""
from __future__ import annotations

import io
from math import ceil, sqrt
from typing import Any, Dict, List

from PIL import Image

from .region_mapper import get_grid_coords

# ── Colour / severity mapping ────────────────────────────────────────────────
SEVERITY_MAP = {
    "center":     {"color": "#6366f1", "severity": "critical"},
    "mid":        {"color": "#f59e0b", "severity": "high"},
    "edge_inner": {"color": "#f97316", "severity": "medium"},
    "edge_outer": {"color": "#ef4444", "severity": "high"},
    "rim":        {"color": "#dc2626", "severity": "critical"},
}

DEFECT_COLORS = {
    "center":    "#6366f1",
    "donut":     "#a855f7",
    "edge loc":  "#f97316",
    "edge ring": "#ef4444",
    "local":     "#f59e0b",
    "near full": "#dc2626",
    "particle":  "#ec4899",
    "random":    "#14b8a6",
    "scratch":   "#f43f5e",
    "clean":     "#22c55e",
    "other / unknown": "#6b7280",
}

COMPOSITE_TILE_SIZE = 128


def _label_color(label: str) -> str:
    return DEFECT_COLORS.get(label.strip().lower(), "#6b7280")


def build_visualization(
    results: List[Dict[str, Any]],
    region_stats: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the full visualization payload.

    Returns:
        grid_points  — per-image points for scatter/grid rendering
        region_map   — region-level summary for heat-map overlay
        legend       — colour legend for the frontend
        grid_size    — square grid dimension
    """
    total = len(results)
    grid_size = max(1, ceil(sqrt(total)))

    # Build region-density lookup
    density_by_region: Dict[str, float] = {
        s["region"]: s["defect_density"] for s in region_stats
    }

    grid_points: List[Dict[str, Any]] = []
    for r in results:
        x, y = get_grid_coords(r["index"], total)
        region = r["region"]
        density = density_by_region.get(region, 0.0)
        x_norm = round((x / (grid_size - 1)) if grid_size > 1 else 0.0, 4)
        y_norm = round((y / (grid_size - 1)) if grid_size > 1 else 0.0, 4)
        grid_points.append(
            {
                "index": r["index"],
                "filename": r.get("filename", ""),
                "x": x,
                "y": y,
                "x_norm": x_norm,
                "y_norm": y_norm,
                "z": round(density, 4),          # pseudo-3D height
                "density": round(density, 4),
                "region": region,
                "label": r["label"],
                "defect": r["label"],
                "confidence": round(r["confidence"], 4),
                "image_data_uri": r.get("image_data_uri"),
                "heatmap_image_data_uri": r.get("heatmap_image_data_uri"),
                "color": _label_color(r["label"]),
                "severity": SEVERITY_MAP.get(region, {}).get("severity", "medium"),
            }
        )

    # Region-level summary for heat map overlay
    region_map: List[Dict[str, Any]] = []
    for stat in region_stats:
        region = stat["region"]
        meta = SEVERITY_MAP.get(region, {"color": "#6b7280", "severity": "medium"})
        region_map.append(
            {
                "region": region,
                "defect_density": stat["defect_density"],
                "dominant_defect": stat["dominant_defect"],
                "avg_confidence": stat["avg_confidence"],
                "total": stat["total"],
                "color": meta["color"],
                "severity": meta["severity"],
            }
        )

    legend = [
        {"label": label.title(), "color": color}
        for label, color in DEFECT_COLORS.items()
    ]

    return {
        "grid_points": grid_points,
        "region_map": region_map,
        "legend": legend,
        "grid_size": grid_size,
        "total_images": total,
    }


def build_composite_grid_image(
    named_images: List[tuple[str, bytes]],
    tile_size: int = COMPOSITE_TILE_SIZE,
) -> tuple[bytes, int]:
    """
    Build a square wafer-grid composite image from uploaded batch images.

    Returns:
        (png_bytes, grid_size)
    """
    total = len(named_images)
    grid_size = max(1, ceil(sqrt(total)))
    canvas_size = grid_size * tile_size

    canvas = Image.new("RGB", (canvas_size, canvas_size), color=(18, 18, 18))
    fallback_tile = Image.new("RGB", (tile_size, tile_size), color=(42, 42, 42))

    for index, (_name, image_bytes) in enumerate(named_images):
        x, y = get_grid_coords(index, total)
        pos = (x * tile_size, y * tile_size)
        try:
            with Image.open(io.BytesIO(image_bytes)) as img:
                tile = img.convert("RGB").resize((tile_size, tile_size))
        except Exception:
            tile = fallback_tile
        canvas.paste(tile, pos)

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue(), grid_size
