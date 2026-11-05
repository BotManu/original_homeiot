"""Development gateway server. Run: python -m gateway."""
import base64
import hmac
import json
import os
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from .core import OpenEMS, Settings, Store, forward


def main():
    settings = Settings(mode=os.getenv("GATEWAY_MODE", "demo"),
        openems_url=os.getenv("OPENEMS_URL", "http://127.0.0.1:8084"),
        openems_user=os.getenv("OPENEMS_USER", "x"), openems_password=os.getenv("OPENEMS_PASSWORD", ""),
        thingsboard_url=os.getenv("THINGSBOARD_URL", ""), thingsboard_token=os.getenv("THINGSBOARD_TOKEN", ""),
        interval=float(os.getenv("POLL_SECONDS", "5")), capacity=int(os.getenv("SAMPLE_CAPACITY", "17280")))
    host = os.getenv("GATEWAY_HOST", "127.0.0.1")
    password = os.getenv("GATEWAY_PASSWORD", "")
    if (host not in ("127.0.0.1", "::1", "localhost") or settings.mode != "demo") and not password:
        raise SystemExit("Set GATEWAY_PASSWORD before enabling LAN access or live mode")
    folder = Path(os.getenv("GATEWAY_DATA", "data")) / settings.mode
    folder.mkdir(parents=True, exist_ok=True)
    store = Store(folder / "gateway.sqlite3", settings.capacity)
    adapter = OpenEMS(settings)
    state = {"source": "starting", "delivery": "not configured" if not settings.thingsboard_url else "waiting"}
    lock, stop = threading.Lock(), threading.Event()

    def collect():
        while not stop.is_set():
            try:
                store.add(adapter.read(), pending=bool(settings.thingsboard_url))
                status = "connected"
            except Exception:
                status = "unavailable"  # Do not expose credential-bearing upstream errors.
            with lock:
                state["source"] = status
            stop.wait(settings.interval)

    def deliver():
        while not stop.is_set():
            if settings.thingsboard_url:
                try:
                    forward(settings, store)
                    status = "reachable"
                except Exception:
                    status = "retrying"
                with lock:
                    state["delivery"] = status
            stop.wait(settings.interval)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_body(self, status, body, content_type="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            if not password:
                return True
            expected = "Basic " + base64.b64encode(("admin:" + password).encode()).decode()
            if hmac.compare_digest(self.headers.get("Authorization", "").encode(), expected.encode()):
                return True
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="OriginalHome local gateway"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return False

        def do_GET(self):
            if not self.authorized():
                return
            path = urlsplit(self.path).path
            if path == "/api/overview":
                samples = store.samples()
                latest = samples[0] if samples else None
                stale = not latest or time.time()*1000 - latest["ts"] > max(15, settings.interval*3)*1000
                with lock:
                    result = dict(state)
                result.update(mode=settings.mode, stale=stale, latest=latest,
                              history=list(reversed(samples)), buffer=store.status(), control_enabled=False)
                self.send_body(200, json.dumps(result, allow_nan=False).encode())
            elif path in ("/", "/app.js", "/style.css"):
                name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
                kind = {"/": "text/html; charset=utf-8", "/app.js": "text/javascript", "/style.css": "text/css"}[path]
                self.send_body(200, (Path(__file__).parent / "static" / name).read_bytes(), kind)
            else:
                self.send_body(404, b'{"error":"Not found"}')

        def do_POST(self):
            if self.authorized():
                self.send_body(405, b'{"error":"Energy writes are disabled pending equipment qualification"}')

    server = ThreadingHTTPServer((host, int(os.getenv("GATEWAY_PORT", "8080"))), Handler)
    for worker in (collect, deliver):
        threading.Thread(target=worker, daemon=True).start()
    print(f"OriginalHome local gateway: http://{host}:{server.server_port} ({settings.mode})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
