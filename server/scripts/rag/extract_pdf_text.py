"""
RAG Pipeline - Step 1: PDF Text Extraction
============================================
Reads every .pdf file inside rag_data/source_docs/,
extracts all readable text, and saves each one as a
separate .txt file in rag_data/extracted_text/.

Library required: PyMuPDF
Install with:  pip install pymupdf
"""

import sys
from pathlib import Path

# ── Try importing PyMuPDF (fitz) ─────────────────────────────────────────────
try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF is not installed.")
    print("Please run:  pip install pymupdf")
    sys.exit(1)

# ── Folder paths (relative to this script's location) ────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "rag_data" / "source_docs"
OUTPUT_DIR = PROJECT_ROOT / "rag_data" / "extracted_text"

# ── Sanity-check the source folder exists ────────────────────────────────────
if not SOURCE_DIR.exists():
    print(f"ERROR: Source folder not found: {SOURCE_DIR}")
    print("Please make sure rag_data/source_docs/ exists and contains PDF files.")
    sys.exit(1)

# ── Create the output folder if it doesn't exist ─────────────────────────────
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"Output folder ready: {OUTPUT_DIR}\n")

# ── Find all PDFs in the source folder ───────────────────────────────────────
pdf_files = sorted(SOURCE_DIR.glob("*.pdf"))

if not pdf_files:
    print("No PDF files found in rag_data/source_docs/. Nothing to do.")
    sys.exit(0)

print(f"Found {len(pdf_files)} PDF file(s) to process:\n")

success_count = 0
fail_count    = 0

# ── Process each PDF ─────────────────────────────────────────────────────────
for pdf_path in pdf_files:
    txt_filename = pdf_path.stem + ".txt"          # e.g. paper1.txt
    txt_path     = OUTPUT_DIR / txt_filename

    print(f"  Processing: {pdf_path.name}", end="  ...  ")

    try:
        doc = fitz.open(str(pdf_path))

        all_pages_text = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")           # plain-text extraction
            all_pages_text.append(f"--- Page {page_num + 1} ---\n{text}")

        doc.close()

        # Combine all pages into a single string
        full_text = "\n\n".join(all_pages_text)

        # Write to .txt file (UTF-8, so international characters are handled)
        txt_path.write_text(full_text, encoding="utf-8")

        char_count = len(full_text)
        print(f"Done  ({len(all_pages_text)} pages, {char_count:,} chars)  →  {txt_path.name}")
        success_count += 1

    except Exception as e:
        print(f"FAILED")
        print(f"    Reason: {e}")
        fail_count += 1

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print(f"Extraction complete.")
print(f"  Successful : {success_count} file(s)")
if fail_count:
    print(f"  Failed     : {fail_count} file(s)  (see errors above)")
print(f"  Output dir : {OUTPUT_DIR}")
print("=" * 60)
