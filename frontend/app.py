"""
Clinical & Regulatory Intelligence Platform — Frontend
Full persistent memory: documents + chat survive restarts.
"""
from __future__ import annotations
import os, time
from typing import Any
import requests
import streamlit as st

st.set_page_config(
    page_title="Clinical & Regulatory Intelligence Platform",
    page_icon="🏥", layout="wide", initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
:root{
    --page-bg:#f0f4f8;
    --page-text:#17324d;
    --page-heading:#0a2540;
    --muted-text:#526377;
    --card-bg:#ffffff;
    --card-heading:#102a43;
    --card-text:#243b53;
    --sidebar-bg-start:#0a2540;
    --sidebar-bg-end:#1a3a5c;
    --sidebar-text:#e8edf2;
    --sidebar-heading:#ffffff;
    --accent:#2563eb;
    --accent-dark:#1d4ed8;
}
.stApp {
    background-color: var(--page-bg);
    color: var(--page-text);
}
.stApp p, .stApp li, .stApp label, .stApp span, .stApp div {
    color: var(--page-text);
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
    color: var(--page-heading);
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg,var(--sidebar-bg-start),var(--sidebar-bg-end));
}
[data-testid="stSidebar"] * { color:var(--sidebar-text) !important; }
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4,
[data-testid="stSidebar"] h5,
[data-testid="stSidebar"] h6 { color:var(--sidebar-heading) !important; }
[data-testid="stSidebar"] .stButton>button {
    background:var(--accent);color:white !important;border:none;
    border-radius:8px;font-weight:600;width:100%;padding:.6rem;
}
[data-testid="stSidebar"] .stButton>button:hover{background:var(--accent-dark);}
.platform-header{background:linear-gradient(135deg,#0a2540,#1e40af);color:white;
    padding:1.5rem 2rem;border-radius:12px;margin-bottom:1.5rem;}
.platform-header h1{margin:0;font-size:1.6rem;font-weight:700;color:white !important;}
.platform-header p{margin:0;opacity:.88;font-size:.9rem;color:#dbeafe !important;}
.metric-card{background:var(--card-bg);border-radius:10px;padding:1.2rem 1.5rem;
    box-shadow:0 2px 8px rgba(0,0,0,.08);border-left:4px solid var(--accent);margin-bottom:1rem;
    color:var(--card-text);}
.metric-card h3{margin:0 0 .3rem;font-size:.85rem;color:var(--muted-text) !important;text-transform:uppercase;}
.metric-card .value{font-size:1.8rem;font-weight:700;color:var(--card-heading) !important;}
.section-found{background:#dcfce7;color:#166534;border-radius:20px;padding:2px 12px;
    font-size:.8rem;font-weight:600;display:inline-block;margin:2px;}
.section-missing{background:#fee2e2;color:#991b1b;border-radius:20px;padding:2px 12px;
    font-size:.8rem;font-weight:600;display:inline-block;margin:2px;}
.risk-HIGH{background:#fee2e2;border-left:4px solid #dc2626;border-radius:8px;padding:.8rem 1rem;margin:.4rem 0;color:#7f1d1d;}
.risk-MEDIUM{background:#fef3c7;border-left:4px solid #d97706;border-radius:8px;padding:.8rem 1rem;margin:.4rem 0;color:#78350f;}
.risk-LOW{background:#dbeafe;border-left:4px solid #2563eb;border-radius:8px;padding:.8rem 1rem;margin:.4rem 0;color:#1e3a8a;}
.chat-user{background:#2563eb;color:white;border-radius:12px 12px 4px 12px;
    padding:.8rem 1.2rem;margin:.5rem 0 .5rem auto;max-width:75%;}
.chat-bot{background:var(--card-bg);color:var(--card-text) !important;border-radius:12px 12px 12px 4px;
    padding:.8rem 1.2rem;margin:.5rem auto .5rem 0;max-width:90%;
    box-shadow:0 2px 6px rgba(0,0,0,.08);}
.citation-box{background:#f1f5f9;border-left:3px solid #94a3b8;border-radius:4px;
    padding:.5rem .8rem;margin-top:.4rem;font-size:.8rem;color:#475569;}
.doc-card{background:var(--card-bg);border-radius:10px;padding:1rem 1.2rem;
    box-shadow:0 2px 8px rgba(0,0,0,.07);margin-bottom:.8rem;
    border-left:4px solid var(--accent);color:var(--card-text);}
.status-ok{color:#16a34a;font-weight:600;}
.status-err{color:#dc2626;font-weight:600;}
.memory-badge{background:#e0f2fe;color:#0369a1;border-radius:20px;
    padding:2px 10px;font-size:.75rem;font-weight:600;}
.stAlert {
    color: var(--card-text);
}
.stTabs [data-baseweb="tab"] {
    color: var(--muted-text);
}
.stTabs [aria-selected="true"] {
    color: var(--page-heading) !important;
}
</style>""", unsafe_allow_html=True)

# ── Backend detection ─────────────────────────────────────────────────────────
PORTS = [8000, 8001, 9001]

import os
import requests

PORTS = [8000, 8001, 8002]

def find_backend() -> str | None:
    candidates = []

    # 1. ENV first
    env = os.environ.get("BACKEND_URL", "").rstrip("/")
    if env:
        candidates.append(env)

    # 2. Try both localhost and 127.0.0.1
    for port in PORTS:
        candidates.append(f"http://127.0.0.1:{port}")
        candidates.append(f"http://localhost:{port}")

    # 3. Test all candidates
    for url in candidates:
        try:
            print(f"Checking backend at: {url}")  # DEBUG
            res = requests.get(f"{url}/health", timeout=5)
            if res.status_code == 200:
                print(f"✅ Connected to backend: {url}")
                return url
        except Exception as e:
            print(f"❌ Failed: {url} | {e}")

    return None

# ── Session state init ────────────────────────────────────────────────────────
def _init():
    defaults = {
        "backend_url": None,
        "backend_checked": False,
        "chat_history": [],       # loaded from DB on startup
        "upload_results": [],     # loaded from DB on startup
        "memory_loaded": False,   # flag: have we loaded from DB yet?
        "session_id": "default",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()

# ── Connect to backend ────────────────────────────────────────────────────────
if not st.session_state["backend_checked"]:
    st.session_state["backend_url"] = find_backend()
    st.session_state["backend_checked"] = True
elif not st.session_state["backend_url"]:
    st.session_state["backend_url"] = find_backend()

BE = st.session_state["backend_url"]

# ── Load persistent memory from backend (runs once per session) ───────────────
def _load_memory_from_backend():
    """Fetch documents + chat history from backend DB and populate session state."""
    if not BE or st.session_state["memory_loaded"]:
        return
    try:
        # Load all previously uploaded documents
        docs_resp = requests.get(f"{BE}/documents", timeout=10)
        if docs_resp.status_code == 200:
            docs = docs_resp.json()
            if docs:
                st.session_state["upload_results"] = docs
                st.session_state["memory_loaded"] = True

        # Load persistent chat history
        chat_resp = requests.get(
            f"{BE}/chat/history",
            params={"session_id": st.session_state["session_id"], "limit": 200},
            timeout=10
        )
        if chat_resp.status_code == 200:
            rows = chat_resp.json()
            st.session_state["chat_history"] = [
                {
                    "role": r["role"],
                    "content": r["content"],
                    "citations": r.get("citations", []),
                    "sources": r.get("sources", []),
                }
                for r in rows
            ]
        st.session_state["memory_loaded"] = True
    except Exception:
        pass  # Backend not up yet — will retry on next rerun

if BE and not st.session_state["memory_loaded"]:
    _load_memory_from_backend()

# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🏥 Clinical Platform")

    # Connection status
    if BE:
        st.markdown(f'<span class="status-ok">● Connected</span><br><small>{BE}</small>',
                    unsafe_allow_html=True)
        # Memory badge
        docs_count = len(st.session_state["upload_results"])
        chat_count = len(st.session_state["chat_history"])
        st.markdown(
            f'<span class="memory-badge">💾 {docs_count} docs · {chat_count} messages stored</span>',
            unsafe_allow_html=True
        )
    else:
        st.markdown('<span class="status-err">● Backend not found</span>', unsafe_allow_html=True)
        st.caption("Start: python -m uvicorn backend.main:app --port 8000 --app-dir .")

    if st.button("🔄 Retry Connection"):
        st.session_state.update({"backend_url": None, "backend_checked": False, "memory_loaded": False})
        st.rerun()

    st.markdown("---")

    # Session selector
    st.markdown("### 💬 Session")
    sessions = ["default"]
    if BE:
        try:
            s = requests.get(f"{BE}/chat/sessions", timeout=5).json()
            sessions = s.get("sessions", ["default"]) or ["default"]
        except Exception: pass

    selected_session = st.selectbox(
        "Conversation session",
        options=sessions,
        index=sessions.index(st.session_state["session_id"])
            if st.session_state["session_id"] in sessions else 0,
        label_visibility="collapsed"
    )
    new_session = st.text_input("New session name", placeholder="e.g. drug_review_2026")
    if st.button("➕ Create / Switch"):
        sid = new_session.strip() or selected_session
        st.session_state["session_id"] = sid
        st.session_state["memory_loaded"] = False   # force reload
        st.rerun()

    if selected_session != st.session_state["session_id"]:
        st.session_state["session_id"] = selected_session
        st.session_state["memory_loaded"] = False
        st.rerun()

    st.markdown("---")

    # Upload
    st.markdown("### 📂 Upload Documents")
    st.caption("Previously uploaded docs load automatically on restart.")

    uploaded_files = st.file_uploader(
        "Select PDF files", type=["pdf"],
        accept_multiple_files=True, label_visibility="collapsed"
    )

    if st.button("🚀 Analyse Documents", disabled=not (uploaded_files and BE)):
        with st.spinner("Processing…"):
            files_payload = [
                ("files", (f.name, f.getvalue(), "application/pdf"))
                for f in uploaded_files
            ]
            try:
                resp = requests.post(f"{BE}/upload", files=files_payload, timeout=300)
                resp.raise_for_status()
                new_results = resp.json()
                # Merge with existing (avoid duplicates)
                existing_names = {r["filename"] for r in st.session_state["upload_results"]}
                for r in new_results:
                    if r.get("filename") not in existing_names:
                        st.session_state["upload_results"].append(r)
                    else:
                        # Update existing
                        st.session_state["upload_results"] = [
                            r if r.get("filename") == x["filename"] else x
                            for x in st.session_state["upload_results"]
                        ]
                skipped = sum(1 for r in new_results if r.get("skipped"))
                new_n   = len(new_results) - skipped
                msg = f"✅ {new_n} new document(s) processed"
                if skipped:
                    msg += f" · {skipped} already in memory"
                st.success(msg)
            except Exception as exc:
                st.error(f"Upload failed: {exc}")

    st.markdown("---")

    # Stats
    if BE:
        try:
            s = requests.get(f"{BE}/stats", timeout=5).json()
            mem = s.get("memory", {})
            vs  = s.get("vector_store", {})
            st.markdown(f"**DB:** {mem.get('documents_stored',0)} docs · "
                       f"{mem.get('messages_stored',0)} messages")
            st.markdown(f"**Vectors:** {vs.get('points_count',0)} chunks indexed")
        except Exception: pass

# ═════════════════════════════════════════════════════════════════════════════
# HEADER
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="platform-header">
    <div>
        <h1>🏥 Clinical &amp; Regulatory Intelligence Platform</h1>
        <p>Enterprise AI analysis · Persistent memory across restarts</p>
    </div>
</div>""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# TABS
# ═════════════════════════════════════════════════════════════════════════════
tab_summary, tab_audit, tab_copilot = st.tabs([
    "📋 Patient / Drug Summary", "🔍 Regulatory Audit", "💬 Clinical Copilot"
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
with tab_summary:
    results = st.session_state["upload_results"]

    if not results:
        if BE:
            st.info("👈 Upload regulatory PDF documents using the sidebar. "
                    "Previously uploaded documents will appear here automatically.", icon="ℹ️")
        else:
            st.warning("Backend not connected. Start the backend first.", icon="⚠️")
    else:
        # KPIs
        total_docs   = len(results)
        total_chunks = sum(r.get("chunks_stored", 0) for r in results)
        total_risks  = sum(len(r.get("risks", [])) for r in results)
        high_risks   = sum(1 for r in results for x in r.get("risks",[])
                          if x.get("severity") == "HIGH")

        c1,c2,c3,c4 = st.columns(4)
        for col, label, val, color in [
            (c1,"Documents",total_docs,"#2563eb"),
            (c2,"Indexed Chunks",total_chunks,"#2563eb"),
            (c3,"Compliance Issues",total_risks,"#2563eb"),
            (c4,"High Severity",high_risks,"#dc2626"),
        ]:
            col.markdown(
                f'<div class="metric-card"><h3>{label}</h3>'
                f'<div class="value" style="color:{color}">{val}</div></div>',
                unsafe_allow_html=True)

        st.markdown("---")

        for result in results:
            if "error" in result:
                st.error(f"**{result.get('filename')}** — {result['error']}")
                continue

            memory_tag = ""
            if result.get("skipped"):
                memory_tag = ' <span class="memory-badge">💾 From memory</span>'
            if result.get("indexed_in_qdrant") is False:
                memory_tag += ' <span style="color:#dc2626;font-size:.75rem;">⚠️ Not in vector index</span>'

            with st.expander(
                f"📄 {result['filename']}{memory_tag}", expanded=True
            ):
                col_a, col_b = st.columns([2,1])
                with col_a:
                    st.markdown("#### Executive Summary")
                    st.markdown(
                        f'<div class="doc-card">{result.get("summary","No summary.")}</div>',
                        unsafe_allow_html=True)
                    if result.get("uploaded_at"):
                        st.caption(f"Uploaded: {result['uploaded_at']}")

                with col_b:
                    st.markdown("#### Sections")
                    pills = ""
                    for sec, info in result.get("sections", {}).items():
                        found = info.get("found") if isinstance(info, dict) else False
                        cls = "section-found" if found else "section-missing"
                        icon = "✓" if found else "✗"
                        pills += f'<span class="{cls}">{icon} {sec.title()}</span>'
                    st.markdown(pills, unsafe_allow_html=True)

                    st.markdown("#### Stats")
                    st.markdown(
                        f"- **Chars:** {result.get('char_count',0):,}\n"
                        f"- **Chunks:** {result.get('chunks_stored',0)}\n"
                        f"- **Issues:** {len(result.get('risks',[]))}"
                    )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — AUDIT
# ─────────────────────────────────────────────────────────────────────────────
with tab_audit:
    results = st.session_state["upload_results"]
    if not results:
        st.info("Upload documents to view compliance audit.", icon="🔍")
    else:
        sev_filter = st.multiselect(
            "Filter by severity", ["HIGH","MEDIUM","LOW"],
            default=["HIGH","MEDIUM","LOW"]
        )
        all_risks = [
            {**r, "_source": res.get("filename","")}
            for res in results for r in res.get("risks",[])
        ]
        filtered = [r for r in all_risks if r.get("severity") in sev_filter]

        high_n = sum(1 for r in all_risks if r.get("severity")=="HIGH")
        med_n  = sum(1 for r in all_risks if r.get("severity")=="MEDIUM")
        low_n  = sum(1 for r in all_risks if r.get("severity")=="LOW")

        c1,c2,c3 = st.columns(3)
        c1.markdown(f'<div class="metric-card" style="border-left-color:#dc2626">'
                   f'<h3>🔴 High</h3><div class="value" style="color:#dc2626">{high_n}</div></div>',
                   unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card" style="border-left-color:#d97706">'
                   f'<h3>🟡 Medium</h3><div class="value" style="color:#d97706">{med_n}</div></div>',
                   unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card" style="border-left-color:#2563eb">'
                   f'<h3>🔵 Low</h3><div class="value" style="color:#2563eb">{low_n}</div></div>',
                   unsafe_allow_html=True)

        st.markdown("---")
        if not filtered:
            st.success("✅ No issues for selected severity levels.")
        else:
            st.markdown(f"### Findings ({len(filtered)})")
            for r in filtered:
                sev  = r.get("severity","LOW")
                icon = {"HIGH":"🔴","MEDIUM":"🟡","LOW":"🔵"}.get(sev,"🔵")
                st.markdown(
                    f'<div class="risk-{sev}"><strong>{icon} [{sev}] '
                    f'{r.get("type","")} — <em>{r.get("_source","")}</em></strong>'
                    f'<br>{r.get("message","")}</div>',
                    unsafe_allow_html=True)

        with st.expander("📊 Full Audit Log"):
            if all_risks:
                import pandas as pd
                df = pd.DataFrame([{
                    "Source":   r.get("_source",""),
                    "Severity": r.get("severity",""),
                    "Type":     r.get("type",""),
                    "Message":  r.get("message",""),
                } for r in all_risks])
                st.dataframe(df, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — COPILOT
# ─────────────────────────────────────────────────────────────────────────────
with tab_copilot:
    results = st.session_state["upload_results"]

    if not results:
        st.info("Upload documents first to use the Clinical Copilot.", icon="💬")
    else:
        sid = st.session_state["session_id"]

        # Persistent history notice
        if st.session_state["chat_history"]:
            st.markdown(
                f'<span class="memory-badge">💾 {len(st.session_state["chat_history"])} '
                f'messages restored from persistent memory · Session: <b>{sid}</b></span>',
                unsafe_allow_html=True
            )

        # Render chat
        for msg in st.session_state["chat_history"]:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-user">🧑‍⚕️ {msg["content"]}</div>',
                           unsafe_allow_html=True)
            else:
                formatted = msg["content"].replace("\n", "<br>")
                st.markdown(f'<div class="chat-bot">🤖 {formatted}</div>',
                           unsafe_allow_html=True)
                for i, cite in enumerate(msg.get("citations",[]), 1):
                    st.markdown(
                        f'<div class="citation-box">📌 <b>Citation {i}:</b> '
                        f'{cite[:300]}{"…" if len(cite)>300 else ""}</div>',
                        unsafe_allow_html=True)
                if msg.get("sources"):
                    st.caption("📄 Sources: " + ", ".join(f"*{s}*" for s in msg["sources"]))

        # Input row
        col_q, col_btn = st.columns([5,1])
        with col_q:
            user_q = st.text_input(
                "Question", key="chat_input",
                placeholder="e.g. What are the contraindications?",
                label_visibility="collapsed"
            )
        with col_btn:
            send = st.button("Send ➤", disabled=not BE)

        if send and user_q.strip():
            st.session_state["chat_history"].append(
                {"role":"user","content":user_q,"citations":[],"sources":[]})
            with st.spinner("Searching documents…"):
                try:
                    resp = requests.post(
                        f"{BE}/chat",
                        json={"query": user_q, "session_id": sid},
                        timeout=120
                    )
                    resp.raise_for_status()
                    d = resp.json()
                    answer    = d.get("answer","No answer.")
                    citations = d.get("citations",[])
                    sources   = d.get("sources",[])
                except Exception as exc:
                    answer, citations, sources = f"⚠️ Error: {exc}", [], []

            st.session_state["chat_history"].append(
                {"role":"assistant","content":answer,
                 "citations":citations,"sources":sources})
            st.rerun()

        # Controls row
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.session_state["chat_history"]:
                if st.button("🗑️ Clear This Session's Chat"):
                    if BE:
                        requests.delete(f"{BE}/chat/history",
                                       params={"session_id": sid}, timeout=5)
                    st.session_state["chat_history"] = []
                    st.rerun()

        with col2:
            if st.button("🔄 Reload Memory"):
                st.session_state["memory_loaded"] = False
                st.rerun()

        with col3:
            if st.button("🧹 Clear All Chat History"):
                if BE:
                    requests.delete(f"{BE}/chat/history/all", timeout=10)
                st.session_state["chat_history"] = []
                st.session_state["memory_loaded"] = False
                st.session_state["session_id"] = "default"
                st.rerun()

        # Suggested questions (only when chat is empty)
        if not st.session_state["chat_history"]:
            st.markdown("#### 💡 Suggested Questions")
            suggestions = [
                "What are the main indications for this drug?",
                "Summarise the contraindications and warnings.",
                "What dosage is recommended for adults?",
                "Are there any drug interactions mentioned?",
                "What adverse reactions have been reported?",
                "What are the storage conditions?",
            ]
            cols = st.columns(3)
            for i, sug in enumerate(suggestions):
                with cols[i % 3]:
                    if st.button(sug, key=f"sug_{i}"):
                        st.session_state["chat_history"].append(
                            {"role":"user","content":sug,"citations":[],"sources":[]})
                        with st.spinner("Generating…"):
                            try:
                                resp = requests.post(f"{BE}/chat",
                                    json={"query":sug,"session_id":sid}, timeout=120)
                                resp.raise_for_status()
                                d = resp.json()
                                answer,citations,sources = (
                                    d.get("answer",""), d.get("citations",[]), d.get("sources",[]))
                            except Exception as exc:
                                answer,citations,sources = f"⚠️ {exc}",[],[]
                        st.session_state["chat_history"].append(
                            {"role":"assistant","content":answer,
                             "citations":citations,"sources":sources})
                        st.rerun()
