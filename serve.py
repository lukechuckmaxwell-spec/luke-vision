#!/usr/bin/env python3
"""Serve Luke Vision: the page and its catalog, and nothing else in this folder.

Standard library only.  Run:  python3 serve.py [port]   (default 8080)
Unlike `python -m http.server`, this never hands out other files (scripts, logs, ...),
which matters once the site is reachable through a tunnel.
"""

import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PORT = 8080
FILES = {   # URL path -> (file, content type)
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/catalog.json": ("catalog.json", "application/json; charset=utf-8"),
}
ROBOTS = b"User-agent: *\nDisallow: /\n"   # keep a shared link out of search engines


class Handler(BaseHTTPRequestHandler):
    quiet = False

    def do_GET(self):
        self.reply(send_body=True)

    def do_HEAD(self):
        self.reply(send_body=False)

    def reply(self, send_body):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if path == "/robots.txt":
            body, ctype = ROBOTS, "text/plain; charset=utf-8"
        elif path in FILES and (ROOT / FILES[path][0]).is_file():
            name, ctype = FILES[path]
            body = (ROOT / name).read_bytes()
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        if not self.quiet:
            super().log_message(fmt, *args)


def make_server(port=PORT, quiet=False):
    """All interfaces, so the Xbox on the home network can still connect directly."""
    handler = type("QuietHandler" if quiet else "Handler", (Handler,), {"quiet": quiet})
    return ThreadingHTTPServer(("0.0.0.0", port), handler)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    try:
        server = make_server(port)
    except OSError as exc:
        print(f"Can't use port {port}: {exc}. Is another server already running?")
        return 1
    print(f"Luke Vision on http://localhost:{port} (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
