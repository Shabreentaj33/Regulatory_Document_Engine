"""
MCP Server — Retrieval only.
Embeds the query locally using sentence-transformers (no external service needed).
Searches Qdrant, returns context chunks.
LLM generation is handled by Claude via MCP.
"""
from __future__ import annotations

from sentence_transformers import SentenceTransformer

_vector_store = None
_model = None


def _get_model() -> SentenceTransformer:
    """Load model once and reuse."""
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def init(vs) -> None:
    """Inject the shared VectorStore instance."""
    global _vector_store
    _vector_store = vs


def embed_query(query: str) -> list[float]:
    model = _get_model()
    embedding = model.encode(query, normalize_embeddings=True)
    return embedding.tolist()


def qdrant_search(query: str, top_k: int = 5) -> list[str]:
    if _vector_store is None:
        raise RuntimeError("mcpserver not initialized — call mcpserver.init(vs) first.")
    query_vector = embed_query(query)
    results = _vector_store.search(query_vector, top_k)
    return [r["text"].strip() for r in results if r["text"]]


def mcp_qa(query: str) -> str:
    """
    Retrieval pipeline for MCP.
    Returns retrieved context as a structured string.
    Claude handles final answer generation.
    """
    context_chunks = qdrant_search(query)

    if not context_chunks:
        return "No relevant information found in the uploaded documents."

    formatted = "\n\n---\n\n".join(
        f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(context_chunks)
    )
    return formatted
