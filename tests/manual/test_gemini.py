from dotenv import load_dotenv
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
import os, traceback

key = os.getenv("GEMINI_API_KEY", "")
print(f"Key length: {len(key)}, starts with: {key[:8]}")

try:
    import google.generativeai as genai
    print("google-generativeai version:", genai.__version__)
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    # Try without response_mime_type first
    r = model.generate_content(
        'Return this JSON exactly: {"greeting": "hello", "status": "ok"}',
        generation_config={"temperature": 0.1, "max_output_tokens": 60},
    )
    print("SUCCESS:")
    print(r.text)
except Exception:
    print("FAILED:")
    traceback.print_exc()
