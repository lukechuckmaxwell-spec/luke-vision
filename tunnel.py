#!/usr/bin/env python3
"""Watch Luke Vision away from home, through a Cloudflare quick tunnel.

Standard library only.  Run:  python3 tunnel.py
Starts the site (see serve.py) plus `cloudflared tunnel --url`, then prints a public
https://....trycloudflare.com link. The link is new on every start and works only while
this runs; anyone who has it can watch. Ctrl+C stops both.
Needs cloudflared:  winget install --id Cloudflare.cloudflared
"""

import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import serve

PORT = serve.PORT
CLOUDFLARED_PATHS = [   # winget's install locations, in case PATH hasn't caught up yet
    r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
    r"C:\Program Files\cloudflared\cloudflared.exe",
]
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def find_cloudflared():
    return shutil.which("cloudflared") or next(
        (p for p in CLOUDFLARED_PATHS if Path(p).is_file()), None)


def main():
    sys.stdout.reconfigure(errors="replace")
    exe = find_cloudflared()
    if not exe:
        print("cloudflared not found. Install it with:  winget install --id Cloudflare.cloudflared")
        return 1
    try:
        server = serve.make_server(PORT, quiet=True)
    except OSError as exc:
        print(f"Can't use port {PORT}: {exc}. Stop the other server (serve.py or http.server) first.")
        return 1
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Luke Vision running on http://localhost:{PORT}; opening a tunnel...")

    proc = subprocess.Popen(
        [exe, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{PORT}"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    url = None
    try:
        for line in proc.stdout:
            if url is None and (m := URL_RE.search(line)):
                url = m.group(0)
                print("\n" + "=" * 64)
                print(f"  Watch from anywhere:  {url}")
                print("  New link every start. Anyone with it can watch, so share carefully.")
                print("  Ctrl+C to stop.")
                print("=" * 64 + "\n", flush=True)
            elif " ERR " in line:
                print(line.rstrip(), flush=True)
        print("cloudflared stopped.")
        return proc.wait()
    except KeyboardInterrupt:
        print("\nStopping...")
        return 0
    finally:
        proc.terminate()
        server.shutdown()


if __name__ == "__main__":
    sys.exit(main())
