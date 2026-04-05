"""
AI Humanizer — Desktop App Launcher

Starts the FastAPI backend in a background thread, waits for models to load,
then opens a native macOS window via pywebview.  One process, no terminal needed.
"""

import subprocess
import sys
import threading
import time

import httpx
import uvicorn
import webview


PORT = 8000
URL = f"http://127.0.0.1:{PORT}"


def _ensure_ollama():
    """Start Ollama if it isn't already running."""
    try:
        httpx.get("http://localhost:11434/api/tags", timeout=2)
        return  # already running
    except Exception:
        pass
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("Started Ollama in background.")
        time.sleep(2)
    except FileNotFoundError:
        print("WARNING: Ollama not installed — humanization won't work.")


def _start_server():
    """Run uvicorn in a daemon thread."""
    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, log_level="warning")


def _wait_for_server(timeout: int = 120):
    """Block until the /api/health endpoint responds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{URL}/api/health", timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def main():
    _ensure_ollama()

    # Start FastAPI in a background thread
    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()

    print("Loading models (this takes ~30s on first launch)...")
    if not _wait_for_server():
        print("ERROR: Server failed to start within 120s.")
        sys.exit(1)

    print("Opening AI Humanizer...")
    webview.create_window(
        "AI Humanizer",
        URL,
        width=1280,
        height=860,
        min_size=(900, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
