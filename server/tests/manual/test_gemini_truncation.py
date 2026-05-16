import os, sys, json
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
from dotenv import load_dotenv; load_dotenv(PROJECT_ROOT / ".env")
import google.generativeai as genai

key = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=key)
model = genai.GenerativeModel("gemini-2.5-flash")

prompt = """You are a semiconductor wafer inspection reasoning assistant for the AutoYield AI system.
Your task is to produce a brief, grounded, engineering-level AI insight for the current wafer inspection result.

OUTPUT FORMAT — STRICT
Return ONLY valid JSON.
{
  "summary": "string",
  "reasoning_basis": ["string"],
  "certainty": "low",
  "recommended_checks": ["string"]
}

OBSERVED EVIDENCE
-----------------
Predicted defect class  : random
Model confidence        : 0.410  (low confidence)
"""

response = model.generate_content(
    prompt,
    generation_config={"temperature": 0.15, "max_output_tokens": 700}
)

out_path = PROJECT_ROOT / "outputs" / "debug" / "truncation_result.txt"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    if response.candidates:
        cand = response.candidates[0]
        f.write("FINISH_REASON: " + str(cand.finish_reason) + "\n")
        parts = cand.content.parts
        if parts:
            f.write("TEXT: " + parts[0].text + "\n")
