"""Write results/traces_summary/<source>/meta.json: commit, seeds, config, input checksums, row counts.

  python -I scripts/traces/write_meta.py SOURCE --config configs/traces_analysis.yaml
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys

import yaml


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--config", default="configs/traces_analysis.yaml")
    a = ap.parse_args()
    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    src = cfg["sources"][a.source]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "scripts/traces", "configs/traces_analysis.yaml"],
                           capture_output=True, text=True, check=True).stdout.strip()
    meta = {"source": a.source, "written_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git_commit": commit, "scripts_or_config_uncommitted_changes": bool(dirty),
            "python": sys.version.split()[0], "analysis_config": cfg["analysis"], "source_config": src}
    if a.source == "tracelab":
        path = os.path.join(src["raw_dir"], src["asset"])
        meta["input_sha256"] = sha256_file(path)
        meta["input_sha256_matches_published"] = meta["input_sha256"] == src["sha256"]
        meta["input_bytes"] = os.path.getsize(path)
    else:
        files = []
        for run in src["runs"]:
            d = os.path.join(src["raw_dir"], run)
            names = sorted(n for n in os.listdir(d) if n.endswith(".traj.json")) if os.path.isdir(d) else []
            h = hashlib.sha256()
            nbytes = 0
            for n in names:
                with open(os.path.join(d, n), "rb") as f:
                    blob = f.read()
                h.update(n.encode() + b"\0" + blob)
                nbytes += len(blob)
            files.append({"run": run, "n_files": len(names), "bytes": nbytes, "sha256_of_name_and_content_stream": h.hexdigest()})
        meta["input_files"] = files
    norm = src["norm_dir"]
    meta["normalised_rows"] = {}
    for n in ("calls", "rounds", "episodes", "sessions"):
        p = os.path.join(norm, n + ".csv")
        if os.path.exists(p):
            with open(p, "rb") as f:
                meta["normalised_rows"][n] = sum(1 for _ in f) - 1
    info = os.path.join(norm, "dataset_info.json")
    if os.path.exists(info):
        with open(info, encoding="utf-8") as fi:
            meta["dataset_info"] = json.load(fi)
    out = os.path.join(src["summary_dir"], "meta.json")
    os.makedirs(src["summary_dir"], exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
