# 🏥 Clinical & Regulatory Intelligence Platform

Enterprise-grade AI platform for automated compliance analysis and intelligent
question answering over regulatory pharmaceutical documents.

**No Docker required** — runs entirely as local Python processes.

---

## Architecture

```
Streamlit UI  (port 8501)
      │
      ▼
FastAPI Backend  (port 8000)
      │
      ├──► Qdrant Vector DB  (port 6333)   ← local binary
      │
      └──► Model Service  (port 9000)
                ├── all-MiniLM-L6-v2       (embeddings, 384-dim)
                ├── distilbart-cnn-12-6    (summarisation)
                └── google/flan-t5-large   (generative QA)
```

---

## Project Structure

```
clinical-platform/
├── backend/
│   ├── config.py              # All configuration constants
│   ├── document_processor.py  # PDF extraction, chunking, section detection
│   ├── compliance_engine.py   # Regulatory compliance checks
│   ├── vector_store.py        # Qdrant wrapper
│   ├── rag_engine.py          # RAG pipeline
│   └── main.py                # FastAPI application
├── model_service/
│   └── model_service.py       # ML inference service
├── frontend/
│   └── app.py                 # Streamlit dashboard
├── data/uploads/              # Uploaded PDFs (auto-created)
├── qdrant_bin/                # Qdrant binary (auto-downloaded)
├── qdrant_data/               # Qdrant persistent storage (auto-created)
├── requirements.txt
├── setup.py                   # One-time setup script
├── start.py                   # Unified process launcher
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.10+ (https://python.org)
- ~6 GB free RAM  
- ~5 GB free disk (model weights, downloaded once)
- Internet connection for first run

### Step 1 — One-time setup

```bash
cd clinical-platform
python setup.py
```

Installs all deps, downloads the Qdrant binary, creates directories.

### Step 2 — Launch everything

```bash
python start.py
```

| Service       | URL                             | Notes                          |
|---------------|---------------------------------|--------------------------------|
| Qdrant        | http://localhost:6333/dashboard | Vector database                |
| Model Service | http://localhost:9000/docs      | First run: ~5-15 min download  |
| Backend API   | http://localhost:8000/docs      | FastAPI + RAG                  |
| **Dashboard** | **http://localhost:8501**       | Open this in your browser      |

Press **Ctrl-C** to stop all services.

---

## Individual Service Start

```bash
python start.py --only qdrant
python start.py --only model
python start.py --only backend
python start.py --only frontend
```

Or manually:

```bash
python -m uvicorn model_service.model_service:app --port 9000
python -m uvicorn backend.main:app --port 8000
streamlit run frontend/app.py
```

---

## Windows Notes

- Run from PowerShell or Command Prompt
- Allow firewall access when Qdrant starts
- ANSI colours work on Windows 10 build 1903+ and Windows 11

## macOS Notes

If Gatekeeper blocks the Qdrant binary:
```bash
xattr -d com.apple.quarantine qdrant_bin/qdrant
chmod +x qdrant_bin/qdrant
```

---

## API Reference

**Backend (port 8000)**

| Method | Endpoint | Description                        |
|--------|----------|------------------------------------|
| GET    | /health  | Liveness check                     |
| GET    | /stats   | Vector store statistics            |
| POST   | /upload  | Ingest PDF files                   |
| POST   | /chat    | RAG question answering             |

**Model Service (port 9000)**

| Method | Endpoint   | Description                    |
|--------|------------|--------------------------------|
| GET    | /health    | Model load status              |
| POST   | /embed     | Sentence embeddings (384-dim)  |
| POST   | /summarize | Abstractive summarisation      |
| POST   | /generate  | FLAN-T5-Large generation       |

---

## Compliance Checks

| Check                        | Severity |
|------------------------------|----------|
| Missing required section     | HIGH     |
| Insufficient warnings text   | HIGH     |
| Missing numeric dosage units | HIGH     |
| Ambiguous dosage language    | MEDIUM   |
| Sparse contraindications     | MEDIUM   |
| Unspecified storage temp     | MEDIUM   |
| Missing adverse incidence %  | LOW      |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Slow first start | Normal — FLAN-T5-Large downloads ~3 GB |
| `ModuleNotFoundError` | Re-run `python setup.py` |
| Qdrant not found | Re-run `python setup.py` |
| Port in use | Kill conflicting process or edit ports in `start.py` |
| Out of memory | FLAN-T5-Large needs ~5 GB RAM; close other apps |
| macOS blocked binary | `xattr -d com.apple.quarantine qdrant_bin/qdrant` |