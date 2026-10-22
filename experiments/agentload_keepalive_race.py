"""Keep-alive race check: the generator against a mock server whose idle keep-alive timeout equals the tool time,
with and without connection reuse (server.force_close_connections), several seeds. Writes a new timestamped dir
results/agentload_keepalive_race/<ts>/ with the config copy, meta.json (git state captured at START), per-run
CSV (keepalive_race.csv) and the child run dirs' paths. Config: configs/agentload_keepalive_race.yaml.
    /opt/anaconda3/bin/python experiments/agentload_keepalive_race.py
Processes: this script + one mock server subprocess + (sequentially) the generator in-process = 2.
"""
from __future__ import annotations

import copy
import json
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from agentload.client import run_experiment  # noqa: E402
from agentload.config import config_from_dict  # noqa: E402
from agentload.runmeta import build_meta, git_info, new_result_dir, write_meta  # noqa: E402

CFG = REPO / "configs" / "agentload_keepalive_race.yaml"


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main() -> int:
    git = git_info(REPO)                                            # at START
    t0 = datetime.now()
    raw = yaml.safe_load(CFG.read_text())
    exp = raw.pop("experiment")
    out = new_result_dir(REPO / "results", "agentload_keepalive_race_summary")
    (out / "config.yaml").write_text(CFG.read_text())
    port = free_port()
    ms = exp["mock_server"]
    srv = subprocess.Popen([sys.executable, "-m", "agentload.mock_server", "--port", str(port),
                            *[a for k, v in ms.items() for a in ("--set", f"{k}={v}")]],
                           env={"PYTHONPATH": str(REPO / "src"), "PATH": "/usr/bin:/bin"},
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows = []
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        for seed in exp["seeds"]:
            for name, fc in exp["variants"].items():
                r = copy.deepcopy(raw)
                r["server"]["base_url"] = f"http://127.0.0.1:{port}"
                r["server"]["force_close_connections"] = fc
                r["run"]["seed"] = seed
                r["output"]["root"] = str(out / "runs")
                r["output"]["name"] = f"{name}_seed{seed}"
                cfg = config_from_dict(r)
                o = run_experiment(cfg, r, CFG, [sys.executable, *sys.argv], REPO)
                meta = json.loads((o.out_dir / "meta.json").read_text())["outcome"]
                req = pd.read_csv(o.out_dir / "requests.csv")
                rows.append({"variant": name, "force_close_connections": fc, "seed": seed, "run_dir": str(o.out_dir),
                             "requests_total": meta["requests_total"], "requests_ok": meta["requests_ok"],
                             "requests_error": meta["requests_error"], "errors_transport": meta["errors_by_kind"].get("transport", 0),
                             "sessions_failed": meta["sessions_failed"], "sessions_started": meta["sessions_started"],
                             "first_error": (req[req["status"] == "error"]["error"].iloc[0] if meta["requests_error"] else "")})
                print(rows[-1], flush=True)
    finally:
        srv.terminate()
        srv.wait(timeout=10)
    pd.DataFrame(rows).to_csv(out / "keepalive_race.csv", index=False)
    write_meta(out, build_meta(experiment="agentload_keepalive_race", argv=[sys.executable, *sys.argv], seeds=exp["seeds"],
                               hardware=raw["meta"]["hardware"], git=git, t_start=t0, t_end=datetime.now(),
                               extra={"mock_port": port, "variants": exp["variants"]}, status="finished"))
    print("result dir:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
