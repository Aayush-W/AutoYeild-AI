import os
from dotenv import load_dotenv; load_dotenv()
import google.generativeai as genai

key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=key)
model = genai.GenerativeModel("gemini-2.5-flash")

prompt = """Return ONLY valid JSON.
{
  "summary": "This is a test summary of the random defect.",
  "reasoning_basis": ["A", "B"],
  "certainty": "low",
  "recommended_checks": ["C", "D"]
}
"""

print("Testing with NO max_output_tokens...")
r = model.generate_content(prompt, generation_config={"temperature": 0.1})
print("Result length:", len(r.text))
print("Result:", r.text)
