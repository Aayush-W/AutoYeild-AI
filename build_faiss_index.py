"""
RAG Pipeline - Step 3: Embed Chunks + Build FAISS Index
=========================================================
Loads rag_data/processed/chunks.json, generates a
sentence-transformer embedding for every valid chunk,
builds a FAISS flat L2 index, and saves:

  rag_data/processed/faiss_index.bin
  rag_data/processed/chunk_metadata.json
  rag_data/processed/chunk_embeddings.npy

Dependencies (install once):
    pip install sentence-transformers faiss-cpu numpy
"""

import json
import sys
from pathlib import Path

import numpy as np

# ── Try importing the required libraries ─────────────────────────────────────
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("ERROR: sentence-transformers is not installed.")
    print("Run: pip install sentence-transformers")
    sys.exit(1)

try:
    import faiss
except ImportError:
    print("ERROR: faiss-cpu is not installed.")
    print("Run: pip install faiss-cpu")
    sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"   # fast, 384-dim, great for retrieval
MIN_TEXT_LENGTH  = 100                   # skip chunks shorter than this
MIN_ALPHA_RATIO  = 0.40                  # skip if <40 % of chars are letters

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).resolve().parent
PROCESSED_DIR  = BASE_DIR / "rag_data" / "processed"
CHUNKS_FILE    = PROCESSED_DIR / "chunks.json"
FAISS_FILE     = PROCESSED_DIR / "faiss_index.bin"
METADATA_FILE  = PROCESSED_DIR / "chunk_metadata.json"
EMBEDDINGS_FILE= PROCESSED_DIR / "chunk_embeddings.npy"

# ── Verify input ──────────────────────────────────────────────────────────────
if not CHUNKS_FILE.exists():
    print(f"ERROR: chunks.json not found at {CHUNKS_FILE}")
    print("Please complete Step 2 first (chunking).")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# Helper: decide whether to keep a chunk
# ─────────────────────────────────────────────────────────────────────────────
def is_useful_chunk(text: str) -> bool:
    """Return True if the chunk has enough real text content to be worth embedding."""
    stripped = text.strip()
    if len(stripped) < MIN_TEXT_LENGTH:
        return False
    # Check that at least MIN_ALPHA_RATIO of the characters are letters
    alpha_count = sum(1 for ch in stripped if ch.isalpha())
    if len(stripped) > 0 and (alpha_count / len(stripped)) < MIN_ALPHA_RATIO:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 1. Load chunks
# ─────────────────────────────────────────────────────────────────────────────
print("Loading chunks from:", CHUNKS_FILE)
raw_chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
print(f"  Total chunks loaded : {len(raw_chunks)}\n")

# ─────────────────────────────────────────────────────────────────────────────
# 2. Filter out junk chunks
# ─────────────────────────────────────────────────────────────────────────────
kept_chunks  = []
skipped      = 0

for chunk in raw_chunks:
    text = chunk.get("text", "")
    if is_useful_chunk(text):
        kept_chunks.append(chunk)
    else:
        skipped += 1

print(f"  Chunks kept    : {len(kept_chunks)}")
print(f"  Chunks skipped : {skipped}  (too short or non-alphabetic)")
print()

if not kept_chunks:
    print("ERROR: No valid chunks to embed. Check your chunks.json.")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# 3. Load the embedding model
# ─────────────────────────────────────────────────────────────────────────────
print(f"Loading embedding model: {EMBEDDING_MODEL}")
print("  (First run downloads ~90 MB — subsequent runs use the local cache)\n")
model = SentenceTransformer(EMBEDDING_MODEL)

# ─────────────────────────────────────────────────────────────────────────────
# 4. Generate embeddings
# ─────────────────────────────────────────────────────────────────────────────
texts = [chunk["text"] for chunk in kept_chunks]

print(f"Generating embeddings for {len(texts)} chunk(s) ...")
embeddings = model.encode(
    texts,
    batch_size=32,          # process 32 chunks at a time for memory efficiency
    show_progress_bar=True, # shows a live progress bar
    normalize_embeddings=True,  # L2-normalise so cosine ≈ dot-product in FAISS
    convert_to_numpy=True,
)

embeddings = np.array(embeddings, dtype="float32")
embed_dim  = embeddings.shape[1]

print(f"\n  Embedding shape : {embeddings.shape}")
print(f"  Embedding dim   : {embed_dim}\n")

# ─────────────────────────────────────────────────────────────────────────────
# 5. Build FAISS index
#    IndexFlatIP = exact inner-product search (equivalent to cosine similarity
#    when vectors are L2-normalised, which we did above)
# ─────────────────────────────────────────────────────────────────────────────
print("Building FAISS index ...")
index = faiss.IndexFlatIP(embed_dim)   # Inner Product (= cosine, after normalise)
index.add(embeddings)
print(f"  Vectors in index : {index.ntotal}")

# ─────────────────────────────────────────────────────────────────────────────
# 6. Save FAISS index
# ─────────────────────────────────────────────────────────────────────────────
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
faiss.write_index(index, str(FAISS_FILE))
print(f"  FAISS index saved → {FAISS_FILE}")

# ─────────────────────────────────────────────────────────────────────────────
# 7. Save metadata (aligned row-for-row with the FAISS index)
# ─────────────────────────────────────────────────────────────────────────────
metadata = [
    {
        "chunk_id":    chunk["chunk_id"],
        "source_file": chunk["source_file"],
        "chunk_index": chunk["chunk_index"],
        "text":        chunk["text"],
    }
    for chunk in kept_chunks
]
METADATA_FILE.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"  Metadata saved     → {METADATA_FILE}")

# ─────────────────────────────────────────────────────────────────────────────
# 8. Save raw embeddings (optional — useful for debugging)
# ─────────────────────────────────────────────────────────────────────────────
np.save(str(EMBEDDINGS_FILE), embeddings)
print(f"  Embeddings saved   → {EMBEDDINGS_FILE}")

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("Embedding + Indexing complete.")
print(f"  Total chunks loaded     : {len(raw_chunks)}")
print(f"  Chunks skipped (junk)   : {skipped}")
print(f"  Chunks embedded         : {len(kept_chunks)}")
print(f"  Embedding dimension     : {embed_dim}")
print(f"  FAISS index size        : {index.ntotal} vectors")
print()
print("  Output files:")
print(f"    {FAISS_FILE}")
print(f"    {METADATA_FILE}")
print(f"    {EMBEDDINGS_FILE}")
print("=" * 60)
print()
print("Next step → Step 4: Accept a user query, embed it with the")
print("same model, search the FAISS index, and retrieve top-K chunks.")
