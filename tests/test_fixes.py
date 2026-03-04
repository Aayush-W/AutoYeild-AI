"""
Unit tests for AutoYield-AI critical fix verification.

Run from the project root:
    python -m pytest tests/test_fixes.py -v

These tests do NOT require a trained model or GPU. They test:
1. DriftMonitor persistence across multiple update() calls
2. Label normalization via ontology.normalize_class()
3. Synthetic image uniqueness across calls
4. Auto-retrainer queue write/read
5. Triage agent queuing logic
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


class TestDriftMonitor(unittest.TestCase):
    """Fix #1: DriftMonitor must accumulate count across multiple update() calls."""

    def _make_monitor(self, tmp_dir, threshold=0.5, max_lc=2):
        from src.autonomy.drift_monitor import DriftMonitor
        state_file = Path(tmp_dir) / "drift_state.json"
        return DriftMonitor(
            confidence_threshold=threshold,
            max_low_confidence=max_lc,
            state_file=state_file,
        )

    def test_no_drift_on_single_low_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            mon = self._make_monitor(tmp, max_lc=2)
            result = mon.update(0.3)  # below threshold, count=1
            self.assertFalse(result, "Single low-conf prediction must NOT trigger drift when max_lc=2")

    def test_drift_on_consecutive_low_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            mon = self._make_monitor(tmp, max_lc=2)
            mon.update(0.3)           # count=1, no drift
            result = mon.update(0.3)  # count=2, drift!
            self.assertTrue(result, "Two consecutive low-conf predictions MUST trigger drift when max_lc=2")

    def test_high_confidence_resets_streak(self):
        with tempfile.TemporaryDirectory() as tmp:
            mon = self._make_monitor(tmp, max_lc=2)
            mon.update(0.3)    # count=1
            mon.update(0.9)    # count reset to 0
            result = mon.update(0.3)  # count=1 again — no drift
            self.assertFalse(result, "High-confidence prediction must reset the streak")

    def test_state_persisted_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "drift_state.json"
            from src.autonomy.drift_monitor import DriftMonitor
            mon = DriftMonitor(confidence_threshold=0.5, max_low_confidence=3, state_file=state_file)
            mon.update(0.3)
            self.assertTrue(state_file.exists(), "State file should be created after first update")
            data = json.loads(state_file.read_text())
            self.assertEqual(data["low_confidence_count"], 1)

    def test_drift_resets_count_after_detection(self):
        """After drift is declared the count must reset so the next window starts fresh."""
        with tempfile.TemporaryDirectory() as tmp:
            mon = self._make_monitor(tmp, max_lc=2)
            mon.update(0.3)
            mon.update(0.3)   # drift detected, count → 0
            # Next single low-conf should NOT immediately fire again
            result = mon.update(0.3)
            self.assertFalse(result, "Count must reset to 0 after drift event")


class TestOntologyNormalization(unittest.TestCase):
    """Fix #3: normalize_class() must map raw model labels to canonical snake_case."""

    def setUp(self):
        from src.utils.ontology import normalize_class
        self.norm = normalize_class

    def test_edge_ring_with_space(self):
        self.assertEqual(self.norm("Edge ring"), "edge_ring")

    def test_edge_ring_mixed_case(self):
        self.assertEqual(self.norm("Edge Ring"), "edge_ring")

    def test_center_capitalized(self):
        self.assertEqual(self.norm("Center"), "center")

    def test_local_capitalized(self):
        self.assertEqual(self.norm("Local"), "local")

    def test_scratch_lowercase(self):
        self.assertEqual(self.norm("scratch"), "scratch")

    def test_clean(self):
        self.assertEqual(self.norm("clean"), "clean")

    def test_near_full_with_space(self):
        self.assertEqual(self.norm("near full"), "near_full")

    def test_already_canonical(self):
        self.assertEqual(self.norm("edge_ring"), "edge_ring")


class TestSyntheticGeneratorUniqueness(unittest.TestCase):
    """
    Augmentation-based generator: each call produces a uniquely-named batch
    (timestamp + UUID prefix) so batches never silently overwrite each other.
    Falls back to noise when no training images are found.
    """

    def test_images_are_saved_fallback(self):
        """With no source train dir, generator falls back to noise and still saves files."""
        from src.self_improvement.synthetic_generator import generate_synthetic_images
        with tempfile.TemporaryDirectory() as tmp:
            paths = generate_synthetic_images(
                output_dir=tmp,
                num_images=3,
                image_size=(32, 32),
                train_dir=str(Path(tmp) / "nonexistent"),  # force fallback
            )
            self.assertEqual(len(paths), 3)
            for p in paths:
                self.assertTrue(Path(p).exists(), f"Expected image file at {p}")

    def test_augmented_batches_have_unique_filenames(self):
        """Two consecutive calls must produce different filenames (timestamp+UUID prefix)."""
        from src.self_improvement.synthetic_generator import generate_synthetic_images
        with tempfile.TemporaryDirectory() as tmp_out:
            # Use a temp source dir with a real image
            with tempfile.TemporaryDirectory() as tmp_src:
                # Create a minimal single-class dir with one solid-colour image
                cls_dir = Path(tmp_src) / "center"
                cls_dir.mkdir()
                img = Image.new("RGB", (64, 64), color=(128, 64, 200))
                img.save(cls_dir / "sample.jpg")

                import time as _time
                batch1 = generate_synthetic_images(
                    output_dir=tmp_out, num_images=2, image_size=(32, 32),
                    train_dir=tmp_src,
                )
                _time.sleep(0.01)  # ensure different timestamp
                batch2 = generate_synthetic_images(
                    output_dir=tmp_out, num_images=2, image_size=(32, 32),
                    train_dir=tmp_src,
                )

            names1 = {Path(p).name for p in batch1}
            names2 = {Path(p).name for p in batch2}
            self.assertTrue(
                names1.isdisjoint(names2),
                f"Batches share filenames: {names1 & names2}",
            )

    def test_output_image_dimensions(self):
        """Generated images must have exactly the requested dimensions."""
        from src.self_improvement.synthetic_generator import generate_synthetic_images
        with tempfile.TemporaryDirectory() as tmp:
            paths = generate_synthetic_images(
                output_dir=tmp,
                num_images=2,
                image_size=(48, 48),
                train_dir=str(Path(tmp) / "nonexistent"),
            )
            for p in paths:
                with Image.open(p) as img:
                    self.assertEqual(img.size, (48, 48),
                                     f"Expected 48x48, got {img.size} for {p}")

    def test_seed_parameter_accepted(self):
        """seed kwarg must still be accepted for API backward-compatibility."""
        from src.self_improvement.synthetic_generator import generate_synthetic_images
        with tempfile.TemporaryDirectory() as tmp:
            try:
                paths = generate_synthetic_images(
                    output_dir=tmp, num_images=1, image_size=(16, 16), seed=42,
                    train_dir=str(Path(tmp) / "nonexistent"),
                )
                self.assertEqual(len(paths), 1)
            except TypeError as e:
                self.fail(f"seed parameter rejected with TypeError: {e}")


class TestAutoRetrainer(unittest.TestCase):
    """Fix #7: auto_retrainer must write queue entries and count pending correctly."""

    def _queue_file(self, tmp_dir):
        return Path(tmp_dir) / "outputs" / "metrics" / "retraining_queue.json"

    def test_queue_entry_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Patch the queue file path for isolation
            import src.self_improvement.auto_retrainer as ar
            original = ar._QUEUE_FILE
            ar._QUEUE_FILE = Path(tmp) / "retraining_queue.json"
            try:
                entry = ar.queue_for_retraining(
                    image_path="/tmp/wafer.png",
                    predicted_class="edge_ring",
                    confidence=0.3,
                    reason="low_confidence",
                )
                self.assertIn("entry_id", entry)
                self.assertTrue(entry["entry_id"].startswith("RT-"))
                queue = json.loads(ar._QUEUE_FILE.read_text())
                self.assertEqual(len(queue), 1)
            finally:
                ar._QUEUE_FILE = original

    def test_threshold_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            import src.self_improvement.auto_retrainer as ar
            original = ar._QUEUE_FILE
            ar._QUEUE_FILE = Path(tmp) / "retraining_queue.json"
            try:
                for i in range(5):
                    ar.queue_for_retraining(f"/tmp/w{i}.png", "scratch", 0.3)
                self.assertTrue(ar.check_retraining_threshold(min_queue_size=5))
                self.assertFalse(ar.check_retraining_threshold(min_queue_size=10))
            finally:
                ar._QUEUE_FILE = original


class TestTriageAgent(unittest.TestCase):
    """GenAI enhancement C: triage() must queue low-confidence samples."""

    def _patch_queue_file(self, ar_module, tmp_dir):
        ar_module._QUEUE_FILE = Path(tmp_dir) / "retraining_queue.json"

    def test_queues_low_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            import src.self_improvement.auto_retrainer as ar
            original = ar._QUEUE_FILE
            ar._QUEUE_FILE = Path(tmp) / "retraining_queue.json"
            try:
                from src.autonomy.triage_agent import triage
                result = triage(
                    image_path="/tmp/w.png",
                    predicted_class="Center",
                    confidence=0.3,
                    top_predictions=[{"label": "Center", "prob": 0.3}],
                    confidence_threshold=0.55,
                )
                self.assertTrue(result["queued"])
                self.assertEqual(result["reason"], "low_confidence")
            finally:
                ar._QUEUE_FILE = original

    def test_queues_ambiguous_top2(self):
        with tempfile.TemporaryDirectory() as tmp:
            import src.self_improvement.auto_retrainer as ar
            original = ar._QUEUE_FILE
            ar._QUEUE_FILE = Path(tmp) / "retraining_queue.json"
            try:
                from src.autonomy.triage_agent import triage
                result = triage(
                    image_path="/tmp/w.png",
                    predicted_class="Edge ring",
                    confidence=0.65,
                    top_predictions=[
                        {"label": "Edge ring", "prob": 0.65},
                        {"label": "Local", "prob": 0.60},  # margin = 0.05 < 0.10
                    ],
                    confidence_threshold=0.55,
                    ambiguity_margin=0.10,
                )
                self.assertTrue(result["queued"])
                self.assertEqual(result["reason"], "ambiguous")
            finally:
                ar._QUEUE_FILE = original

    def test_accepted_high_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            import src.self_improvement.auto_retrainer as ar
            original = ar._QUEUE_FILE
            ar._QUEUE_FILE = Path(tmp) / "retraining_queue.json"
            try:
                from src.autonomy.triage_agent import triage
                result = triage(
                    image_path="/tmp/w.png",
                    predicted_class="clean",
                    confidence=0.92,
                    top_predictions=[
                        {"label": "clean", "prob": 0.92},
                        {"label": "random", "prob": 0.05},
                    ],
                    confidence_threshold=0.55,
                    ambiguity_margin=0.10,
                )
                self.assertFalse(result["queued"])
                self.assertEqual(result["reason"], "accepted")
            finally:
                ar._QUEUE_FILE = original


if __name__ == "__main__":
    unittest.main()
