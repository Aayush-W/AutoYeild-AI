"""
RAG Pipeline - Step 4: Query Embedding + FAISS Retrieval
==========================================================
Given a user query string:
  1. Embed it with the same sentence-transformer model used at index time.
  2. Search the FAISS index for the top-k nearest vectors.
  3. Map each result back to its original chunk text + metadata.
  4. Return structured results ready for Step 5 (LLM prompting).

  ── Score note ────────────────────────────────────────────────────────────
  Step 3 built an IndexFlatIP (Inner Product) index on L2-NORMALISED vectors.
  Inner-product on normalised vectors == cosine similarity.
  Score range : -1.0  →  +1.0
  Interpretation : HIGHER score = MORE similar = BETTER match.
  ─────────────────────────────────────────────────────────────────────────

Usage (command-line):
    python scripts/rag/search_faiss_index.py
    python scripts/rag/search_faiss_index.py --query "wafer edge defect" --top_k 5

Usage (import into FastAPI / another module):
    from scripts.rag.search_faiss_index import load_index_and_metadata, embed_query, search_index
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ── Try importing required libraries ─────────────────────────────────────────
try:
    import faiss
except ImportError:
    print("ERROR: faiss-cpu not installed. Run: pip install faiss-cpu")
    sys.exit(1)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("ERROR: sentence-transformers not installed. Run: pip install sentence-transformers")
    sys.exit(1)

# ── Configuration ─────────────────────────────────────────────────────────────
EMBEDDING_MODEL  = "all-MiniLM-L6-v2"  # must match the model used in Step 3
DEFAULT_TOP_K    = 5
PREVIEW_CHARS    = 300                  # characters to show in the text preview

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT   = Path(__file__).resolve().parents[2]
PROCESSED_DIR  = PROJECT_ROOT / "rag_data" / "processed"
FAISS_PATH     = PROCESSED_DIR / "faiss_index.bin"
METADATA_PATH  = PROCESSED_DIR / "chunk_metadata.json"


# ─────────────────────────────────────────────────────────────────────────────
# Function 1: load_index_and_metadata
# ─────────────────────────────────────────────────────────────────────────────
def load_index_and_metadata(
    faiss_path: Path = FAISS_PATH,
    metadata_path: Path = METADATA_PATH,
) -> Tuple[Any, List[Dict]]:
    """
    Load the FAISS index and aligned metadata from disk.

    Returns:
        (faiss_index, metadata_list)
    Raises:
        FileNotFoundError  if either file is missing.
        ValueError         if the lengths do not match.
    """
    if not faiss_path.exists():
        raise FileNotFoundError(
            f"FAISS index not found: {faiss_path}\n"
            "Please run scripts/rag/build_faiss_index.py (Step 3) first."
        )
    if not metadata_path.exists():
        raise FileNotFoundError(
            f"Metadata file not found: {metadata_path}\n"
            "Please run scripts/rag/build_faiss_index.py (Step 3) first."
        )

    index    = faiss.read_index(str(faiss_path))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    if len(metadata) != index.ntotal:
        raise ValueError(
            f"Mismatch: FAISS index has {index.ntotal} vectors "
            f"but metadata has {len(metadata)} entries.\n"
            "Re-run scripts/rag/build_faiss_index.py to rebuild both together."
        )

    return index, metadata


# ─────────────────────────────────────────────────────────────────────────────
# Function 2: embed_query
# ─────────────────────────────────────────────────────────────────────────────
def embed_query(
    query: str,
    model: SentenceTransformer,
) -> np.ndarray:
    """
    Convert a plain-text query into a normalised float32 embedding vector.

    The vector is L2-normalised so it is compatible with the IndexFlatIP
    (cosine similarity) index built in Step 3.

    Returns:
        numpy array of shape (1, embedding_dim)
    """
    query = query.strip()
    if not query:
        raise ValueError("Query string is empty.")

    embedding = model.encode(
        [query],
        normalize_embeddings=True,  # must match Step 3
        convert_to_numpy=True,
    )
    return embedding.astype("float32")   # FAISS requires float32


# ─────────────────────────────────────────────────────────────────────────────
# Function 3: search_index
# ─────────────────────────────────────────────────────────────────────────────
def search_index(
    query_embedding: np.ndarray,
    index: Any,
    metadata: List[Dict],
    top_k: int = DEFAULT_TOP_K,
) -> List[Dict]:
    """
    Search the FAISS index with the query embedding and return the top-k results.

    Returns a list of dicts, each containing:
        rank, score, chunk_id, source_file, chunk_index, text
    """
    top_k = min(top_k, index.ntotal)   # can't ask for more than what exists
    scores, indices = index.search(query_embedding, top_k)

    results = []
    for rank, (faiss_idx, score) in enumerate(
        zip(indices[0], scores[0]), start=1
    ):
        if faiss_idx == -1:
            # FAISS returns -1 when it can't find enough results
            continue

        chunk = metadata[faiss_idx]
        results.append({
            "rank":        rank,
            "score":       round(float(score), 4),   # cosine similarity
            "chunk_id":    chunk["chunk_id"],
            "source_file": chunk["source_file"],
            "chunk_index": chunk["chunk_index"],
            "text":        chunk["text"],
        })

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Function 4: format_results
# ─────────────────────────────────────────────────────────────────────────────
def format_results(results: List[Dict], query: str, preview_chars: int = PREVIEW_CHARS) -> str:
    """
    Pretty-print retrieval results to the terminal.
    """
    lines = []
    lines.append("\n" + "=" * 64)
    lines.append(f"  Query : \"{query}\"")
    lines.append(f"  Hits  : {len(results)}")
    lines.append("=" * 64)

    for r in results:
        text_preview = r["text"][:preview_chars].replace("\n", " ").strip()
        if len(r["text"]) > preview_chars:
            text_preview += " …"

        lines.append(
            f"\n  [{r['rank']}]  score={r['score']:.4f}  |  "
            f"{r['source_file']}  (chunk #{r['chunk_index']})"
        )
        lines.append(f"       {r['chunk_id']}")
        lines.append(f"       \"{text_preview}\"")

    lines.append("\n" + "=" * 64 + "\n")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# High-level helper: retrieve()
# Combines all four functions — easy to import into FastAPI
# ─────────────────────────────────────────────────────────────────────────────

# Module-level cache so the model / index are loaded only once per process
_cache: Dict = {}

def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    model_name: str = EMBEDDING_MODEL,
) -> List[Dict]:
    """
    One-call retrieval suitable for FastAPI route handlers.

    Loads the model and index on first call, then caches them in memory.
    Returns a list of result dicts (rank, score, chunk_id, source_file,
    chunk_index, text).
    """
    global _cache

    # Load on first call
    if not _cache:
        print("  [retriever] Loading FAISS index and metadata …")
        _cache["index"], _cache["metadata"] = load_index_and_metadata()
        print(f"  [retriever] Loading embedding model: {model_name} …")
        _cache["model"] = SentenceTransformer(model_name)
        print("  [retriever] Ready.\n")

    query_emb = embed_query(query, _cache["model"])
    return search_index(query_emb, _cache["index"], _cache["metadata"], top_k)


# ─────────────────────────────────────────────────────────────────────────────
# Command-line entry point
# ─────────────────────────────────────────────────────────────────────────────
def _cli():
    parser = argparse.ArgumentParser(
        description="RAG Step 4 — FAISS retrieval test"
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Query string to search. If omitted, runs three built-in demo queries.",
    )
    parser.add_argument(
        "--top_k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Number of results to return (default: {DEFAULT_TOP_K})",
    )
    args = parser.parse_args()

    # ── Load resources ────────────────────────────────────────────────────────
    print("Loading FAISS index …")
    index, metadata = load_index_and_metadata()
    print(f"  Index vectors : {index.ntotal}")
    print(f"  Metadata rows : {len(metadata)}")

    print(f"\nLoading embedding model: {EMBEDDING_MODEL} …")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("  Model ready.\n")

    # ── Decide which queries to run ───────────────────────────────────────────
    if args.query:
        queries = [args.query]
    else:
        # Built-in demo queries representative of AutoYield AI use cases
        queries = [
            "diffuse low confidence wafer defect contamination",
            "edge ring lithography defect process variation",
            "manual review uncertain classification drift",
        ]

    # ── Run each query ────────────────────────────────────────────────────────
    for query in queries:
        try:
            q_emb    = embed_query(query, model)
            results  = search_index(q_emb, index, metadata, top_k=args.top_k)
            print(format_results(results, query))
        except ValueError as exc:
            print(f"Skipping query — {exc}")


if __name__ == "__main__":
    _cli()
