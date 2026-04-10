"""
Vector Store — persistent local Qdrant (no separate process needed)
────────────────────────────────────────────────────────────────────
Uses QdrantClient in local/embedded mode: vectors are stored in
data/qdrant_storage/ and persist across restarts automatically.

No qdrant.exe process required. No port 6333 needed.
Falls back to remote Qdrant if USE_LOCAL_QDRANT=false.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)

# client = QdrantClient(
#     host="localhost",
#     port=6333
# )

class VectorStore:
    """Persistent vector storage using embedded local Qdrant."""

    def __init__(
        self,
        local_path: str | None = None,
        host: str | None = None,
        port: int = 6333,
        collection_name: str = "regdoc_collection",
        vector_size: int = 384, 
        use_local: bool = True,
    ) -> None:
        self._collection  = collection_name
        self._vector_size = vector_size
        self._client: QdrantClient | None = None

        # Resolve config from args or environment
        from pathlib import Path as _P
        import os

        if use_local or os.getenv("USE_LOCAL_QDRANT", "true").lower() == "true":
            path = local_path or os.getenv(
                "QDRANT_LOCAL_PATH",
                str(_P(__file__).resolve().parent.parent / "data" / "qdrant_storage")
            )
            _P(path).mkdir(parents=True, exist_ok=True)
            self._mode  = "local"
            self._path  = path
            self._host  = None
            self._port  = None
        else:
            self._mode  = "remote"
            self._path  = None
            self._host  = host or os.getenv("QDRANT_HOST", "localhost")
            self._port  = port

    # ── Client ────────────────────────────────────────────────────────────────

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            if self._mode == "local":
                self._client = QdrantClient(path=self._path)
                logger.info("Qdrant LOCAL mode — storage: %s", self._path)
            else:
                self._client = QdrantClient(host=self._host, port=self._port)
                logger.info("Qdrant REMOTE mode — %s:%s", self._host, self._port)
        return self._client

    # ── Collection ────────────────────────────────────────────────────────────

    def ensure_collection(self) -> None:
        existing = [c.name for c in self.client.get_collections().collections]
        if self._collection not in existing:
            self.client.create_collection(
                collection_name=self._collection,
                vectors_config=qmodels.VectorParams(
                    size=self._vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            logger.info("Created collection '%s'", self._collection)

    # ── Upsert ────────────────────────────────────────────────────────────────

    def upsert_chunks(
        self,
        chunks: list[str],
        vectors: list[list[float]],
        source_filename: str,
    ) -> int:
        self.ensure_collection()
        points = [
            qmodels.PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={"text": chunk, "source": source_filename},
            )
            for chunk, vec in zip(chunks, vectors)
        ]
        self.client.upsert(collection_name=self._collection, points=points)
        logger.info("Upserted %d chunks from '%s'", len(points), source_filename)
        return len(points)

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query_vector: list[float], top_k: int = 10) -> list[dict[str, Any]]:
        self.ensure_collection()
        response = self.client.query_points(
            collection_name=self._collection,
            query=query_vector,
            limit=top_k,
            with_payload=True,
        )
        results = response.points
        return [
            {"text": r.payload.get("text",""), "source": r.payload.get("source",""), "score": r.score}
            for r in results
        ]

    # ── Info ──────────────────────────────────────────────────────────────────

    def collection_info(self) -> dict[str, Any]:
        self.ensure_collection()
        info = self.client.get_collection(self._collection)
        return {
            "name":         self._collection,
            "points_count": info.points_count,
            "vector_count": info.vectors_count,
            "status":       str(info.status),
            "storage_mode": self._mode,
            "storage_path": self._path or f"{self._host}:{self._port}",
        }

    def get_indexed_sources(self) -> list[str]:
        """Return list of unique source filenames stored in the collection."""
        self.ensure_collection()
        sources = set()
        offset = None
        while True:
            records, offset = self.client.scroll(
                collection_name=self._collection,
                scroll_filter=None,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for r in records:
                src = r.payload.get("source", "")
                if src:
                    sources.add(src)
            if offset is None:
                break
        return sorted(sources)
