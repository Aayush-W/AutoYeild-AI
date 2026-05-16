import pytest

from src.batch.region_mapper import assign_region, get_grid_coords
from src.batch.aggregation import aggregate_results

def test_region_mapper():
    # Test coordinates for a 16-image batch
    x, y = get_grid_coords(0, 16)
    assert x == 0 and y == 0
    
    x, y = get_grid_coords(15, 16)
    assert x == 3 and y == 3
    
    # Test region assignment mapping for 16 instances
    region_0 = assign_region(0, 16)
    assert region_0 == "rim"  # Corners are typically rim
    
    # Center
    region_center = assign_region(5, 16)
    assert region_center in ["center", "mid"]


def test_aggregation_with_mixed_results():
    results = [
        {"index": 0, "filename": "1.jpg", "region": "center", "label": "clean", "confidence": 0.9, "x": 0, "y": 0, "severity_score": 0.1},
        {"index": 1, "filename": "2.jpg", "region": "center", "label": "scratch", "confidence": 0.8, "x": 1, "y": 0, "severity_score": 0.2},
        {"index": 2, "filename": "3.jpg", "region": "rim", "label": "clean", "confidence": 0.95, "x": 2, "y": 0, "severity_score": 0.05},
        {"index": 3, "filename": "4.jpg", "region": "rim", "label": "particle", "confidence": 0.85, "x": 3, "y": 0, "severity_score": 0.15},
    ]
    
    agg = aggregate_results(results)
    
    assert "region_stats" in agg
    assert "insights" in agg
    
    insights = agg["insights"]
    assert insights["total_images"] == 4
    assert insights["defect_rate"] == 0.5   # 2 defects out of 4
    assert insights["clean_rate"] == 0.5    # 2 clean out of 4
    assert insights["worst_region"] in ["center", "rim"]
    
    # Region stats checks
    stats = {s["region"]: s for s in agg["region_stats"]}
    assert stats["center"]["total"] == 2
    assert stats["center"]["defect_density"] == 0.5
    assert stats["center"]["dominant_defect"] in ["clean", "scratch"]

def test_aggregation_with_empty_results():
    # Should handle empty gracefully
    agg = aggregate_results([])
    insights = agg["insights"]
    assert insights["total_images"] == 0
    assert insights["clean_rate"] == 0.0
    assert insights["defect_rate"] == 0.0
