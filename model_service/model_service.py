"""
Model Service — Embeddings Only
--------------------------------
Provides sentence embeddings via all-MiniLM-L6-v2.
LLM generation is handled externally (Claude via MCP).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent
MODEL_CACHE = Path(os.environ.get("MODEL_CACHE", str(_ROOT / "data" / "models")))
MODEL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("TRANSFORMERS_CACHE", str(MODEL_CACHE))
os.environ.setdefault("HF_HOME", str(MODEL_CACHE))

EMBED_MODEL = "all-MiniLM-L6-v2"

_embed_model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _embed_model
    logger.info("Loading embedding model: %s", EMBED_MODEL)
    try:
        _embed_model = SentenceTransformer(EMBED_MODEL, cache_folder=str(MODEL_CACHE))
        logger.info("✅ Embedding model loaded")
    except Exception as exc:
        raise RuntimeError(f"Failed to load embedding model: {exc}") from exc
    yield
    _embed_model = None
    logger.info("Model service shut down.")


app = FastAPI(title="Model Service (Embedding Only)", lifespan=lifespan)


class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    vectors: list[list[float]]


@app.get("/health")
def health():
    return {
        "status": "ok" if _embed_model else "loading",
        "embedding_model": EMBED_MODEL,
    }


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest):
    if not req.texts:
        raise HTTPException(400, "texts cannot be empty")
    if _embed_model is None:
        raise HTTPException(503, "Embedding model not loaded yet")
    try:
        vectors = _embed_model.encode(req.texts, convert_to_numpy=True)
        return {"vectors": vectors.tolist()}
    except Exception as exc:
        logger.exception("Embedding failed")
        raise HTTPException(500, str(exc))

