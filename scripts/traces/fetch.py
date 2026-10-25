"""Threaded downloader for the public agent-trace sources (one process, many connections).

The machine's link gives ~5 KB/s per connection but the rate scales with the number of connections, so large files
are fetched as HTTP Range chunks and small files in parallel. Everything is checked against an expected size and,
for the big archive, a SHA-256 published by the host. Nothing downloaded is ever executed or imported.

  python -I scripts/traces/fetch.py ranges URL OUT --size N [--sha256 HEX] [--threads 24] [--chunk-mb 2] [--prefix FILE]
  python -I scripts/traces/fetch.py files LIST OUTDIR [--threads 24]
      LIST: text file, one "URL<TAB>relative_path<TAB>size" per line (size may be 0 = unknown)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

ALLOWED_HOSTS = {"github.com", "swe-bench-submissions.s3.amazonaws.com", "huggingface.co", "raw.githubusercontent.com"}
UA = "nova-research-trace-fetch/1.0"
_print_lock = threading.Lock()


def _check_url(url: str) -> None:
    u = urlparse(url)
    if u.scheme != "https" or u.hostname not in ALLOWED_HOSTS:
        raise SystemExit(f"refusing url outside the allow-list: {url}")


def _get(url: str, rng: tuple[int, int] | None, timeout: float) -> bytes:
    headers = {"User-Agent": UA}
    if rng is not None:
        headers["Range"] = f"bytes={rng[0]}-{rng[1]}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        want_status = 206 if rng is not None else 200
        if r.status != want_status:
            raise RuntimeError(f"HTTP {r.status}, wanted {want_status}")
        return r.read()


def _retry(fn, tries: int = 10):
    last = None
    for k in range(tries):
        try:
            return fn()
        except (urllib.error.URLError, TimeoutError, ConnectionError, RuntimeError, OSError) as e:  # noqa: PERF203
            last = e
            time.sleep(min(2.0 * (k + 1), 20.0))
    raise RuntimeError(f"giving up after {tries} tries: {last!r}")


def cmd_ranges(a) -> None:
    _check_url(a.url)
    out = a.out
    parts_dir = out + ".parts"
    os.makedirs(parts_dir, exist_ok=True)
    chunk = int(a.chunk_mb * 1024 * 1024)
    n = (a.size + chunk - 1) // chunk
    spans = [(i * chunk, min(a.size, (i + 1) * chunk) - 1) for i in range(n)]
    if a.prefix and os.path.exists(a.prefix):      # reuse an interrupted single-stream download as whole chunks
        have = os.path.getsize(a.prefix)
        with open(a.prefix, "rb") as f:
            for i, (lo, hi) in enumerate(spans):
                p = os.path.join(parts_dir, f"part_{i:05d}")
                if hi < have and not os.path.exists(p):
                    f.seek(lo)
                    blob = f.read(hi - lo + 1)
                    with open(p, "wb") as g:
                        g.write(blob)

    done = [0]
    t0 = time.time()

    def one(i: int) -> int:
        lo, hi = spans[i]
        p = os.path.join(parts_dir, f"part_{i:05d}")
        if os.path.exists(p) and os.path.getsize(p) == hi - lo + 1:
            return i
        blob = _retry(lambda: _get(a.url, (lo, hi), a.timeout))
        if len(blob) != hi - lo + 1:
            raise RuntimeError(f"chunk {i}: got {len(blob)} bytes, wanted {hi - lo + 1}")
        with open(p + ".tmp", "wb") as g:
            g.write(blob)
        os.replace(p + ".tmp", p)
        return i

    with ThreadPoolExecutor(max_workers=a.threads) as ex:
        futs = [ex.submit(one, i) for i in range(n)]
        for fut in as_completed(futs):
            fut.result()
            done[0] += 1
            if done[0] % 5 == 0 or done[0] == n:
                with _print_lock:
                    mb = sum(os.path.getsize(os.path.join(parts_dir, x)) for x in os.listdir(parts_dir) if not x.endswith(".tmp")) / 1e6
                    print(f"[{time.time() - t0:7.0f}s] chunks {done[0]}/{n}  {mb:.1f} MB", flush=True)

    h = hashlib.sha256()
    with open(out + ".assembling", "wb") as g:
        for i in range(n):
            with open(os.path.join(parts_dir, f"part_{i:05d}"), "rb") as f:
                blob = f.read()
            h.update(blob)
            g.write(blob)
    size = os.path.getsize(out + ".assembling")
    if size != a.size:
        raise SystemExit(f"assembled size {size} != expected {a.size}")
    if a.sha256 and h.hexdigest() != a.sha256.lower():
        raise SystemExit(f"SHA-256 mismatch: got {h.hexdigest()} expected {a.sha256}")
    os.replace(out + ".assembling", out)
    print(f"OK {out} size={size} sha256={h.hexdigest()}", flush=True)
    for x in os.listdir(parts_dir):
        os.remove(os.path.join(parts_dir, x))
    os.rmdir(parts_dir)


def cmd_files(a) -> None:
    items = []
    with open(a.list, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            url, rel, size = line.split("\t")
            _check_url(url)
            if rel.startswith("/") or ".." in rel.split("/"):
                raise SystemExit(f"unsafe relative path {rel!r}")
            items.append((url, rel, int(size)))
    os.makedirs(a.outdir, exist_ok=True)
    t0 = time.time()
    nbytes = [0]
    ndone = [0]

    def one(item) -> str:
        url, rel, size = item
        dest = os.path.join(a.outdir, rel)
        if os.path.exists(dest) and (size == 0 or os.path.getsize(dest) == size):
            return rel
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        blob = _retry(lambda: _get(url, None, a.timeout))
        if size and len(blob) != size:
            raise RuntimeError(f"{rel}: got {len(blob)} bytes, wanted {size}")
        with open(dest + ".tmp", "wb") as g:
            g.write(blob)
        os.replace(dest + ".tmp", dest)
        with _print_lock:
            nbytes[0] += len(blob)
        return rel

    with ThreadPoolExecutor(max_workers=a.threads) as ex:
        futs = [ex.submit(one, it) for it in items]
        for fut in as_completed(futs):
            fut.result()
            ndone[0] += 1
            if ndone[0] % 10 == 0 or ndone[0] == len(items):
                with _print_lock:
                    print(f"[{time.time() - t0:7.0f}s] files {ndone[0]}/{len(items)}  {nbytes[0] / 1e6:.1f} MB", flush=True)
    print(f"OK {len(items)} files into {a.outdir}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("ranges")
    r.add_argument("url")
    r.add_argument("out")
    r.add_argument("--size", type=int, required=True)
    r.add_argument("--sha256", default="")
    r.add_argument("--threads", type=int, default=24)
    r.add_argument("--chunk-mb", type=float, default=2.0)
    r.add_argument("--timeout", type=float, default=90.0)
    r.add_argument("--prefix", default="", help="partial single-stream download to reuse as whole chunks")
    r.set_defaults(fn=cmd_ranges)
    f = sub.add_parser("files")
    f.add_argument("list")
    f.add_argument("outdir")
    f.add_argument("--threads", type=int, default=24)
    f.add_argument("--timeout", type=float, default=120.0)
    f.set_defaults(fn=cmd_files)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
