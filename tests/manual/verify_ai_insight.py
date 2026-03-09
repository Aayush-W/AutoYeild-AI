"""
Verification script: POST a real wafer image to /api/analyze
and print the ai_insight field from the response.
"""
import json
import sys
from pathlib import Path
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IMAGE_PATH = str(PROJECT_ROOT / "outputs" / "uploads" / "641447.jpg")
URL        = "http://localhost:8000/api/analyze"

print(f"POSTing {IMAGE_PATH} to {URL} ...\n")

with open(IMAGE_PATH, "rb") as f:
    resp = requests.post(
        URL,
        files={"file": ("test.jpg", f, "image/jpeg")},
        data={"confidence_threshold": 0.45},
        timeout=120,
    )

if resp.status_code != 200:
    print(f"ERROR: HTTP {resp.status_code}")
    print(resp.text[:500])
    sys.exit(1)

data = resp.json()

# ── 1. Does ai_insight exist in the response? ────────────────────────────────
ai_insight = data.get("ai_insight")
print("=" * 64)
print("  CHECK 1 — Does ai_insight exist in response?")
print(f"  {'YES ✅' if ai_insight else 'NO ❌  (key missing)'}")
print()

# ── 2. Is fallback_used false? ───────────────────────────────────────────────
if ai_insight:
    fallback = ai_insight.get("fallback_used", "key-missing")
    print("  CHECK 2 — fallback_used value:")
    if fallback is False:
        print("  false ✅  Gemini actually responded and JSON was parsed correctly.")
    elif fallback is True:
        print("  true ⚠️   LLM call or JSON parsing failed — using deterministic fallback.")
    else:
        print(f"  {fallback} (unexpected)")
    print()

    # ── 3. Full ai_insight content ──────────────────────────────────────────
    print("  CHECK 3 — Full ai_insight content:")
    print(json.dumps(ai_insight, indent=4))

print()
print("  Other response keys:", list(data.keys()))
print("=" * 64)
