#!/usr/bin/env python3
"""
Traffic generator for the Prima API.

Sends a realistic mix of requests against a running local stack to populate
the Grafana dashboard with meaningful data.

Usage:
    python3 scripts/load.py                  # 60 seconds, default URL
    python3 scripts/load.py --duration 120   # run for 2 minutes
    python3 scripts/load.py --url http://localhost:8000 --duration 30
"""

import argparse
import random
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib


# ── Minimal valid 1×1 PNG (no external deps needed) ──────────────────────────

def _make_png() -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x80\x40")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


PNG = _make_png()
DOMAINS = ["example.com", "acme.io", "demo.co", "sample.org", "prima.it"]


# ── Request helpers ───────────────────────────────────────────────────────────

def get(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def post_user(base: str, index: int) -> int:
    email = f"user{index}@{random.choice(DOMAINS)}"
    body = (
        b"------boundary\r\n"
        b"Content-Disposition: form-data; name=\"name\"\r\n\r\n"
        + f"User {index}".encode()
        + b"\r\n------boundary\r\n"
        b"Content-Disposition: form-data; name=\"email\"\r\n\r\n"
        + email.encode()
        + b"\r\n------boundary\r\n"
        b"Content-Disposition: form-data; name=\"avatar\"; filename=\"avatar.png\"\r\n"
        b"Content-Type: image/png\r\n\r\n"
        + PNG
        + b"\r\n------boundary--\r\n"
    )
    req = urllib.request.Request(
        f"{base}/user",
        data=body,
        headers={"Content-Type": "multipart/form-data; boundary=----boundary"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def post_invalid(base: str) -> int:
    """POST /user with a malformed email — intentionally triggers a 422."""
    body = (
        b"------boundary\r\n"
        b"Content-Disposition: form-data; name=\"name\"\r\n\r\nBad User\r\n"
        b"------boundary\r\n"
        b"Content-Disposition: form-data; name=\"email\"\r\n\r\nnot-an-email\r\n"
        b"------boundary\r\n"
        b"Content-Disposition: form-data; name=\"avatar\"; filename=\"avatar.png\"\r\n"
        b"Content-Type: image/png\r\n\r\n"
        + PNG
        + b"\r\n------boundary--\r\n"
    )
    req = urllib.request.Request(
        f"{base}/user",
        data=body,
        headers={"Content-Type": "multipart/form-data; boundary=----boundary"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


# ── Main loop ─────────────────────────────────────────────────────────────────

def run(base: str, duration: int) -> None:
    print(f"Sending traffic to {base} for {duration}s")
    print(f"  Mix: 28% /health  24% /users  20% POST /user (valid)  13% POST /user (invalid)  15% /metrics")
    print(f"  Grafana dashboard → http://localhost:3000/d/prima-api-obs")
    print()

    counts: dict[str, int] = {"2xx": 0, "4xx": 0, "5xx": 0, "err": 0}
    users_created = 0
    total = 0
    start = time.time()

    while True:
        elapsed = time.time() - start
        if elapsed >= duration:
            break

        total += 1
        r = random.random()

        if r < 0.28:
            status = get(f"{base}/health")
        elif r < 0.52:
            status = get(f"{base}/users")
        elif r < 0.72:
            status = post_user(base, total)
            if status == 201:
                users_created += 1
        elif r < 0.85:
            status = post_invalid(base)
        else:
            status = get(f"{base}/metrics")

        if 200 <= status < 300:
            counts["2xx"] += 1
        elif 400 <= status < 500:
            counts["4xx"] += 1
        elif status >= 500:
            counts["5xx"] += 1
        else:
            counts["err"] += 1

        if total % 50 == 0:
            rps = total / elapsed if elapsed > 0 else 0
            print(
                f"  {elapsed:5.0f}s  {total:4d} reqs  {rps:.1f} req/s  "
                f"2xx={counts['2xx']}  4xx={counts['4xx']}  "
                f"users_created={users_created}"
            )
            sys.stdout.flush()

        time.sleep(random.uniform(0.05, 0.2))

    elapsed = time.time() - start
    rps = total / elapsed if elapsed > 0 else 0
    print()
    print(f"Done — {total} requests in {elapsed:.0f}s ({rps:.1f} req/s)")
    print(f"  2xx={counts['2xx']}  4xx={counts['4xx']}  5xx={counts['5xx']}  users_created={users_created}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Prima API traffic generator")
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds (default: 60)")
    args = parser.parse_args()
    run(args.url, args.duration)


if __name__ == "__main__":
    main()
