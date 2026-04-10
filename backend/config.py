"""
Configuration settings for the Clinical & Regulatory Intelligence Platform.
Optimized for Ollama + Qdrant RAG pipeline.
"""

import os

# ── Model Service (Ollama-based) ──────────────────────────────────────────────
MODEL_SERVICE_URL: str = os.getenv("MODEL_SERVICE_URL", "http://127.0.0.1:9000")

# Ollama direct (used internally if needed)
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")

# Models (aligned with your system)
EMBEDDING_MODEL: str = "nomic-embed-text"
LLM_MODEL: str = "llama3:8b"

# ── Qdrant (Vector DB) ────────────────────────────────────────────────────────
QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))

COLLECTION_NAME: str = "regdoc_collection"

# MUST match embedding model dimension (nomic-embed-text = 768)
VECTOR_SIZE: int = 768

# Distance metric (important for retrieval quality)
DISTANCE_METRIC: str = "cosine"

# ── Document Processing ───────────────────────────────────────────────────────
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "data/uploads")

# Optimized chunking for RAG
CHUNK_SIZE: int = 350          # slightly tighter → better semantic precision
CHUNK_OVERLAP: int = 75        # preserves context continuity

# Max input length sent to LLM (avoid overload)
MAX_CONTEXT_CHARS: int = 4000

# ── RAG Pipeline ──────────────────────────────────────────────────────────────

# Retrieval (higher recall)
TOP_K_RETRIEVE: int = 8

# After reranking (precision stage)
TOP_K_RERANK: int = 4

# Reranker (optional but recommended)
RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Enable/disable reranking (good for debugging)
USE_RERANKER: bool = True

# Score threshold to filter weak matches
MIN_SIMILARITY_SCORE: float = 0.2

# ── Generation Controls ───────────────────────────────────────────────────────
MAX_TOKENS: int = 300
TEMPERATURE: float = 0.1   # low = factual (important for regulatory domain)

# ── Regulatory Sections ───────────────────────────────────────────────────────
REQUIRED_SECTIONS: list[str] = [
    "indications",
    "dosage",
    "contraindications",
    "warnings",
    "adverse reactions",
    "storage",
]

SECTION_ALIASES: dict[str, list[str]] = {
    "indications": [
        "indication", "intended use", "use", "indication and usage"
    ],
    "dosage": [
        "dose", "dosage and administration", "administration", "dosing"
    ],
    "contraindications": [
        "contraindication", "contra-indications"
    ],
    "warnings": [
        "warning", "precaution", "precautions", "warnings and precautions"
    ],
    "adverse reactions": [
        "adverse reaction", "side effect", "side effects", "undesirable effects"
    ],
    "storage": [
        "store", "storage conditions", "how to store", "keeping"
    ],
}