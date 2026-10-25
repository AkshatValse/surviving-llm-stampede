"""Normalise mini-SWE-agent v2.x trajectories (SWE-bench 'bash-only' leaderboard runs) into flat CSVs.

  python -I scripts/traces/parse_mini_swe.py DATA_DIR OUTDIR

DATA_DIR/<run>/<instance>.traj.json (untrusted JSON; only json.load is applied). In format mini-swe-agent-1.1 every
assistant message has extra.timestamp (set when the model response has come back) and every tool message has
extra.timestamp (set when the shell command in the SWE-bench docker container has returned), plus extra.returncode and
extra.exception_type. Hence, per assistant message k with tool messages j = 1..m following it:

  tool phase wall time = ts(last tool message) - ts(assistant_k)                               = `docker exec` command time
                         (for a step with several commands only the phase total is observable: the result messages
                          of one step are stamped together after the last command)
  llm_s            = ts(assistant_k) - ts(last tool message of step k-1)                       = model call latency + client overhead

A tool call that hit the harness limit (returncode -1, TimeoutExpired, 60 s) is flagged censored=1. The final assistant
message (the submit command) is not followed by a tool message, so a trajectory with T model calls has T-1 timed tool phases,
exactly the simulator's convention (T turns, T-1 tool times). Format-error retries (assistant message followed by a user
message instead of a tool message) have no tool phase and are counted in n_noop.

Outputs: calls.csv, rounds.csv, episodes.csv (one episode = one trajectory), sessions.csv (same as episodes, kept for symmetry).
"""
from __future__ import annotations

import csv
import json
import os
import sys


def main(data_dir: str, outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    f_calls = open(os.path.join(outdir, "calls.csv"), "w", newline="", encoding="utf-8")
    f_rounds = open(os.path.join(outdir, "rounds.csv"), "w", newline="", encoding="utf-8")
    f_eps = open(os.path.join(outdir, "episodes.csv"), "w", newline="", encoding="utf-8")
    w_calls, w_rounds, w_eps = csv.writer(f_calls), csv.writer(f_rounds), csv.writer(f_eps)
    w_calls.writerow(["session", "provider", "model", "episode", "round", "tool", "wall_s", "internal_s", "best_s", "is_error", "censored",
                      "returncode", "result_chars", "n_parallel"])
    w_rounds.writerow(["session", "provider", "model", "episode", "round", "pos_in_episode", "input_total", "prefix", "new_append",
                       "output_tokens", "n_tools", "z_round_s", "gap_next_s", "delta_ctx", "d_in", "llm_s", "cached_tokens"])
    w_eps.writerow(["session", "provider", "episode", "n_rounds", "n_tool_rounds", "first_input_total", "wall_s", "human_gap_before_s",
                    "exit_status", "n_noop", "n_timeouts", "total_tool_s"])
    n_files = 0
    n_skipped = 0
    for run in sorted(os.listdir(data_dir)):
        rdir = os.path.join(data_dir, run)
        if not os.path.isdir(rdir):
            continue
        model = run.split("mini-v2.0.0_", 1)[-1]
        for fn in sorted(os.listdir(rdir)):
            if not fn.endswith(".traj.json"):
                continue
            with open(os.path.join(rdir, fn), encoding="utf-8") as f:
                d = json.load(f)
            inst = fn[: -len(".traj.json")]
            sid = f"{model}:{inst}"
            msgs = d.get("messages") or []
            if d.get("trajectory_format") not in ("mini-swe-agent-1.1",):
                n_skipped += 1
                continue
            n_files += 1
            rounds = []          # dicts for assistant steps
            cur = None
            last_ts = None       # timestamp of the last tool (or non-tool) message before the next assistant message
            n_noop = 0
            for m in msgs:
                role = m.get("role")
                if role is None:            # OpenAI Responses-API runs store the raw response / function_call_output objects as messages
                    if m.get("object") == "response":
                        role = "assistant"
                    elif m.get("type") == "function_call_output":
                        role = "tool"
                ex = m.get("extra") or {}
                ts = ex.get("timestamp")
                if role == "assistant":
                    if m.get("object") == "response":                     # Responses API: usage at the message level
                        usage = m.get("usage") or {}
                        ptd = usage.get("input_tokens_details") or {}
                        inp, out = usage.get("input_tokens"), usage.get("output_tokens")
                    else:                                                  # chat completions: usage inside extra.response
                        usage = ((ex.get("response") or {}).get("usage")) or {}
                        ptd = usage.get("prompt_tokens_details") or {}
                        inp, out = usage.get("prompt_tokens"), usage.get("completion_tokens")
                    cur = {"ts": ts, "llm": (ts - last_ts) if (ts is not None and last_ts is not None) else None,
                           "inp": inp, "out": out,
                           "cached": (ptd.get("cached_tokens") or 0) + (usage.get("cache_read_input_tokens") or 0),
                           "n_actions": len(ex.get("actions") or []), "tools": []}
                    rounds.append(cur)
                    last_ts = ts
                elif role == "tool" and cur is not None:
                    prev = cur["tools"][-1]["ts"] if cur["tools"] else cur["ts"]
                    lat = (ts - prev) if (ts is not None and prev is not None) else None
                    rc = ex.get("returncode")
                    cur["tools"].append({"ts": ts, "lat": lat, "rc": rc, "exc": ex.get("exception_type"),
                                         "chars": len(ex.get("raw_output") or "")})
                    last_ts = ts
                elif role == "user" and cur is not None:
                    # format-error / retry message inserted instead of a tool result
                    if not cur["tools"]:
                        n_noop += 1
                        if ts is not None:
                            last_ts = ts
            T = len(rounds)
            n_to = 0
            tot_tool = 0.0
            for k, r in enumerate(rounds):
                nxt = rounds[k + 1] if k + 1 < T else None
                z = None
                if r["tools"] and r["tools"][-1]["ts"] is not None and r["ts"] is not None:
                    z = r["tools"][-1]["ts"] - r["ts"]
                    tot_tool += z
                gap_next = (nxt["ts"] - r["ts"]) if (nxt is not None and nxt["ts"] is not None and r["ts"] is not None) else None
                delta = d_in = None
                if nxt is not None and nxt["inp"] is not None and r["inp"] is not None:
                    d_in = nxt["inp"] - r["inp"]
                    if r["out"] is not None:
                        delta = d_in - r["out"]
                w_rounds.writerow([sid, "mini-swe-agent", model, 0, k, k, r["inp"], r["cached"], "", r["out"], len(r["tools"]),
                                   "" if z is None else f"{z:.6g}", "" if gap_next is None else f"{gap_next:.6g}",
                                   "" if delta is None else delta, "" if d_in is None else d_in,
                                   "" if r["llm"] is None else f"{r['llm']:.6g}", r["cached"]])
                if r["tools"] and z is not None:
                    # One row per tool PHASE. When a step issues several commands (parallel_tool_calls) the harness runs them
                    # one after the other but stamps all result messages at the end, so only the phase total is observable.
                    cens = int(any(t["rc"] == -1 and t["exc"] == "TimeoutExpired" for t in r["tools"]))
                    bad = int(any(t["rc"] not in (0, None) for t in r["tools"]))
                    w_calls.writerow([sid, "mini-swe-agent", model, 0, k, "bash", f"{z:.6g}", "", f"{z:.6g}", bad, cens,
                                      r["tools"][-1]["rc"], sum(t["chars"] for t in r["tools"]), len(r["tools"])])
                if r["tools"]:
                    n_to += 1
            tss = [r["ts"] for r in rounds if r["ts"] is not None] + [t["ts"] for r in rounds for t in r["tools"] if t["ts"] is not None]
            wall = (max(tss) - min(tss)) if tss else None
            n_to_cnt = sum(1 for r in rounds for t in r["tools"] if t["rc"] == -1 and t["exc"] == "TimeoutExpired")
            w_eps.writerow([sid, "mini-swe-agent", 0, T, n_to, rounds[0]["inp"] if rounds else "", "" if wall is None else f"{wall:.6g}", "",
                            (d.get("info") or {}).get("exit_status"), n_noop, n_to_cnt, f"{tot_tool:.6g}"])
    for fh in (f_calls, f_rounds, f_eps):
        fh.close()
    print(f"parsed {n_files} trajectories ({n_skipped} skipped for format) into {outdir}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
