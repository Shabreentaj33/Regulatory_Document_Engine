"""
Clinical & Regulatory Intelligence Platform — Backend API
with Full Persistent Memory (SQLite + embedded Qdrant)
"""
from __future__ import annotations
# from backend.dependencies import vector_store as _vector_store
import importlib.util, logging, sys
from pathlib import Path
from typing import Any, List
from backend.mcpserver import mcp_qa   

# ── Self-healing path setup ───────────────────────────────────────────────────
_BDIR = Path(__file__).resolve().parent
_ROOT = _BDIR.parent
for _p in [str(_ROOT), str(_BDIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_cfg = _load("_cfg",  _BDIR / "config.py")
_dp  = _load("_dp",   _BDIR / "document_processor.py")
_ce  = _load("_ce",   _BDIR / "compliance_engine.py")
_vs  = _load("_vs",   _BDIR / "vector_store.py")
# _re  = _load("_re",   _BDIR / "rag_engine.py")
_mem = _load("_mem",  _BDIR / "memory.py")

DocumentProcessor = _dp.DocumentProcessor
ComplianceEngine  = _ce.ComplianceEngine
VectorStore       = _vs.VectorStore
# RAGEngine         = _re.RAGEngine
PersistentMemory  = _mem.PersistentMemory
MODEL_SERVICE_URL = _cfg.MODEL_SERVICE_URL
UPLOAD_DIR        = _cfg.UPLOAD_DIR
print("load done")
# ─────────────────────────────────────────────────────────────────────────────
import requests
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Clinical & Regulatory Intelligence Platform", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Singletons ────────────────────────────────────────────────────────────────
# ── Singletons ────────────────────────────────────────────────────────────────
_processor    = DocumentProcessor()
_compliance   = ComplianceEngine()
_vector_store = VectorStore()          # single instance, exclusive lock owner
_memory       = PersistentMemory(db_path=str(_ROOT / "data" / "memory.db"))

# ✅ Inject the shared instance into mcpserver — prevents double-lock
from backend import mcpserver as _mcpserver
_mcpserver.init(_vector_store)
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
logger.info("Backend ready | root=%s | uploads=%s", _ROOT, UPLOAD_DIR)
print("app done")
# ── Schemas ───────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str
    session_id: str = "default"

class ChatResponse(BaseModel):
    answer: str
    citations: List[str]
    sources: List[str]

class ClearHistoryRequest(BaseModel):
    session_id: str = "default"
print("schemas done")
# ── Helpers ───────────────────────────────────────────────────────────────────
def _embed(texts):
    r = requests.post(f"{MODEL_SERVICE_URL}/embed", json={"texts": texts}, timeout=60)
    r.raise_for_status()
    return r.json()["vectors"]


def _summarize(text: str) -> str:
    """Improved extractive summary with better coverage."""
    
    if not text or not text.strip():
        return "No content could be extracted from this document."

    import re
    
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    # Clean sentences
    sentences = [s.strip() for s in sentences if len(s.strip()) > 40]

    if not sentences:
        return text[:1000]

    # Score sentences based on keywords (domain-aware)
    keywords = [
        "indication", "dosage", "warning", "contraindication",
        "adverse", "reaction", "storage", "treatment", "use"
    ]

    scored = []
    for s in sentences:
        score = sum(1 for k in keywords if k.lower() in s.lower())
        scored.append((score, s))

    # Sort by importance
    scored.sort(reverse=True, key=lambda x: x[0])

    # Pick top sentences (coverage-based)
    top_sentences = [s for _, s in scored[:15]]

    # Maintain original order
    ordered_summary = [s for s in sentences if s in top_sentences]

    summary = " ".join(ordered_summary)

    return summary[:2000]
# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "version": "2.0.0"}
print("routes done")
@app.get("/health")
async def health():
    try:
        r = requests.get(f"{MODEL_SERVICE_URL}/health", timeout=5)
        ms = "ok" if r.status_code == 200 else "error"
    except Exception:
        ms = "unreachable"
    try:
        _vector_store.ensure_collection(); vs = "ok"
    except Exception:
        vs = "unreachable"
    return {"status": "ok", "model_service": ms, "vector_store": vs}
print("health done")
@app.get("/routes")
async def list_routes():
    return {"routes": [r.path for r in app.routes]}

@app.get("/stats")
async def stats():
    mem  = _memory.stats()
    try:   vs = _vector_store.collection_info()
    except Exception: vs = {}
    return {"memory": mem, "vector_store": vs}
print("stats done")
# ── Persistent document registry ──────────────────────────────────────────────

@app.get("/documents")
async def get_documents():
    """Return all previously uploaded documents from persistent memory."""
    docs = _memory.load_all_documents()
    # Also get which sources are indexed in Qdrant
    try:
        indexed = set(_vector_store.get_indexed_sources())
    except Exception:
        indexed = set()
    for doc in docs:
        doc["indexed_in_qdrant"] = doc["filename"] in indexed
    return docs

@app.delete("/documents/{filename}")
async def delete_document(filename: str):
    """Remove a document from memory and Qdrant."""
    _memory.delete_document(filename)
    return {"deleted": filename}
print("documents done")
# ── Upload ────────────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_documents(files: List[UploadFile] = File(...)) -> List[dict]:
    valid = [f for f in files if f and f.filename]
    if not valid:
        raise HTTPException(422, "No valid files received.")
    logger.info("/upload — %d file(s)", len(valid))
    results: List[dict] = []

    for upload in valid:
        filename = upload.filename or "unknown.pdf"
        save_path = Path(UPLOAD_DIR) / filename

        # Skip if already fully indexed
        if _memory.document_exists(filename):
            logger.info("Skipping already-indexed: %s", filename)
            existing = [d for d in _memory.load_all_documents() if d["filename"] == filename]
            if existing:
                results.append({**existing[0], "skipped": True,
                                 "message": "Already indexed — loaded from memory"})
                continue

        # Save file
        try:
            data = await upload.read()
            save_path.write_bytes(data)
        except Exception as exc:
            results.append({"filename": filename, "error": f"Save failed: {exc}"}); continue

        # Extract + analyse
        try:
            doc = _processor.process_document(save_path)
        except Exception as exc:
            results.append({"filename": filename, "error": f"Processing failed: {exc}"}); continue

        risks   = _compliance.run_checks(doc["sections"])
        summary = _summarize(doc["text"])

        # Embed + store in Qdrant
        chunks  = doc["chunks"]
        vectors: List[List[float]] = []
        if chunks:
            try:    vectors = _embed(chunks)
            except Exception as exc: logger.warning("Embed failed: %s", exc)

        stored = 0
        if vectors:
            try:    stored = _vector_store.upsert_chunks(chunks, vectors, filename)
            except Exception as exc: logger.error("Upsert failed: %s", exc)

        # Build sections for storage
        sections_out = {
            k: {"found": v["found"], "preview": v["content"][:200] if v["content"] else ""}
            for k, v in doc["sections"].items()
        }

        # Persist to SQLite
        _memory.save_document(
            filename=filename, summary=summary,
            sections=sections_out, risks=risks,
            chunks_stored=stored, char_count=doc["char_count"]
        )

        result = {
            "filename": filename, "summary": summary,
            "sections": sections_out, "risks": risks,
            "chunks_stored": stored, "char_count": doc["char_count"],
        }
        results.append(result)
        logger.info("Processed %s — %d chunks, %d risks", filename, stored, len(risks))

    return results
print("upload done")
# ── Chat with persistent history ──────────────────────────────────────────────
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> dict:
    if not req.query.strip():
        raise HTTPException(400, "Query cannot be empty.")

    # Save user message
    _memory.save_message(
        role="user",
        content=req.query,
        session_id=req.session_id
    )

    try:
        answer = mcp_qa(req.query)

        result = {
            "answer": answer,
            "citations": [],
            "sources": []
        }

    except Exception as exc:
        logger.error("MCP error: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))

    # Save assistant response
    _memory.save_message(
        role="assistant",
        content=result["answer"],
        citations=result.get("citations", []),
        sources=result.get("sources", []),
        session_id=req.session_id,
    )

    return result
@app.get("/chat/history")
async def get_chat_history(session_id: str = "default", limit: int = 200):
    """Return full persistent chat history for a session."""
    return _memory.load_chat_history(session_id=session_id, limit=limit)

@app.delete("/chat/history")
async def clear_chat_history(session_id: str = "default"):
    """Clear chat history for a session."""
    _memory.clear_chat_history(session_id=session_id)
    return {"cleared": True, "session_id": session_id}

@app.delete("/chat/history/all")
async def clear_all_chat_history():
    """Clear chat history for all sessions."""
    _memory.clear_all_chat_history()
    return {"cleared": True, "scope": "all"}

@app.get("/chat/sessions")
async def get_sessions():
    return {"sessions": _memory.get_all_sessions()}
print("chat done")