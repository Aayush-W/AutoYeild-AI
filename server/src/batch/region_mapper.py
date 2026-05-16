"""
region_mapper.py — Grid-based simulated spatial region assignment.
Maps batch image indices to wafer regions without requiring physical coordinates.
"""
from __future__ import annotations
from math import ceil, sqrt


REGION_THRESHOLDS = [
    (0.25, "center"),
    (0.50, "mid"),
    (0.75, "edge_inner"),
    (0.90, "edge_outer"),
    (float("inf"), "rim"),
]


def assign_region(index: int, total_images: int) -> str:
    """
    Assign a simulated wafer region to an image by its batch index.

    Uses a square grid layout; normalised radial distance from the grid centre
    determines the region band.
    """
    grid_size = max(1, ceil(sqrt(total_images)))
    x = index % grid_size
    y = index // grid_size

    center_x = (grid_size - 1) / 2.0
    center_y = (grid_size - 1) / 2.0

    if grid_size <= 1:
        return "center"

    r = sqrt((x - center_x) ** 2 + (y - center_y) ** 2) / (grid_size / 2.0)

    for threshold, region in REGION_THRESHOLDS:
        if r < threshold:
            return region
    return "rim"


def get_grid_coords(index: int, total_images: int) -> tuple[int, int]:
    """Return (x, y) grid cell coordinates for an image index."""
    grid_size = max(1, ceil(sqrt(total_images)))
    return index % grid_size, index // grid_size


def all_regions() -> list[str]:
    return ["center", "mid", "edge_inner", "edge_outer", "rim"]
