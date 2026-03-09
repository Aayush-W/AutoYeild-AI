"""
RAG Pipeline - Step 2: Text Chunking
======================================
Reads every .txt file from rag_data/extracted_text/,
lightly cleans each one, splits it into overlapping
character-based chunks, and saves all chunks with
metadata to rag_data/processed/chunks.json.

No external libraries required — pure Python only.
"""

import json
import re
import sys
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
CHUNK_SIZE    = 1000   # target characters per chunk
CHUNK_OVERLAP = 200    # overlap characters between consecutive chunks
MIN_CHUNK_LEN = 100    # skip any chunk shorter than this (avoids tiny fragments)

# ── Folder paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR   = PROJECT_ROOT / "rag_data" / "extracted_text"
OUTPUT_DIR  = PROJECT_ROOT / "rag_data" / "processed"
OUTPUT_FILE = OUTPUT_DIR / "chunks.json"

# ── Verify input folder ───────────────────────────────────────────────────────
if not INPUT_DIR.exists():
    print(f"ERROR: Input folder not found: {INPUT_DIR}")
    print("Please complete Step 1 first (PDF extraction).")
    sys.exit(1)

# ── Create output folder ──────────────────────────────────────────────────────
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"Output folder ready: {OUTPUT_DIR}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Helper: light text cleaner
# ─────────────────────────────────────────────────────────────────────────────
def clean_text(raw: str) -> str:
    """
    Very light cleaning pass — never changes the meaning:
      1. Normalise Windows line endings  (\\r\\n → \\n)
      2. Collapse runs of 3+ blank lines into a single blank line
      3. Collapse runs of spaces/tabs on a single line to one space
      4. Strip leading / trailing whitespace from the whole document
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Remove page-break markers left by the extractor (e.g. "--- Page 3 ---")
    text = re.sub(r"--- Page \d+ ---", "", text)

    # Collapse 3+ consecutive blank lines into 2 (one blank line separator)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse multiple spaces / tabs inside a line into a single space
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: overlapping character-based splitter
# ─────────────────────────────────────────────────────────────────────────────
def split_into_chunks(text: str, chunk_size: int, overlap: int):
    """
    Slides a window of `chunk_size` characters over `text`,
    stepping forward by (chunk_size - overlap) each time.

    The window prefers to break at the nearest sentence-ending
    punctuation so chunks don't cut words in half.

    Returns a list of non-empty string chunks.
    """
    step   = max(1, chunk_size - overlap)   # how far we advance each iteration
    chunks = []
    start  = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        # ── Soft boundary: try to end on a sentence break ─────────────────
        if end < len(text):
            # Search backwards from `end` for a good break point
            # (period, exclamation, question mark, or a blank-line transition)
            search_window = text[start:end]
            # Find last occurrence of a sentence terminator in the window
            match = None
            for pattern in (r"[.!?]\s", r"\n\n"):
                for m in re.finditer(pattern, search_window):
                    match = m   # keep updating — we want the LAST match
                if match:
                    break
            if match:
                end = start + match.end()   # snap end to after the terminator

        chunk = text[start:end].strip()

        if len(chunk) >= MIN_CHUNK_LEN:
            chunks.append(chunk)

        start += step

    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# Main processing loop
# ─────────────────────────────────────────────────────────────────────────────
txt_files = sorted(INPUT_DIR.glob("*.txt"))

if not txt_files:
    print("No .txt files found in rag_data/extracted_text/. Nothing to do.")
    sys.exit(0)

print(f"Found {len(txt_files)} text file(s) to process:\n")

all_chunks      = []   # will hold every chunk dict across all files
global_chunk_no = 1    # running counter for chunk_id across all documents

for txt_path in txt_files:
    print(f"  {txt_path.name}")

    try:
        raw_text   = txt_path.read_text(encoding="utf-8")
        clean      = clean_text(raw_text)
        doc_chunks = split_into_chunks(clean, CHUNK_SIZE, CHUNK_OVERLAP)

        for i, chunk_text in enumerate(doc_chunks):
            all_chunks.append({
                "chunk_id":    f"chunk_{global_chunk_no:04d}",
                "source_file": txt_path.name,
                "chunk_index": i,
                "text":        chunk_text,
            })
            global_chunk_no += 1

        print(f"    → {len(doc_chunks)} chunk(s) created")

    except Exception as exc:
        print(f"    ERROR processing {txt_path.name}: {exc}")

# ── Save to JSON ──────────────────────────────────────────────────────────────
OUTPUT_FILE.write_text(
    json.dumps(all_chunks, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("Chunking complete.")
print(f"  Files processed : {len(txt_files)}")
print(f"  Total chunks    : {len(all_chunks)}")
print(f"  Output file     : {OUTPUT_FILE}")
print()
print(" Breakdown per source file:")
from collections import Counter
counts = Counter(c["source_file"] for c in all_chunks)
for fname, n in sorted(counts.items()):
    print(f"    {fname:45s}  {n:4d} chunk(s)")
print("=" * 60)
print()
print("Next step → Step 3: Embed each chunk using a sentence")
print("transformer and store vectors in a FAISS index.")
