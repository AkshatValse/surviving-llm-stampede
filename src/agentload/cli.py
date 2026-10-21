"""Command line: ``python -m agentload {run,plan,probe,canary} --config configs/agentload_*.yaml [--set a.b=v ...]``."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

import aiohttp
import numpy as np
import yaml

from .canary import run_canary
from .client import run_experiment
from .config import Config, load_config, resolve_ramp, resolve_rate
from .parse import extract_output_ids, extract_usage, parse_prometheus
from .runmeta import build_meta, default_hardware, git_info, new_result_dir, write_meta
from .workload import build_open_plan, effective_mean_turns, prompt_len


def _repo_dir(cfg_path: str) -> Path:
    return Path(cfg_path).resolve().parent.parent


def _common(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--config", required=True)
    ap.add_argument("--set", action="append", default=[], metavar="a.b=value",
                    help="override a config value (YAML-parsed); may be repeated")
    ap.add_argument("--seed", type=int, default=None, help="shortcut for --set run.seed=N")
    ap.add_argument("--out-root", default=None, help="shortcut for --set output.root=PATH")
    ap.add_argument("--name", default=None, help="shortcut for --set output.name=NAME")


def _load(args: argparse.Namespace) -> Tuple[Config, Dict[str, Any]]:
    sets = list(args.set)
    if args.seed is not None:
        sets.append(f"run.seed={args.seed}")
    if args.out_root is not None:
        sets.append(f"output.root={args.out_root}")
    if args.name is not None:
        sets.append(f"output.name={args.name}")
    return load_config(args.config, sets)


def cmd_plan(args: argparse.Namespace) -> int:
    """Print plan statistics (no server needed, nothing written): sessions, turns, prompt-token totals."""
    cfg, raw = _load(args)
    base = _repo_dir(args.config)
    rate = resolve_rate(cfg.arrivals, base)
    ramp = resolve_ramp(cfg.arrivals, base) if cfg.arrivals.kind == "ramp" else []
    plan = [] if cfg.arrivals.kind == "closed" else build_open_plan(cfg.run.seed, cfg.workload, cfg.arrivals,
                                                                    cfg.run.duration_s, rate, ramp)
    turns = int(sum(p.n_turns for p in plan))
    prompt_tokens = int(sum(prompt_len(cfg.workload, t) for p in plan for t in range(1, p.n_turns + 1)))
    out = {"kind": cfg.arrivals.kind, "seed": cfg.run.seed, "resolved_rate": rate, "n_sessions": len(plan),
           "n_burst_sessions": sum(p.origin == "burst" for p in plan), "n_turns_total": turns,
           "mean_turns_per_session": turns / len(plan) if plan else None,
           "expected_turns_per_session": effective_mean_turns(cfg.workload),
           "all_miss_prompt_tokens_total": prompt_tokens,
           "max_prompt_tokens": prompt_len(cfg.workload, cfg.workload.max_turns)}
    print(json.dumps(out, indent=2))
    if args.write:                                  # record it: new timestamped dir with config copy and meta.json
        git = git_info(base)
        t0 = datetime.now()
        d = new_result_dir(cfg.output.root, f"{cfg.output.name}_planstats")
        (d / "plan_stats.json").write_text(json.dumps(out, indent=2))
        (d / "config.yaml").write_text(Path(args.config).read_text())
        (d / "config_effective.yaml").write_text(yaml.safe_dump(raw, sort_keys=False))
        write_meta(d, build_meta(experiment=f"{cfg.output.name}_planstats", argv=[sys.executable, "-m", "agentload",
                   *sys.argv[1:]], seeds=[cfg.run.seed], hardware=default_hardware(), git=git, t_start=t0,
                   t_end=datetime.now(), extra={"plan_stats": out}, status="finished"))
        print("result dir:", d)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cfg, raw = _load(args)
    out = run_experiment(cfg, raw, args.config, [sys.executable, "-m", "agentload", *sys.argv[1:]],
                         _repo_dir(args.config))
    print(json.dumps({"out_dir": str(out.out_dir), "abort_reason": out.abort_reason, "t_end_s": out.t_end_s,
                      **out.counts}, indent=2))
    return 143 if (out.abort_reason or "").startswith("signal_") else 0


async def _probe(cfg: Config) -> int:
    """Three requests + one /metrics scrape; prints raw JSON so field names can be checked on the engine.
    1-2: identical requests (the 2nd shows cached_tokens > 0 if caching is on), sent with the config's own body.
    3: the same prompt with ``return_token_ids: true`` regardless of ``server.request_token_ids``: does the engine
    accept the field, and does the response carry output token ids (plan step (c))? The last line,
    ``PROBE_SUMMARY {json}``, collects the answers (also: does the server's prompt_tokens equal the 64 sent?)."""
    srv = cfg.server
    ids = np.arange(cfg.workload.token_id_low, cfg.workload.token_id_low + 64, dtype=np.int32).tolist()
    prompt: Any = ids if cfg.workload.prompt_mode == "tokens" else " ".join(["the"] * 64)
    body: Dict[str, Any] = {"model": srv.model, "prompt": prompt, "max_tokens": 8, "temperature": 0.0,
                            "stream": False, **srv.extra_body}
    if srv.request_token_ids:
        body["return_token_ids"] = True
    summary: Dict[str, Any] = {"prompt_tokens_sent": len(ids) if cfg.workload.prompt_mode == "tokens" else None}
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(force_close=True)) as http:
        for rep in (1, 2):                # the 2nd identical request shows cached_tokens > 0 if caching is on
            async with http.post(srv.base_url.rstrip("/") + srv.completions_path, json=body) as r:
                txt = await r.text()
                print(f"--- request {rep}: HTTP {r.status}")
                print(txt[:2000])
                if r.status == 200:
                    u = extract_usage(json.loads(txt))
                    print("parsed:", json.dumps(u))
                    summary[f"request{rep}_http"] = 200
                    summary[f"request{rep}_cached_tokens"] = u["cached_tokens"]
                    summary[f"request{rep}_cached_source"] = u["cached_source"]
                    summary[f"request{rep}_prompt_tokens"] = u["prompt_tokens"]
                else:
                    summary[f"request{rep}_http"] = r.status
        body3 = {**body, "return_token_ids": True}
        async with http.post(srv.base_url.rstrip("/") + srv.completions_path, json=body3) as r:
            txt = await r.text()
            print(f"--- request 3 (return_token_ids=true): HTTP {r.status}")
            print(txt[:2000])
            summary["return_token_ids_http"] = r.status
            found = None
            if r.status == 200:
                data = json.loads(txt)
                for path in srv.output_ids_paths:
                    if extract_output_ids(data, [path]) is not None:
                        found = path
                        break
            summary["output_ids_path"] = found
            summary["output_ids_present"] = found is not None
        async with http.get(srv.base_url.rstrip("/") + srv.metrics_path) as r:
            t = await r.text()
            names = sorted({n for n, _, _ in parse_prometheus(t, cfg.metrics.prefixes, cfg.metrics.drop_suffixes)})
            print(f"--- /metrics HTTP {r.status}; {len(names)} names with prefixes {cfg.metrics.prefixes}:")
            print("\n".join(names))
            summary["metrics_http"] = r.status
            summary["n_metric_names"] = len(names)
    print("PROBE_SUMMARY " + json.dumps(summary, sort_keys=True))
    return 0


def cmd_probe(args: argparse.Namespace) -> int:
    cfg, _ = _load(args)
    return asyncio.run(_probe(cfg))


def cmd_canary(args: argparse.Namespace) -> int:
    """Start-state check (see agentload.canary). Prints ``CANARY_RESULT {json}``; writes the same JSON to --out.
    Exit 0 verified, 1 failed, 3 unverifiable."""
    cfg, _ = _load(args)
    prime = json.loads(Path(args.prime_json).read_text()) if args.prime_json else None
    rc, res = asyncio.run(run_canary(cfg, args.phase, args.salt, bool(args.cache_expected), prime))
    res["exit_code"] = rc
    txt = json.dumps(res, sort_keys=True)
    print("CANARY_RESULT " + txt)
    if args.out:
        Path(args.out).write_text(json.dumps(res, indent=2, sort_keys=True))
    return rc


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m agentload")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn, h in (("run", cmd_run, "run the load generator"), ("plan", cmd_plan, "print plan statistics only"),
                        ("probe", cmd_probe, "3 requests (incl. return_token_ids) + scrape /metrics, print raw output"),
                        ("canary", cmd_canary, "verify the engine is idle / the prefix cache is empty after a flush")):
        p = sub.add_parser(name, help=h)
        _common(p)
        if name == "plan":
            p.add_argument("--write", action="store_true", help="also write plan_stats.json + meta.json to a new results dir")
        if name == "canary":
            p.add_argument("--phase", required=True, choices=["prime", "check", "idle"])
            p.add_argument("--salt", type=int, required=True, help="selects the canary prompt (one per flush)")
            p.add_argument("--cache-expected", type=int, default=1, choices=[0, 1],
                           help="0: prefix caching is disabled in the engine; only the idle wait is checked")
            p.add_argument("--prime-json", default=None, help="(check) the prime phase's --out file")
            p.add_argument("--out", default=None, help="write the result JSON here")
        p.set_defaults(fn=fn)
    args = ap.parse_args(argv)
    return int(args.fn(args))
