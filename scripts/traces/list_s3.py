"""List the public SWE-bench submissions bucket for the configured mini-SWE-agent runs (read-only, no credentials).

  python -I scripts/traces/list_s3.py --config configs/traces_analysis.yaml OUTDIR

Writes OUTDIR/<run>.tsv with "key<TAB>size" per trajectory file (input of make_sample_list.py).
"""
from __future__ import annotations

import argparse
import os
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import yaml

HOST = "https://swe-bench-submissions.s3.amazonaws.com/"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--config", default="configs/traces_analysis.yaml")
    a = ap.parse_args()
    with open(a.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)["sources"]["mini_swe_v2"]
    os.makedirs(a.outdir, exist_ok=True)
    for run in cfg["runs"]:
        prefix = f"bash-only/{run}/trajs/"
        keys: list[tuple[str, int]] = []
        token = None
        while True:
            q = {"list-type": "2", "prefix": prefix, "max-keys": "1000"}
            if token:
                q["continuation-token"] = token
            with urllib.request.urlopen(HOST + "?" + urllib.parse.urlencode(q), timeout=60) as r:
                root = ET.fromstring(r.read())
            for c in root.findall("s3:Contents", NS):
                keys.append((c.find("s3:Key", NS).text, int(c.find("s3:Size", NS).text)))
            if root.findtext("s3:IsTruncated", namespaces=NS) == "true":
                token = root.findtext("s3:NextContinuationToken", namespaces=NS)
            else:
                break
        with open(os.path.join(a.outdir, run + ".tsv"), "w", encoding="utf-8", newline="\n") as g:
            for k, s in keys:
                g.write(f"{k}\t{s}\n")
        print(run, len(keys), f"{sum(s for _, s in keys) / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
