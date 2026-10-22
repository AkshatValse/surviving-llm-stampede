"""Parse SGLang server.log Prefill/Decode batch lines into a tidy table (one row per batch log line, file order)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2] / "results" / "nova"      # tracked in git (real Nova data)
LOGS = sorted(
    list((ROOT / "s0_smoke_17060165_pulled_20261021-152347" / "nova_job_logs").glob("*/server.log"))
    + list((ROOT / "stageC_1706210x_pulled_20261022-125454" / "nova_job_logs").glob("*/server.log"))
)

TS = r"^\[(?P<ts>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] "
RE_P = re.compile(
    TS + r"Prefill batch, #new-seq: (?P<new_seq>\d+), #new-token: (?P<new_tok>\d+), #cached-token: (?P<cached>\d+), "
    r"token usage: (?P<usage>[0-9.]+), #running-req: (?P<running>\d+), #queue-req: (?P<queue>\d+), "
    r"#pending-token: (?P<pending>\d+), cuda graph: (?P<cg>True|False), input throughput \(token/s\): (?P<thr>[0-9.]+)\s*$"
)
RE_D = re.compile(
    TS + r"Decode batch, #running-req: (?P<running>\d+), #token: (?P<token>\d+), token usage: (?P<usage>[0-9.]+), "
    r"cuda graph: (?P<cg>True|False), gen throughput \(token/s\): (?P<thr>[0-9.]+), #queue-req: (?P<queue>\d+)\s*$"
)
RE_FLUSH = re.compile(TS + r"Cache flushed successfully!")


def parse(path: Path) -> pd.DataFrame:
    job = path.parent.name.split("-")[0]
    rows = []
    unparsed = 0
    epoch = 0  # increments at each cache flush
    with open(path, "r", errors="replace") as fh:
        for ln, line in enumerate(fh, 1):
            if "Cache flushed successfully" in line:
                epoch += 1
                continue
            if "Prefill batch" in line:
                m = RE_P.match(line)
                if not m:
                    unparsed += 1
                    continue
                d = m.groupdict()
                rows.append(dict(job=job, line=ln, epoch=epoch, kind="P", ts=d["ts"], new_seq=int(d["new_seq"]),
                                 new_tok=int(d["new_tok"]), cached=int(d["cached"]), usage=float(d["usage"]),
                                 running=int(d["running"]), queue=int(d["queue"]), pending=int(d["pending"]),
                                 cg=d["cg"] == "True", thr=float(d["thr"])))
            elif "Decode batch" in line:
                m = RE_D.match(line)
                if not m:
                    unparsed += 1
                    continue
                d = m.groupdict()
                rows.append(dict(job=job, line=ln, epoch=epoch, kind="D", ts=d["ts"], running=int(d["running"]),
                                 token=int(d["token"]), usage=float(d["usage"]), cg=d["cg"] == "True",
                                 thr=float(d["thr"]), queue=int(d["queue"])))
    df = pd.DataFrame(rows)
    df["ts"] = pd.to_datetime(df["ts"])
    print(f"{path}: {len(df)} batch rows, unparsed batch-like lines: {unparsed}", file=sys.stderr)
    return df


def main(out: str) -> None:
    dfs = [parse(p) for p in LOGS]
    df = pd.concat(dfs, ignore_index=True)
    df.to_pickle(out)
    print(df.groupby(["job", "kind"]).size())


if __name__ == "__main__":
    main(sys.argv[1])
