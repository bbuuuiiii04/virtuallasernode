"""
HTTP + Server-Sent-Events inspector server (build step 3).

Serves the static browser inspector and pushes 30Hz JSON snapshots of all
universes + the fixture patch. Stdlib only (http.server + SSE); bound to
127.0.0.1 so it's never exposed beyond loopback.
"""

import json
import os
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .fixtures import FIXTURES, decode_fixture
from .util import log
from .capture_index_runtime import CaptureIndexRuntime

WEB_PUSH_HZ = 30        # SSE snapshot rate to the browser
MAX_SSE_CLIENTS = 16    # cap concurrent /stream connections (each = 1 thread)

STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static"))
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}
# Only these paths are served as files (no arbitrary filesystem access).
STATIC_ROUTES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/renderer.js": "renderer.js",
    "/style.css": "style.css",
}


from .fixture_model_adapter import compose_fixture_model, load_fixture_model, sanitize_model

ROOT = Path(__file__).resolve().parent
CAPTURE_INDEX_PATH = ROOT / "artifacts" / "renderer" / "renderer-capture-index-pr1" / "capture_index_v1.json"
SOUNDSWITCH_CUES_PATH = ROOT / "data" / "soundswitch_laser_cues.json"

def _snapshot(node, fixture_model_cache=None, capture_index_runtime=None):
    """JSON-serializable snapshot of all universes + the fixture patch.

    Per-field reads are individually GIL-atomic (single writer thread), but the
    snapshot is not transactionally consistent — buffer, fps, and pkts may come
    from adjacent frames. Cosmetic for a visualizer. list() materializes the
    dict items atomically so a new universe inserted mid-iteration can't raise.
    """
    uni_vals = {}
    unis = {}
    for u, st in list(node.universes.items()):
        vals = list(st.buffer)
        uni_vals[u] = vals
        unis[str(u)] = {
            "values": vals,
            "fps": st.fps,
            "src": st.locked_src,
            "pkts": st.packet_count,
        }
    
    composed_models = []
    for f in FIXTURES:
        vals = uni_vals.get(f["universe"], [0] * 512)
        start = f["start"] - 1
        ch_list = vals[start:start+f["count"]]
        
        if fixture_model_cache is None:
            dec = decode_fixture(vals, f)
            composed_models.append({
                "decoded": dec,
                "composed": dec,
                "fixture_model": {
                    "model_status": "unavailable",
                    "confidence": "decoded_fallback",
                    "unsupported": ["model_load_failed"],
                    "capture_lookup": {
                        "hit": False,
                        "provenance_label": "MANUAL_DECODER",
                        "fallback_reason": "capture_index_unavailable",
                    },
                }
            })
            continue

        try:
            model = compose_fixture_model(ch_list, model=fixture_model_cache)
            model["composed"]["name"] = f["name"]
            model["composed"]["universe"] = f["universe"]
            model["decoded"]["name"] = f["name"]
            model["decoded"]["universe"] = f["universe"]
            lookup = (
                capture_index_runtime.lookup_exact_from_channels(ch_list)
                if capture_index_runtime is not None else
                {
                    "hit": False,
                    "provenance_label": "MEASURED_FIXTURE_MODEL",
                    "fallback_reason": "capture_index_unavailable",
                }
            )
            model["fixture_model"]["capture_lookup"] = lookup
            composed_models.append(model)
        except Exception as e:
            # Fallback cleanly so the SSE stream never dies
            log(f"[web] model adapter error: {e}")
            dec = decode_fixture(vals, f)
            composed_models.append({
                "decoded": dec,
                "composed": dec,
                "fixture_model": {
                    "model_status": "adapter_error",
                    "confidence": "decoded_fallback",
                    "unsupported": ["model_adapter_error"],
                    "error": str(e),
                    "capture_lookup": {
                        "hit": False,
                        "provenance_label": "MANUAL_DECODER",
                        "fallback_reason": "model_adapter_error",
                    },
                }
            })

    return {
        "universes": unis,
        "fixtures": FIXTURES,
        "decoded": [m["decoded"] for m in composed_models],
        "composed": [m.get("composed", m["decoded"]) for m in composed_models],
        "fixture_models": [m.get("fixture_model", {}) for m in composed_models],
        "polls": node.poll_count
    }


class SnapshotProducer:
    """
    Builds the SSE frame once per tick on a single thread, so the decode runs
    once regardless of client count and every /stream client sends the SAME
    frame at the same time (no per-client decode, no phase skew, tear-free).
    """

    def __init__(self, node, hz):
        self.node = node
        self.period = 1.0 / hz
        self._cond = threading.Condition()
        self._frame = None   # latest "data: {...}\n\n" bytes
        self._seq = 0
        try:
            self._fixture_model_cache = sanitize_model(load_fixture_model())
        except Exception as e:
            log(f"[web] failed to load fixture_model.json: {e}")
            self._fixture_model_cache = None
        try:
            self._capture_index_runtime = CaptureIndexRuntime.from_paths(
                index_path=CAPTURE_INDEX_PATH,
                cues_path=SOUNDSWITCH_CUES_PATH,
            )
        except Exception as e:
            log(f"[web] failed to load capture index: {e}")
            self._capture_index_runtime = None
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            try:
                payload = ("data: " + json.dumps(_snapshot(
                    self.node,
                    self._fixture_model_cache,
                    self._capture_index_runtime,
                ))
                           + "\n\n").encode("utf-8")
                with self._cond:
                    self._frame = payload
                    self._seq += 1
                    self._cond.notify_all()
            except Exception as e:
                # Never let the producer thread die silently — clients would
                # then freeze on the last frame forever.
                log(f"[web] snapshot producer error: {e}")
            time.sleep(self.period)

    def wait_next(self, last_seq, timeout):
        """Block until a frame newer than last_seq exists. Returns (seq, bytes)."""
        with self._cond:
            if self._seq == last_seq:
                self._cond.wait(timeout)
            return self._seq, self._frame


def start_web_server(node, port):
    """Start the HTTP + SSE inspector in a daemon thread. Returns the server."""
    sse_slots = threading.BoundedSemaphore(MAX_SSE_CLIENTS)
    producer = SnapshotProducer(node, WEB_PUSH_HZ)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass  # silence default per-request logging

        def _serve_static(self, fname):
            path = os.path.abspath(os.path.join(STATIC_DIR, fname))
            # commonpath avoids the startswith prefix weakness (e.g. a sibling
            # "static_evil" dir). fname is allowlisted anyway, so this is
            # belt-and-suspenders.
            if (os.path.commonpath([STATIC_DIR, path]) != STATIC_DIR
                    or not os.path.isfile(path)):
                self.send_response(404)
                self.end_headers()
                return
            with open(path, "rb") as f:
                body = f.read()
            ext = os.path.splitext(path)[1]
            self.send_response(200)
            self.send_header("Content-Type",
                             CONTENT_TYPES.get(ext, "application/octet-stream"))
            self.send_header("Content-Length", str(len(body)))
            # No caching — the browser must always load the latest renderer.js
            # (stale cache was serving old code during tuning).
            self.send_header("Cache-Control", "no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(body)

        def _serve_stream(self):
            if not sse_slots.acquire(blocking=False):
                self.send_response(503)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"too many SSE clients")
                return
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                last_seq = 0
                while True:
                    new_seq, frame = producer.wait_next(last_seq, 1.0)
                    # Only send when a genuinely new frame exists — a bare
                    # wait() timeout (e.g. producer stalled) must not re-send.
                    if frame is None or new_seq == last_seq:
                        continue
                    last_seq = new_seq
                    self.wfile.write(frame)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                return  # browser tab closed
            finally:
                sse_slots.release()

        def _serve_calibration(self):
            # calibration.json lives at the package root (single source of truth
            # shared with the Python decoder), not in static/. Served no-store so
            # the renderer always fetches the latest after an edit.
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "calibration.json")
            if not os.path.isfile(path):
                self.send_response(404)
                self.end_headers()
                return
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/stream":
                self._serve_stream()
            elif self.path == "/calibration.json":
                self._serve_calibration()
            elif self.path in STATIC_ROUTES:
                self._serve_static(STATIC_ROUTES[self.path])
            else:
                self.send_response(404)
                self.end_headers()

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd
