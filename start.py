"""
start.py — Unified launcher for the Clinical & Regulatory Intelligence Platform.

Usage
-----
Start everything (recommended):
    python start.py

Start a single service (for development):
    python start.py --only qdrant
    python start.py --only model
    python start.py --only backend
    python start.py --only frontend

Stop everything:
    Ctrl-C  (all child processes are terminated cleanly)

Services started
----------------
1. Qdrant          — vector database        → http://localhost:6333
2. Model Service   — ML inference           → http://localhost:9000
3. Backend API     — FastAPI document API   → http://localhost:8000
4. Frontend        — Streamlit dashboard    → http://localhost:8501
"""

from __future__ import annotations

import argparse
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

import urllib.request

ROOT = Path(__file__).parent.resolve()

# ─────────────────────────────────────────────────────────────────────────────
# Colour helpers (works on Windows 10+ with ANSI enabled)
# ─────────────────────────────────────────────────────────────────────────────

if platform.system() == "Windows":
    os.system("color")   # enable ANSI on Windows console

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RED    = "\033[31m"


def _c(colour: str, text: str) -> str:
    return f"{colour}{text}{RESET}"


def log(service: str, msg: str, colour: str = CYAN) -> None:
    tag = _c(colour, f"[{service:<14}]")
    print(f"{tag} {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# Process registry
# ─────────────────────────────────────────────────────────────────────────────

_procs: list[subprocess.Popen] = []


def _cleanup(*_) -> None:
    print(_c(YELLOW, "\n\n🛑  Shutting down all services …"))
    for p in _procs:
        try:
            p.terminate()
        except Exception:
            pass
    for p in _procs:
        try:
            p.wait(timeout=8)
        except subprocess.TimeoutExpired:
            p.kill()
    print(_c(GREEN, "✅  All services stopped.\n"))
    sys.exit(0)


signal.signal(signal.SIGINT, _cleanup)
signal.signal(signal.SIGTERM, _cleanup)


# ─────────────────────────────────────────────────────────────────────────────
# Health-check helper
# ─────────────────────────────────────────────────────────────────────────────

def _wait_for_http(url: str, service: str, timeout: int = 180, interval: int = 3) -> bool:
    """Poll *url* until HTTP 200 or *timeout* seconds elapse."""
    deadline = time.time() + timeout
    dots = 0
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        if dots % 5 == 0:
            log(service, f"Waiting for {url} …", YELLOW)
        dots += 1
        time.sleep(interval)
    return False


def _is_port_free(host: str, port: int) -> bool:
    """Return True if the given port is available on the current host."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


# ─────────────────────────────────────────────────────────────────────────────
# Service launchers
# ─────────────────────────────────────────────────────────────────────────────

def start_qdrant() -> subprocess.Popen | None:
    """Launch the Qdrant binary as a subprocess."""
    os_name = platform.system()
    exe_name = "qdrant.exe" if os_name == "Windows" else "qdrant"
    qdrant_exe = ROOT / "qdrant_bin" / exe_name

    if not qdrant_exe.exists():
        log("Qdrant", "Binary not found in qdrant_bin/. Run: python setup.py", RED)
        log("Qdrant", "Alternatively install Qdrant from https://qdrant.tech/documentation/guides/installation/", YELLOW)
        log("Qdrant", "Assuming Qdrant is already running on port 6333 …", YELLOW)
        return None

    data_dir = ROOT / "qdrant_data"
    data_dir.mkdir(exist_ok=True)

    log("Qdrant", f"Starting {qdrant_exe.name} …", GREEN)
    env = os.environ.copy()
    env["QDRANT__STORAGE__STORAGE_PATH"] = str(data_dir)

    proc = subprocess.Popen(
        [str(qdrant_exe)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _procs.append(proc)

    # Qdrant >= 1.8 responds on "/" — older builds used "/healthz"
    if _wait_for_http("http://localhost:6333/", "Qdrant", timeout=30):
        log("Qdrant", "✅  Running on http://localhost:6333", GREEN)
    else:
        log("Qdrant", "⚠️  Did not respond in time — continuing anyway", YELLOW)

    return proc



def _check_available_ram() -> None:
    """Warn if available RAM is below the recommended threshold (Windows only)."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength",                 ctypes.c_ulong),
                ("dwMemoryLoad",             ctypes.c_ulong),
                ("ullTotalPhys",             ctypes.c_ulonglong),
                ("ullAvailPhys",             ctypes.c_ulonglong),
                ("ullTotalPageFile",         ctypes.c_ulonglong),
                ("ullAvailPageFile",         ctypes.c_ulonglong),
                ("ullTotalVirtual",          ctypes.c_ulonglong),
                ("ullAvailVirtual",          ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        avail_gb = stat.ullAvailPhys / (1024 ** 3)
        total_gb = stat.ullTotalPhys / (1024 ** 3)
        log("Launcher", f"RAM: {avail_gb:.1f} GB free / {total_gb:.1f} GB total", CYAN)
        if avail_gb < 1.5:
            log("Launcher", "WARNING: Less than 1.5 GB RAM free.", RED)
            log("Launcher", "Close other applications before loading models.", RED)
    except Exception:
        pass


def start_model_service() -> subprocess.Popen:
    """Launch the Model Service with uvicorn."""
    _check_available_ram()
    log("ModelService", "Starting … (lightweight models: ~700 MB total)", YELLOW)
    log("ModelService", "First run downloads models from HuggingFace (~700 MB).", YELLOW)

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("MODEL_SERVICE_HOST", "0.0.0.0")
    env.setdefault("MODEL_SERVICE_PORT", "9000")

    model_host = env["MODEL_SERVICE_HOST"]
    model_port = int(env["MODEL_SERVICE_PORT"])

    if not _is_port_free(model_host, model_port):
        log("ModelService", f"Port {model_port} is already in use. Searching for an available port …", RED)
        for candidate in range(model_port + 1, model_port + 11):
            if _is_port_free(model_host, candidate):
                model_port = candidate
                env["MODEL_SERVICE_PORT"] = str(model_port)
                log("ModelService", f"Using available port {model_port} instead.", YELLOW)
                break
        else:
            log("ModelService", f"No available port found between {model_port + 1} and {model_port + 10}.", RED)
            _cleanup()

    model_url = f"http://localhost:{model_port}"
    os.environ["MODEL_SERVICE_URL"] = model_url

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "model_service.model_service:app",
            "--host", model_host,
            "--port", str(model_port),
            "--log-level", "info",
        ],
        cwd=str(ROOT),
        env=env,
    )
    _procs.append(proc)

    log("ModelService", "Waiting for models to load (up to 10 min) …", YELLOW)
    if _wait_for_http(f"{model_url}/health", "ModelService", timeout=600, interval=5):
        log("ModelService", f"✅  Running on {model_url}", GREEN)
    else:
        log("ModelService", "⚠️  Still loading — backend will retry automatically", YELLOW)

    return proc


def start_backend() -> subprocess.Popen:
    """Launch the FastAPI backend with uvicorn."""
    log("Backend", "Starting FastAPI backend …", GREEN)

    env = os.environ.copy()
    env.setdefault("QDRANT_HOST", "localhost")
    env.setdefault("QDRANT_PORT", "6333")
    env.setdefault("USE_LOCAL_QDRANT", "false")
    env.setdefault("MODEL_SERVICE_URL", "http://localhost:9000")
    env.setdefault("UPLOAD_DIR", str(ROOT / "data" / "uploads"))
    env.setdefault("BACKEND_HOST", "0.0.0.0")
    env.setdefault("BACKEND_PORT", "8000")

    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")

    backend_host = env["BACKEND_HOST"]
    backend_port = int(env["BACKEND_PORT"])

    if not _is_port_free(backend_host, backend_port):
        log("Backend", f"Port {backend_port} is already in use. Searching for an available port …", RED)
        for candidate in range(backend_port + 1, backend_port + 11):
            if _is_port_free(backend_host, candidate):
                backend_port = candidate
                env["BACKEND_PORT"] = str(backend_port)
                log("Backend", f"Using available port {backend_port} instead.", YELLOW)
                break
        else:
            log("Backend", f"No available port found between {backend_port + 1} and {backend_port + 10}.", RED)
            _cleanup()

    backend_url = f"http://localhost:{backend_port}"
    os.environ["BACKEND_URL"] = backend_url

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--host", backend_host,
            "--port", str(backend_port),
            "--log-level", "info",
            "--app-dir", str(ROOT),
        ],
        cwd=str(ROOT),
        env=env,
    )
    _procs.append(proc)

    if _wait_for_http(f"{backend_url}/health", "Backend", timeout=30):
        log("Backend", f"✅  Running on {backend_url}", GREEN)
    else:
        log("Backend", "⚠️  Did not respond in time — check logs", YELLOW)
        _cleanup()

    return proc


def start_frontend() -> subprocess.Popen:
    """Launch the Streamlit frontend."""
    log("Frontend", "Starting Streamlit dashboard …", GREEN)

    env = os.environ.copy()
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("BACKEND_URL", "http://localhost:8000")
    env.setdefault("FRONTEND_HOST", "localhost")
    env.setdefault("FRONTEND_PORT", "8501")

    frontend_host = env["FRONTEND_HOST"]
    frontend_port = int(env["FRONTEND_PORT"])

    if not _is_port_free(frontend_host, frontend_port):
        log("Frontend", f"Port {frontend_port} is already in use. Searching for an available port …", RED)
        for candidate in range(frontend_port + 1, frontend_port + 11):
            if _is_port_free(frontend_host, candidate):
                frontend_port = candidate
                env["FRONTEND_PORT"] = str(frontend_port)
                log("Frontend", f"Using available port {frontend_port} instead.", YELLOW)
                break
        else:
            log("Frontend", f"No available port found between {frontend_port + 1} and {frontend_port + 10}.", RED)
            _cleanup()

    frontend_url = f"http://{frontend_host}:{frontend_port}"

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            str(ROOT / "frontend" / "app.py"),
            "--server.port", str(frontend_port),
            "--server.address", frontend_host,
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=str(ROOT),
        env=env,
    )
    _procs.append(proc)

    if _wait_for_http(frontend_url, "Frontend", timeout=30):
        log("Frontend", f"✅  Running on {frontend_url}", GREEN)
    else:
        log("Frontend", "⚠️  Did not respond in time — check logs", YELLOW)
        _cleanup()

    return proc


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def _banner() -> None:
    print(_c(BOLD, """
╔══════════════════════════════════════════════════════════╗
║   🏥  Clinical & Regulatory Intelligence Platform        ║
║       Local launcher — no Docker required                ║
╚══════════════════════════════════════════════════════════╝
"""))


def _clear_pycache() -> None:
    """Delete all __pycache__ dirs — prevents stale .pyc from causing 404s."""
    import shutil
    for cache_dir in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache_dir, ignore_errors=True)
    log("Launcher", "Cleared __pycache__ directories", CYAN)


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the Clinical Platform services.")
    parser.add_argument(
        "--only",
        choices=["qdrant", "model", "backend", "frontend"],
        help="Start only a specific service.",
    )
    args = parser.parse_args()

    _banner()
    _clear_pycache()

    only = args.only

    if only == "qdrant":
        start_qdrant()
    elif only == "model":
        start_model_service()
    elif only == "backend":
        start_backend()
    elif only == "frontend":
        start_frontend()
    else:
        # Full stack — ordered startup with health gates
        log("Launcher", "Starting all services in order …", CYAN)

        start_qdrant()
        time.sleep(2)

        start_model_service()
        # Model service health is waited inside start_model_service()

        start_backend()
        time.sleep(1)

        start_frontend()

        backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
        model_url = os.environ.get("MODEL_SERVICE_URL", "http://localhost:9000")
        frontend_host = os.environ.get("FRONTEND_HOST", "localhost")
        frontend_port = os.environ.get("FRONTEND_PORT", "8501")
        frontend_url = f"http://{frontend_host}:{frontend_port}"

        print(_c(BOLD + GREEN, f"""
┌──────────────────────────────────────────────────────────┐
│   ✅  All services are running                           │
│                                                          │
│   Dashboard  →  {frontend_url}                    │
│   Backend    →  {backend_url}/docs               │
│   Models     →  {model_url}/docs               │
│   Qdrant UI  →  http://localhost:6333/dashboard          │
│                                                          │
│   Press Ctrl-C to stop all services                      │
└──────────────────────────────────────────────────────────┘
"""))

    # Keep process alive — wait for all children
    try:
        while True:
            # Restart any process that died unexpectedly
            for p in list(_procs):
                if p.poll() is not None:
                    log("Launcher", f"Process {p.pid} exited with code {p.returncode}", RED)
            time.sleep(5)
    except KeyboardInterrupt:
        _cleanup()


if __name__ == "__main__":
    main()
