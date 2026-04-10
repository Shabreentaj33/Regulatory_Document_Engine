"""
MCP Server — Retrieval only.
Embeds the query, searches Qdrant, returns context chunks.
LLM generation is handled by Claude (connected via MCP in Claude desktop config).
"""
from __future__ import annotations

import requests
from backend.config import MODEL_SERVICE_URL

_vector_store = None


def init(vs) -> None:
    """Inject the shared VectorStore instance from main.py."""
    global _vector_store
    _vector_store = vs


def embed_query(query: str) -> list[float]:
    resp = requests.post(
        f"{MODEL_SERVICE_URL}/embed",
        json={"texts": [query]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["vectors"][0]


def qdrant_search(query: str, top_k: int = 5) -> list[str]:
    if _vector_store is None:
        raise RuntimeError("mcpserver not initialized — call mcpserver.init(vs) first.")
    query_vector = embed_query(query)
    results = _vector_store.search(query_vector, top_k)
    return [r["text"].strip() for r in results if r["text"]]


def mcp_qa(query: str) -> str:
    """
    Retrieval pipeline for MCP.
    Returns the retrieved context as a structured string.
    Claude (connected via MCP) handles the final answer generation.
    """
    context_chunks = qdrant_search(query)

    if not context_chunks:
        return "No relevant information found in the uploaded documents."

    # Return context so Claude can reason over it
    formatted = "\n\n---\n\n".join(
        f"[Chunk {i+1}]\n{chunk}" for i, chunk in enumerate(context_chunks)
    )
    return formatted