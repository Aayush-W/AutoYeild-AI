import sys
import json
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

from api.services.insight_reasoner import generate_ai_insight

SAMPLE_OBSERVATION = {
    "prediction_label": "random",
    "confidence": 0.41,
    "heatmap_analysis": {
        "dominant_region": "unknown",
        "spread_score": 0.0,
        "num_hotspots": 0,
        "max_activation": 0.0,
    },
    "drift": {
        "current_score": 0.0,
        "trend": "stable",
        "tool": "inspection-tool",
    },
    "metadata": {
        "lot_id": "TEST-001",
        "process_stage": "wafer-inspection",
    },
}

def main():
    print("=========================================")
    print("Testing generate_ai_insight (Step 5 fix)")
    print("=========================================")
    try:
        result = generate_ai_insight(SAMPLE_OBSERVATION, top_k=3)
        print("\n--- FINAL OUTPUT ---")
        print(json.dumps(result, indent=2))
        print(f"\nfallback_used: {result.get('fallback_used')}")
        if not result.get("fallback_used"):
            print("SUCCESS! Valid JSON generated and parsed.")
        else:
            print("WARNING! Fallback was used. Parsing or generation failed.")
    except Exception as e:
        print("EXCEPTION in generate_ai_insight:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
