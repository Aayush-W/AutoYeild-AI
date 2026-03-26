import asyncio
import time

import pytest

from src.batch import batch_processor as bp


async def _clear_jobs() -> None:
    async with bp._jobs_lock:
        bp._jobs.clear()


async def _wait_for_terminal(job_id: str, timeout_s: float = 5.0):
    started = time.time()
    last_state = None
    while time.time() - started < timeout_s:
        last_state = await bp.get_batch_job(job_id)
        if last_state and last_state.get("status") in {"completed", "failed"}:
            return last_state
        await asyncio.sleep(0.03)
    raise TimeoutError(f"Job {job_id} did not reach terminal status. Last state: {last_state}")


@pytest.mark.asyncio
async def test_progress_is_monotonic_under_parallel_completion(monkeypatch):
    await _clear_jobs()

    def fake_infer(_image_bytes, filename):
        # Complete out-of-order: lower index sleeps longer.
        idx = int(filename.split("_")[1].split(".")[0])
        time.sleep(max(0.0, (4 - idx) * 0.03))
        return "clean", 0.9

    monkeypatch.setattr(bp, "_run_inference_on_bytes", fake_infer)

    named_images = [(f"img_{i}.png", b"x") for i in range(5)]
    job_id = await bp.start_batch_job(named_images)

    progress_values = []
    final_state = None
    for _ in range(200):
        state = await bp.get_batch_job(job_id)
        if not state:
            await asyncio.sleep(0.03)
            continue
        progress_values.append(state.get("processed", 0))
        if state.get("status") in {"completed", "failed"}:
            final_state = state
            break
        await asyncio.sleep(0.03)

    assert final_state is not None, "Batch job did not complete in time."
    assert final_state["status"] == "completed"
    assert all(
        nxt >= prev for prev, nxt in zip(progress_values, progress_values[1:])
    ), f"Progress regressed: {progress_values}"


def test_invalid_zip_raises_value_error():
    with pytest.raises(ValueError, match="Invalid ZIP archive"):
        bp.prepare_images_from_uploads([], [("invalid.zip", b"not-a-valid-zip")])


@pytest.mark.asyncio
async def test_unhandled_post_processing_exception_marks_job_failed(monkeypatch):
    await _clear_jobs()

    monkeypatch.setattr(bp, "_run_inference_on_bytes", lambda _b, _f: ("clean", 0.8))

    def explode(_results):
        raise RuntimeError("aggregation exploded")

    monkeypatch.setattr(bp, "aggregate_results", explode)

    job_id = await bp.start_batch_job([("img_0.png", b"x")])
    final_state = await _wait_for_terminal(job_id)

    assert final_state["status"] == "failed"
    assert "Post-processing failed" in (final_state.get("error") or "")


@pytest.mark.asyncio
async def test_all_inference_failures_mark_job_failed_with_summary(monkeypatch):
    await _clear_jobs()

    def always_fail(_b, _f):
        raise RuntimeError("decode failed")

    monkeypatch.setattr(bp, "_run_inference_on_bytes", always_fail)

    job_id = await bp.start_batch_job(
        [("img_0.png", b"x"), ("img_1.png", b"x"), ("img_2.png", b"x")]
    )
    final_state = await _wait_for_terminal(job_id)

    assert final_state["status"] == "failed"
    assert final_state["failed"] == 3
    assert final_state["processed"] == 3
    assert "All 3 images failed inference." in (final_state.get("error") or "")
    assert final_state["result"] is not None
    assert final_state["result"]["processed_images"] == 0


@pytest.mark.asyncio
async def test_combined_grid_analysis_payload_present(monkeypatch):
    await _clear_jobs()

    monkeypatch.setattr(bp, "_run_inference_on_bytes", lambda _b, _f: ("clean", 0.91))
    monkeypatch.setattr(
        bp,
        "_run_heatmap_summary_on_bytes",
        lambda _b, _f: {
            "dominant_region": "center zone",
            "spread_score": 0.12,
            "num_hotspots": 2,
            "max_activation": 0.61,
        },
    )
    monkeypatch.setattr(
        bp,
        "_run_combined_grid_analysis",
        lambda _named, _results: {
            "grid_size": 1,
            "grid_image": "data:image/png;base64,AAA",
            "grid_heatmap_image": "data:image/png;base64,BBB",
            "grid_prediction": {"label": "clean", "confidence": 0.92, "top_predictions": []},
            "grid_heatmap_summary": {"dominant_region": "center zone"},
            "per_image_heatmap_summary": {"dominant_region_mode": "center zone"},
            "heatmap_comparison": {"dominant_region_match": True},
        },
    )

    job_id = await bp.start_batch_job([("img_0.png", b"x")], include_visualization=True)
    final_state = await _wait_for_terminal(job_id)

    assert final_state["status"] == "completed"
    assert final_state["result"] is not None
    assert final_state["result"]["combined_analysis"] is not None
    assert final_state["result"]["combined_analysis"]["grid_size"] == 1
