#!/usr/bin/env python3
"""
EZ Logger — Live Preview Server
----------------------------------------
Run this once, leave it running, then open http://localhost:8765 in your browser.
Every time you save renamer.py the browser updates automatically.

Requirements:
    pip install watchdog
"""

import os
import sys
import time
import json
import queue
import threading
import http.server
from pathlib import Path

# ── Find renamer.py (same folder as this script) ──────────────────────────────
HERE        = Path(__file__).parent
WATCH_FILE  = HERE / "renamer.py"
PORT        = 8765
PREVIEW_HTML = HERE / "preview.html"

if not WATCH_FILE.exists():
    print(f"[preview] ERROR: cannot find {WATCH_FILE}")
    print("[preview] Make sure preview_server.py is in the same folder as renamer.py")
    sys.exit(1)

# ── SSE client registry ───────────────────────────────────────────────────────
_clients_lock = threading.Lock()
_clients: list[queue.Queue] = []

def _add_client(q):
    with _clients_lock:
        _clients.append(q)

def _remove_client(q):
    with _clients_lock:
        if q in _clients:
            _clients.remove(q)

def _notify_all():
    with _clients_lock:
        alive = []
        for q in _clients:
            try:
                q.put_nowait("reload")
                alive.append(q)
            except queue.Full:
                pass
        _clients.clear()
        _clients.extend(alive)
    print(f"[preview] change detected → reloading {len(_clients)} browser tab(s)")

# ── File watcher ──────────────────────────────────────────────────────────────
def _watch():
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class Handler(FileSystemEventHandler):
            _last = 0
            def on_modified(self, event):
                if Path(event.src_path).resolve() == WATCH_FILE.resolve():
                    now = time.time()
                    if now - Handler._last > 0.4:   # debounce rapid saves
                        Handler._last = now
                        _notify_all()

        observer = Observer()
        observer.schedule(Handler(), path=str(WATCH_FILE.parent), recursive=False)
        observer.start()
        print(f"[preview] watching {WATCH_FILE.name} for changes…")
        observer.join()

    except ImportError:
        print("[preview] 'watchdog' not installed — falling back to polling")
        print("[preview] To get instant updates:  pip install watchdog")
        _poll_fallback()

def _poll_fallback():
    """Poll mtime every second when watchdog is unavailable."""
    last_mtime = WATCH_FILE.stat().st_mtime
    while True:
        time.sleep(1)
        try:
            mtime = WATCH_FILE.stat().st_mtime
            if mtime != last_mtime:
                last_mtime = mtime
                _notify_all()
        except OSError:
            pass

# ── State extraction — reads shortcuts/config from their JSON files ───────────
def _get_state():
    """
    Returns a dict describing the current UI state.
    Reads the same JSON files that renamer.py reads, so the preview
    always reflects your saved shortcuts and session settings.
    """
    config_path    = os.path.expanduser("~/.bball_renamer_v3_config.json")
    shortcuts_path = os.path.expanduser("~/.bball_renamer_v3_shortcuts.json")

    DEFAULT_SESSION = {
        "sport": "MBB", "opponent": "MIAMI",
        "videographer": "ZK", "phase": "PRE", "folder": "",
    }
    DEFAULT_SHORTCUTS = {
        "players": [
            {"key": "1", "label": "HAND"},
            {"key": "2", "label": "HASTINGS"},
            {"key": "3", "label": "SMITH"},
        ],
        "plays": [
            {"key": "1", "label": "LAYUP"},
            {"key": "2", "label": "THREE"},
            {"key": "3", "label": "POST UP"},
            {"key": "4", "label": "DRIVE"},
            {"key": "5", "label": "CLOSE UP"},
        ],
        "ratings": [
            {"key": "1", "label": "GOOD"},
            {"key": "2", "label": "MISS"},
            {"key": "3", "label": "FOUL"},
            {"key": "4", "label": "TO"},
        ],
    }

    def load(path, default):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return default

    session   = load(config_path,    DEFAULT_SESSION)
    shortcuts = load(shortcuts_path, DEFAULT_SHORTCUTS)

    # Read the last-modified timestamp of renamer.py so the browser can show it
    try:
        mtime = WATCH_FILE.stat().st_mtime
        last_saved = time.strftime("%H:%M:%S", time.localtime(mtime))
    except Exception:
        last_saved = "—"

    SPORTS = {
        "MBB": {"emoji": "🏀"}, "WBB": {"emoji": "🏀"},
        "MHK": {"emoji": "🏒"}, "WHK": {"emoji": "🏒"},
        "FB":  {"emoji": "🏈"}, "WLAX": {"emoji": "🥍"},
        "BASE": {"emoji": "⚾"}, "SB": {"emoji": "🥎"},
    }
    sport_key   = session.get("sport", "MBB")
    sport_emoji = SPORTS.get(sport_key, {}).get("emoji", "🏅")

    return {
        "session": {
            "sport":        sport_key,
            "sport_emoji":  sport_emoji,
            "opponent":     session.get("opponent", ""),
            "videographer": session.get("videographer", ""),
            "phase":        session.get("phase", ""),
            "folder":       Path(session.get("folder", "")).name or "No folder",
        },
        "shortcuts": shortcuts,
        "last_saved": last_saved,
        "watch_file": WATCH_FILE.name,
    }

# ── HTTP handler ──────────────────────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass   # suppress access log noise

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_file(PREVIEW_HTML, "text/html")
        elif self.path == "/state":
            self._serve_json(_get_state())
        elif self.path == "/events":
            self._serve_sse()
        else:
            self.send_error(404)

    def _serve_file(self, path: Path, content_type: str):
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            self.send_error(404, f"File not found: {path.name}")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_json(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_sse(self):
        self.send_response(200)
        self.send_header("Content-Type",  "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection",    "keep-alive")
        self.end_headers()

        q = queue.Queue(maxsize=4)
        _add_client(q)
        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    self.wfile.write(f"data: {msg}\n\n".encode())
                    self.wfile.flush()
                except queue.Empty:
                    # heartbeat keeps the connection alive through proxies
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            _remove_client(q)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Start file watcher in background thread
    watcher_thread = threading.Thread(target=_watch, daemon=True)
    watcher_thread.start()

    # Start HTTP server
    server = http.server.HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"[preview] server running → open http://localhost:{PORT}")
    print(f"[preview] press Ctrl+C to stop\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[preview] stopped")
