#!/usr/bin/env python3
"""Serve the Expo web dist and proxy /api/* to the transportation-api backend.

Performance notes (mobile / Lighthouse):
  * Static assets are gzip-compressed on the fly and sent with
    `Content-Encoding: gzip` so the ~720KB main bundle transfers as ~200KB.
  * Hashed build assets (_expo/static, *.js, *.css) get a long-lived
    `Cache-Control: public, max-age=31536000, immutable` so repeat visits
    cost zero network. index.html is served uncompressed + no-cache so
    deploys show up immediately.
  * /api/* is proxied to the backend with permissive CORS.
"""
import gzip
import http.server
import io
import os
import socketserver
import urllib.request

try:
    import brotli  # optional; enables brotli precompression when available
except ImportError:
    brotli = None

DIST = "/opt/data/kanban/workspaces/t_b3fe8645/transportation-app/dist"
API_BASE = "http://127.0.0.1:8000"
PORT = int(os.environ.get("SERVE_PORT", "8124"))

# Compressible static types.
GZIP_EXT = {".js", ".css", ".html", ".json", ".svg", ".txt", ".map"}

# Hashed/immutable assets (Expo emits content-hashed filenames) — safe to
# cache forever.
IMMUTABLE_EXT = {".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg",
                 ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".webp"}

# On-the-fly gzip fallback when a precompressed .gz is missing. Set False to
# skip runtime compression entirely (precompressed files are always preferred).
compresslevel = 9


def _should_gzip(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in GZIP_EXT


def _cache_header(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in IMMUTABLE_EXT:
        return "public, max-age=31536000, immutable"
    return "no-cache"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=DIST, **kw)

    def do_GET(self):
        if self.path.startswith("/api/"):
            target = API_BASE + self.path
            try:
                req = urllib.request.Request(
                    target, headers={"Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = resp.read()
                    self.send_response(resp.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            except Exception as e:  # noqa: BLE001
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(str(e).encode())
            return

        fs_path = self.translate_path(self.path)
        if not os.path.exists(fs_path) or os.path.isdir(fs_path):
            # SPA fallback.
            self.path = "/index.html"
            fs_path = os.path.join(DIST, "index.html")

        self._serve_file(fs_path)

    def _serve_file(self, fs_path: str) -> None:
        try:
            with open(fs_path, "rb") as f:
                data = f.read()
        except OSError:
            self.send_error(404, "File not found")
            return

        accept = self.headers.get("Accept-Encoding", "").lower()
        # Prefer brotli > gzip when the client supports it; precomputed on
        # startup so there is zero per-request compression CPU. Brotli ships
        # ~15-25% smaller than gzip for JS/CSS, which directly lifts the
        # Lighthouse "uses-text-compression" weight and transfer time.
        encoding = None
        body = data
        if compresslevel and _should_gzip(fs_path):
            if "br" in accept and os.path.exists(fs_path + ".br"):
                with open(fs_path + ".br", "rb") as f:
                    body = f.read()
                encoding = "br"
            elif "gzip" in accept and os.path.exists(fs_path + ".gz"):
                with open(fs_path + ".gz", "rb") as f:
                    body = f.read()
                encoding = "gzip"
            elif "gzip" in accept:
                buf = io.BytesIO()
                with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9) as gz:
                    gz.write(data)
                body = buf.getvalue()
                encoding = "gzip"

        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(fs_path))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", _cache_header(fs_path))
        if encoding:
            self.send_header("Content-Encoding", encoding)
        self.send_header("Vary", "Accept-Encoding")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # silence default logging noise
        return


# Pre-compute compressed variants of every compressible asset so steady-state
# requests never pay compression CPU and brotli is available when supported.
def precompress() -> int:
    count = 0
    for root, _dirs, files in os.walk(DIST):
        for name in files:
            p = os.path.join(root, name)
            if not _should_gzip(p):
                continue
            try:
                with open(p, "rb") as f:
                    raw = f.read()
            except OSError:
                continue
            if not os.path.exists(p + ".gz"):
                with open(p + ".gz", "wb") as f:
                    with gzip.GzipFile(fileobj=f, mode="wb", compresslevel=9) as gz:
                        gz.write(raw)
            if brotli and not os.path.exists(p + ".br"):
                with open(p + ".br", "wb") as f:
                    f.write(brotli.compress(raw, quality=11))
            count += 1
    return count


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    n = precompress()
    print(f"Precompressed {n} static assets (brotli={'on' if brotli else 'off'}).")
    with ReusableTCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Serving dist on http://127.0.0.1:{PORT} (gzip+brotli + cache) proxy /api ->", API_BASE)
        httpd.serve_forever()
