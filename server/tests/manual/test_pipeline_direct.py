"""
Direct pipeline test - bypasses FastAPI and runs inference + insight directly.
"""
import sys, traceback, json
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

img = str(PROJECT_ROOT / "outputs" / "uploads" / "641447.jpg")

print("Step 1: Running inference...")
try:
    from src.inference.run_inference import predict_with_probs
    defect_class, confidence, top_predictions = predict_with_probs(img)
    print(f"  defect_class={defect_class}  confidence={confidence:.4f}")
except Exception:
    print("  FAILED:")
    traceback.print_exc()
    sys.exit(1)

print("\nStep 2: Running Grad-CAM...")
try:
    from src.inference.gradcam import generate_gradcam
    cam_class, cam_path = generate_gradcam(img)
    print(f"  cam_class={cam_class}")
except Exception:
    print("  FAILED:")
    traceback.print_exc()
    sys.exit(1)

print("\nStep 3: Running triage...")
try:
    from src.autonomy.triage_agent import triage
    triage_result = triage(img, defect_class, confidence, top_predictions)
    print(f"  triage_result type={type(triage_result)}: {str(triage_result)[:100]}")
except Exception:
    print("  FAILED:")
    traceback.print_exc()
    sys.exit(1)

print("\nStep 4: Calling generate_ai_insight...")
try:
    from api.services.insight_reasoner import generate_ai_insight
    observation = {
        "prediction_label": defect_class,
        "confidence": round(confidence, 4),
        "heatmap_analysis": {
            "dominant_region": triage_result.get("dominant_region", "unknown") if isinstance(triage_result, dict) else "unknown",
            "spread_score":    triage_result.get("spread_score", 0.0) if isinstance(triage_result, dict) else 0.0,
            "num_hotspots":    triage_result.get("num_hotspots", 0) if isinstance(triage_result, dict) else 0,
            "max_activation":  triage_result.get("max_activation", 0.0) if isinstance(triage_result, dict) else 0.0,
        },
        "drift": {
            "current_score": 0,
            "trend": "stable",
            "tool": "inspection-tool",
        },
        "metadata": {
            "lot_id": "TEST-001",
            "process_stage": "wafer-inspection",
        },
    }
    result = generate_ai_insight(observation, top_k=5)
    print("\n" + "="*64)
    print("  ai_insight result:")
    print(json.dumps(result, indent=4))
    print("="*64)
    print(f"\n  fallback_used = {result.get('fallback_used')}")
    if result.get('fallback_used') is False:
        print("  Gemini responded successfully! ✅")
    else:
        print("  Fallback used — check GEMINI_API_KEY or Gemini response format.")
except Exception:
    print("  FAILED:")
    traceback.print_exc()
