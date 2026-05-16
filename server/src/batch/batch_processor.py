"""
batch_processor.py — Async job orchestration for batch wafer inspections.

Public API:
    start_batch_job(image_files, include_visualization, enable_genai) -> job_id
    get_batch_job(job_id) -> BatchJobState dict or None
"""
from __future__ import annotations

import asyncio
import base64
import io
import os
import statistics
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict

from PIL import Image

from .aggregation import aggregate_results
from .recommendation_engine import generate_recommendations
from .region_mapper import assign_region, get_grid_coords
from .visualization import build_composite_grid_image, build_visualization

# ── Internal data contracts ───────────────────────────────────────────────────
class BatchImageResult(TypedDict, total=False):
    index: int
    filename: str
    region: str
    label: str
    confidence: float
    x: int
    y: int
    severity_score: float
    image_data_uri: Optional[str]
    heatmap_image_data_uri: Optional[str]
    heatmap_summary: Dict[str, Any]
    heatmap_error: Optional[str]
    error: str


class RegionStats(TypedDict):
    region: str
    total: int
    label_counts: Dict[str, int]
    dominant_defect: str
    defect_density: float
    avg_confidence: float


class BatchInsights(TypedDict):
    total_images: int
    clean_rate: float
    defect_rate: float
    confidence_mean: float
    confidence_std: float
    confidence_min: float
    confidence_max: float
    worst_region: Optional[str]


class BatchRecommendation(TypedDict):
    region: str
    defect: str
    density: float
    recommendation: str
    source: str


class BatchVisualizationPoint(TypedDict):
    x: int
    y: int
    z: float
    region: str
    label: str
    confidence: float
    severity: float
    image_data_uri: Optional[str]
    heatmap_image_data_uri: Optional[str]


class CombinedGridAnalysis(TypedDict):
    grid_size: int
    grid_image: str
    grid_prediction: Dict[str, Any]
    grid_heatmap_image: str
    grid_heatmap_summary: Dict[str, Any]
    per_image_heatmap_summary: Dict[str, Any]
    heatmap_comparison: Dict[str, Any]


class BatchJobState(TypedDict):
    job_id: str
    status: Literal["queued", "running", "completed", "failed"]
    total: int
    processed: int
    failed: int
    started_at: str
    completed_at: Optional[str]
    result: Optional[Dict[str, Any]]
    error: Optional[str]


# ── Constants ────────────────────────────────────────────────────────────────
MAX_IMAGES = 256
MAX_ARCHIVE_MB = 200
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
JOB_TTL_SECONDS = 1800  # 30 minutes
MAX_CONCURRENT_WORKERS = 4

# ── In-memory job registry ────────────────────────────────────────────────────
_jobs: Dict[str, BatchJobState] = {}
_jobs_lock = asyncio.Lock()


def _new_job_id() -> str:
    return f"BATCH-{uuid.uuid4().hex[:12].upper()}"


async def _get_job(job_id: str) -> Optional[BatchJobState]:
    async with _jobs_lock:
        return _jobs.get(job_id)


async def _set_job(job_id: str, state: BatchJobState) -> None:
    async with _jobs_lock:
        _jobs[job_id] = state


async def _update_job(job_id: str, **kwargs: Any) -> None:
    async with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def _initial_state(job_id: str, total: int) -> BatchJobState:
    return {
        "job_id": job_id,
        "status": "queued",
        "total": total,
        "processed": 0,
        "failed": 0,
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "result": None,
        "error": None,
    }


# ── Cleanup old jobs ─────────────────────────────────────────────────────────
async def _cleanup_old_jobs() -> None:
    cutoff = datetime.utcnow() - timedelta(seconds=JOB_TTL_SECONDS)
    async with _jobs_lock:
        to_delete = [
            jid
            for jid, state in _jobs.items()
            if state.get("status") in ("completed", "failed")
            and datetime.fromisoformat(state["started_at"]) < cutoff
        ]
        for jid in to_delete:
            del _jobs[jid]


# ── Image file helpers ────────────────────────────────────────────────────────
def _is_allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _extract_zip(archive_bytes: bytes) -> List[tuple[str, bytes]]:
    """Safely extract image files from a zip archive, blocking path traversal."""
    images: List[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        for info in zf.infolist():
            # Block path traversal
            safe_name = Path(info.filename).name
            if not safe_name or not _is_allowed(safe_name):
                continue
            if len(images) >= MAX_IMAGES:
                break
            images.append((safe_name, zf.read(info.filename)))
    return images


# ── Core inference loop ───────────────────────────────────────────────────────
def _run_inference_on_bytes(image_bytes: bytes, filename: str) -> tuple[str, float]:
    """Write image bytes to a temp file and run existing inference."""
    suffix = Path(filename).suffix or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    try:
        from src.inference.run_inference import predict_with_probs  # noqa: PLC0415
        label, confidence, _ = predict_with_probs(tmp_path)
        return label, confidence
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _to_data_uri(image_bytes: bytes, ext: str = "png") -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/{ext};base64,{encoded}"


def _mime_ext_from_filename(filename: str) -> Optional[str]:
    ext = Path(filename).suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "jpeg"
    if ext == ".png":
        return "png"
    if ext == ".webp":
        return "webp"
    if ext == ".bmp":
        return "bmp"
    return None


def _build_thumbnail_data_uri(
    image_bytes: bytes,
    filename: str,
    *,
    thumb_size: int = 192,
) -> Optional[str]:
    """
    Build a compact square thumbnail data URI for 3D tile texturing.
    Returns None on decode/processing failure.
    """
    try:
        # Pillow >=9 exposes Image.Resampling, older versions keep constants on Image.
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)
        with Image.open(io.BytesIO(image_bytes)) as source:
            img = source.convert("RGB")
            img.thumbnail((thumb_size, thumb_size), resample)
            canvas = Image.new("RGB", (thumb_size, thumb_size), color=(9, 12, 18))
            offset = (
                (thumb_size - img.width) // 2,
                (thumb_size - img.height) // 2,
            )
            canvas.paste(img, offset)
            buffer = io.BytesIO()
            canvas.save(buffer, format="PNG")
            return _to_data_uri(buffer.getvalue(), "png")
    except Exception:
        return None


def _build_display_data_uri(image_bytes: bytes, filename: str) -> Optional[str]:
    """
    Prefer exact uploaded image bytes for display when browser-compatible.
    Fallback to a robust PNG thumbnail for unsupported formats (e.g., TIFF).
    """
    mime_ext = _mime_ext_from_filename(filename)
    if mime_ext:
        return _to_data_uri(image_bytes, mime_ext)
    return _build_thumbnail_data_uri(image_bytes, filename)


def _run_heatmap_artifacts_on_bytes(
    image_bytes: bytes, filename: str
) -> tuple[Dict[str, Any], Optional[str]]:
    suffix = Path(filename).suffix or ".png"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    heatmap_path = None
    try:
        from src.inference.gradcam import generate_gradcam, summarize_gradcam_overlay  # noqa: PLC0415

        _predicted, heatmap_path = generate_gradcam(tmp_path)
        summary = summarize_gradcam_overlay(heatmap_path)
        heatmap_image_data_uri = None
        if heatmap_path and os.path.exists(heatmap_path):
            with open(heatmap_path, "rb") as handle:
                heatmap_image_data_uri = _build_thumbnail_data_uri(
                    handle.read(),
                    f"{Path(filename).stem}_heatmap.png",
                )
        return summary, heatmap_image_data_uri
    finally:
        if heatmap_path:
            try:
                os.unlink(heatmap_path)
            except OSError:
                pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _run_heatmap_summary_on_bytes(image_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Backward-compatible helper retained for tests and legacy call sites.
    """
    summary, _heatmap_image_data_uri = _run_heatmap_artifacts_on_bytes(image_bytes, filename)
    return summary

def _aggregate_per_image_heatmap_summaries(
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    summaries = [
        r.get("heatmap_summary")
        for r in results
        if r.get("heatmap_summary") and isinstance(r.get("heatmap_summary"), dict)
    ]
    if not summaries:
        return {
            "count": 0,
            "dominant_region_distribution": {},
            "avg_spread_score": 0.0,
            "avg_hotspots": 0.0,
            "avg_max_activation": 0.0,
            "dominant_region_mode": "unknown",
        }

    region_counts: Dict[str, int] = {}
    spread_values: List[float] = []
    hotspot_values: List[float] = []
    activation_values: List[float] = []

    for summary in summaries:
        region = str(summary.get("dominant_region", "unknown"))
        region_counts[region] = region_counts.get(region, 0) + 1
        spread_values.append(float(summary.get("spread_score", 0.0)))
        hotspot_values.append(float(summary.get("num_hotspots", 0)))
        activation_values.append(float(summary.get("max_activation", 0.0)))

    dominant_region_mode = max(region_counts, key=region_counts.get)
    return {
        "count": len(summaries),
        "dominant_region_distribution": region_counts,
        "avg_spread_score": round(statistics.mean(spread_values), 4),
        "avg_hotspots": round(statistics.mean(hotspot_values), 4),
        "avg_max_activation": round(statistics.mean(activation_values), 4),
        "dominant_region_mode": dominant_region_mode,
    }


def _compare_heatmaps(
    per_image_summary: Dict[str, Any],
    combined_summary: Dict[str, Any],
) -> Dict[str, Any]:
    per_mode = per_image_summary.get("dominant_region_mode", "unknown")
    combined_mode = combined_summary.get("dominant_region", "unknown")
    spread_delta = round(
        float(combined_summary.get("spread_score", 0.0))
        - float(per_image_summary.get("avg_spread_score", 0.0)),
        4,
    )
    hotspot_delta = round(
        float(combined_summary.get("num_hotspots", 0.0))
        - float(per_image_summary.get("avg_hotspots", 0.0)),
        4,
    )
    activation_delta = round(
        float(combined_summary.get("max_activation", 0.0))
        - float(per_image_summary.get("avg_max_activation", 0.0)),
        4,
    )
    dominant_region_match = per_mode == combined_mode

    if dominant_region_match and spread_delta <= 0.05:
        conclusion = "Composite heatmap aligns with per-image pattern."
    elif not dominant_region_match:
        conclusion = "Composite heatmap shifts dominant focus versus per-image trend."
    else:
        conclusion = "Composite heatmap is more diffuse than per-image average."

    return {
        "dominant_region_match": dominant_region_match,
        "per_image_dominant_region": per_mode,
        "combined_dominant_region": combined_mode,
        "spread_delta": spread_delta,
        "hotspot_delta": hotspot_delta,
        "activation_delta": activation_delta,
        "conclusion": conclusion,
    }


def _run_combined_grid_analysis(
    named_images: List[tuple[str, bytes]],
    valid_results: List[Dict[str, Any]],
) -> CombinedGridAnalysis:
    from src.inference.gradcam import generate_gradcam, summarize_gradcam_overlay  # noqa: PLC0415
    from src.inference.run_inference import predict_with_probs  # noqa: PLC0415

    composite_bytes, grid_size = build_composite_grid_image(named_images)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(composite_bytes)
        composite_path = tmp.name

    heatmap_path = None
    try:
        label, confidence, top_predictions = predict_with_probs(composite_path)
        _predicted, heatmap_path = generate_gradcam(composite_path)
        combined_heatmap_summary = summarize_gradcam_overlay(heatmap_path)

        with open(heatmap_path, "rb") as handle:
            combined_heatmap_bytes = handle.read()

        per_image_summary = _aggregate_per_image_heatmap_summaries(valid_results)
        heatmap_comparison = _compare_heatmaps(per_image_summary, combined_heatmap_summary)

        return {
            "grid_size": grid_size,
            "grid_image": _to_data_uri(composite_bytes, ext="png"),
            "grid_prediction": {
                "label": label,
                "confidence": round(confidence, 4),
                "top_predictions": top_predictions,
            },
            "grid_heatmap_image": _to_data_uri(combined_heatmap_bytes, ext="png"),
            "grid_heatmap_summary": combined_heatmap_summary,
            "per_image_heatmap_summary": per_image_summary,
            "heatmap_comparison": heatmap_comparison,
        }
    finally:
        if heatmap_path:
            try:
                os.unlink(heatmap_path)
            except OSError:
                pass
        try:
            os.unlink(composite_path)
        except OSError:
            pass


async def _process_images(
    job_id: str,
    named_images: List[tuple[str, bytes]],
    include_visualization: bool,
    enable_genai: bool,
) -> None:
    """Background coroutine that runs inference and builds the final result."""
    total = len(named_images)
    await _update_job(job_id, status="running")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)
    results: List[Optional[Dict[str, Any]]] = [None] * total
    failed_count = 0
    completed_count = 0
    progress_lock = asyncio.Lock()

    async def process_one(index: int, filename: str, img_bytes: bytes) -> None:
        nonlocal failed_count, completed_count
        async with semaphore:
            try:
                label, confidence = await asyncio.to_thread(
                    _run_inference_on_bytes, img_bytes, filename
                )
                heatmap_summary = None
                heatmap_image_data_uri = None
                heatmap_error = None
                try:
                    heatmap_summary, heatmap_image_data_uri = await asyncio.to_thread(
                        _run_heatmap_artifacts_on_bytes,
                        img_bytes,
                        filename,
                    )
                except Exception as hm_exc:
                    heatmap_error = str(hm_exc)
                image_data_uri = await asyncio.to_thread(
                    _build_display_data_uri,
                    img_bytes,
                    filename,
                )
                x, y = get_grid_coords(index, total)
                region = assign_region(index, total)
                results[index] = {
                    "index": index,
                    "filename": filename,
                    "region": region,
                    "label": label,
                    "confidence": confidence,
                    "x": x,
                    "y": y,
                    "severity_score": round(1.0 - confidence, 4),
                    "image_data_uri": image_data_uri,
                    "heatmap_image_data_uri": heatmap_image_data_uri,
                    "heatmap_summary": heatmap_summary,
                    "heatmap_error": heatmap_error,
                }
            except Exception as exc:
                failed_count += 1
                x, y = get_grid_coords(index, total)
                image_data_uri = await asyncio.to_thread(
                    _build_display_data_uri,
                    img_bytes,
                    filename,
                )
                results[index] = {
                    "index": index,
                    "filename": filename,
                    "region": assign_region(index, total),
                    "label": "error",
                    "confidence": 0.0,
                    "x": x,
                    "y": y,
                    "severity_score": 1.0,
                    "image_data_uri": image_data_uri,
                    "heatmap_image_data_uri": None,
                    "error": str(exc),
                }
            finally:
                async with progress_lock:
                    completed_count += 1
                    current_completed = completed_count
                    current_failed = failed_count
                await _update_job(
                    job_id,
                    processed=current_completed,
                    failed=current_failed,
                )

    try:
        tasks = [
            asyncio.create_task(process_one(i, fname, img_bytes))
            for i, (fname, img_bytes) in enumerate(named_images)
        ]
        await asyncio.gather(*tasks)

        valid_results = [r for r in results if r is not None and r["label"] != "error"]

        if not valid_results:
            failed_result = {
                "job_id": job_id,
                "total_images": total,
                "processed_images": 0,
                "failed_images": failed_count,
                "region_stats": [],
                "insights": {
                    "total_images": total,
                    "clean_rate": 0.0,
                    "defect_rate": 0.0,
                    "confidence_mean": 0.0,
                    "confidence_std": 0.0,
                    "confidence_min": 0.0,
                    "confidence_max": 0.0,
                    "worst_region": None,
                },
                "recommendations": [],
                "visualization": None,
                "spatial_points": [],
                "combined_analysis": None,
                "completed_at": datetime.utcnow().isoformat(),
                "individual_results": [r for r in results if r is not None],
                "error_summary": f"All {total} images failed inference.",
            }
            await _update_job(
                job_id,
                status="failed",
                error=failed_result["error_summary"],
                result=failed_result,
                completed_at=datetime.utcnow().isoformat(),
                processed=total,
                failed=failed_count,
            )
            return

        aggregation = aggregate_results(valid_results)
        region_stats = aggregation["region_stats"]
        insights = aggregation["insights"]
        recommendations = generate_recommendations(region_stats, enable_genai=enable_genai)

        visualization = None
        spatial_points = []
        if include_visualization and valid_results:
            visualization = build_visualization(valid_results, region_stats)
            spatial_points = visualization.get("grid_points", [])

        combined_analysis = None
        combined_analysis_error = None
        if include_visualization and named_images:
            try:
                combined_analysis = await asyncio.to_thread(
                    _run_combined_grid_analysis,
                    named_images,
                    valid_results,
                )
            except Exception as combined_exc:
                combined_analysis_error = str(combined_exc)

        final_result = {
            "job_id": job_id,
            "total_images": total,
            "processed_images": len(valid_results),
            "failed_images": failed_count,
            "region_stats": region_stats,
            "insights": insights,
            "recommendations": recommendations,
            "visualization": visualization,
            "spatial_points": spatial_points,
            "combined_analysis": combined_analysis,
            "combined_analysis_error": combined_analysis_error,
            "completed_at": datetime.utcnow().isoformat(),
            "individual_results": [r for r in results if r is not None],
        }

        await _update_job(
            job_id,
            status="completed",
            result=final_result,
            completed_at=datetime.utcnow().isoformat(),
            processed=total,
            failed=failed_count,
        )
    except Exception as exc:
        await _update_job(
            job_id,
            status="failed",
            error=f"Post-processing failed: {exc}",
            completed_at=datetime.utcnow().isoformat(),
            processed=completed_count,
            failed=failed_count,
        )
    finally:
        # Background cleanup of old jobs
        asyncio.create_task(_cleanup_old_jobs())


# ── Public API ────────────────────────────────────────────────────────────────
async def start_batch_job(
    named_images: List[tuple[str, bytes]],
    include_visualization: bool = True,
    enable_genai: bool = False,
) -> str:
    """
    Validate input, register a new job, launch background processing, return job_id.
    Raises ValueError on validation failures.
    """
    if not named_images:
        raise ValueError("No images provided.")
    if len(named_images) > MAX_IMAGES:
        raise ValueError(f"Batch exceeds maximum of {MAX_IMAGES} images.")

    job_id = _new_job_id()
    state = _initial_state(job_id, len(named_images))
    await _set_job(job_id, state)

    asyncio.create_task(
        _process_images(job_id, named_images, include_visualization, enable_genai)
    )
    return job_id


async def get_batch_job(job_id: str) -> Optional[BatchJobState]:
    """Return the current state of a batch job, or None if not found."""
    return await _get_job(job_id)


def prepare_images_from_uploads(
    image_files: List[tuple[str, bytes]],
    archive_files: List[tuple[str, bytes]],
) -> List[tuple[str, bytes]]:
    """
    Combine direct image uploads and zip archive contents into a unified list.
    Filters by allowed extensions and respects MAX_IMAGES cap.
    """
    named: List[tuple[str, bytes]] = []

    for fname, fbytes in image_files:
        if _is_allowed(fname) and len(named) < MAX_IMAGES:
            named.append((fname, fbytes))

    for archive_name, archive_bytes in archive_files:
        size_mb = len(archive_bytes) / (1024 * 1024)
        if size_mb > MAX_ARCHIVE_MB:
            raise ValueError(
                f"Archive '{archive_name}' exceeds {MAX_ARCHIVE_MB} MB limit."
            )
        try:
            extracted = _extract_zip(archive_bytes)
        except zipfile.BadZipFile:
            raise ValueError(f"Invalid ZIP archive: {archive_name}")
        for fname, fbytes in extracted:
            if len(named) >= MAX_IMAGES:
                break
            named.append((fname, fbytes))

    return named
