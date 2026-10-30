#!/usr/bin/env python3
"""
start_dev.py — One-command development server launcher.

Starts both:
  • FastAPI backend  → http://localhost:8000  (uvicorn, auto-reload)
  • Vite frontend    → http://localhost:5173  (npm run dev)

Usage:
    python start_dev.py

Press Ctrl+C to stop both servers.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "Frontend"


def check_requirements():
    """Warn if key packages are missing."""
    missing = []
    try:
        import fastapi  # noqa: F401
    except ImportError:
        missing.append("fastapi")
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        missing.append("uvicorn")
    if missing:
        print(f"[!] Missing Python packages: {', '.join(missing)}")
        print(f"    Run:  pip install -r requirements.txt")
        sys.exit(1)


def check_node():
    """Warn if Node / npm is not installed."""
    try:
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("[!] Node.js not found. Install it from https://nodejs.org/")
        sys.exit(1)

    if not (FRONTEND / "node_modules").exists():
        print("[*] node_modules not found - installing dependencies...")
        subprocess.run(["npm", "install"], cwd=str(FRONTEND), check=True)


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    check_requirements()
    check_node()

    print("=" * 60)
    print("  Autonomous SaaS BI Engine - Development Server")
    print("=" * 60)
    print("  Backend  -> http://localhost:8000")
    print("  Frontend -> http://localhost:5173")
    print("  API Docs -> http://localhost:8000/docs")
    print("  Press Ctrl+C to stop both servers.")
    print("=" * 60)
    print()

    backend_cmd = [
        sys.executable, "-m", "uvicorn",
        "api.server:app",
        "--reload",
        "--port", "8000",
        "--host", "127.0.0.1",
        "--log-level", "info",
    ]
    frontend_cmd = ["npm", "run", "dev"]

    processes = []
    try:
        backend = subprocess.Popen(
            backend_cmd,
            cwd=str(ROOT),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        processes.append(backend)
        time.sleep(1.5)  # Give the backend a moment to start

        frontend = subprocess.Popen(
            frontend_cmd,
            cwd=str(FRONTEND),
            stdout=sys.stdout,
            stderr=sys.stderr,
            shell=(sys.platform == "win32"),
        )
        processes.append(frontend)

        # Wait for either process to exit
        while True:
            for p in processes:
                if p.poll() is not None:
                    print(f"\n[!] A server exited (code {p.returncode}). Stopping all.")
                    raise KeyboardInterrupt
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        for p in processes:
            try:
                if sys.platform == "win32":
                    p.send_signal(signal.CTRL_C_EVENT)
                else:
                    p.terminate()
            except Exception:
                p.kill()
        for p in processes:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("[*] Done.")


if __name__ == "__main__":
    _venv_python = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / ("python.exe" if sys.platform == "win32" else "python")
    if _venv_python.exists() and Path(sys.executable).resolve() != _venv_python.resolve():
        sys.exit(subprocess.call([str(_venv_python), __file__] + sys.argv[1:]))
    main()
