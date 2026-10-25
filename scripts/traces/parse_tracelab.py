"""Normalise the SyFI TraceLab public coding-agent trace (uw-syfi/TraceLab release v0.0.2, CC BY 4.0) into flat CSVs.

  python -I scripts/traces/parse_tracelab.py DATA.jsonl.gz OUTDIR

DATA is untrusted: it is only read with gzip + json (no eval, no pickle, nothing executed). One input line = one LLM
round (one model call); each round carries its tool calls with emitted_at / result_at and, when the runner reported it,
an internal duration. Output (one row per ...):

  calls.csv    tool call:  session, provider, model, episode, round, tool, wall_s, internal_s, best_s, is_error, result_chars, input_chars
  rounds.csv   LLM round:  session, provider, model, episode, round, pos_in_episode, input_total, prefix, new_append, output_tokens,
                           n_tools, z_round_s (last result - last tool_call emission), gap_next_s (next round's input ready - this
                           round's last output event), delta_ctx (context growth beyond prev input+output), ready_to_out_s, ...
  episodes.csv episode:    session, provider, episode, n_rounds, n_tool_rounds, first_input_total, wall_s, human_gap_before_s
  sessions.csv session:    session, provider, n_rounds, n_episodes, first_input_total

Definitions (also in notes/lit/AGENT_TRACES.md):
  * episode  = maximal run of consecutive rounds of one session that ends with the first round that issues no tool call
               (an autonomous agent run for one user prompt). Rounds of a session are ordered by round_index.
  * wall_s   = result_at - emitted_at (trace-observed; includes any permission-prompt wait and background-task effects)
  * internal_s = runner-reported duration (Claude durationMs/durationSeconds, Codex wrapper Wall time), only when logged
  * best_s   = internal_s if logged else wall_s (the trace authors' own precedence)
  * delta_ctx = input_total(k+1) - input_total(k) - output_tokens(k): tokens the client appended between two consecutive
               calls (tool output + any user text), i.e. the simulator's new_prompt_tokens (Delta). Negative = context compaction.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # our own scripts/traces, not the data directory
from common import tool_class  # noqa: E402

OUTPUT_EVENTS = {"reasoning", "text", "tool_call"}
INPUT_EVENTS = {"user_message", "tool_result"}


def ts_ms(s: str | None) -> float | None:
    if not s:
        return None
    return datetime.fromisoformat(s).timestamp() * 1000.0


def main(path: str, outdir: str) -> None:
    os.makedirs(outdir, exist_ok=True)
    sessions: dict[str, list[dict]] = defaultdict(list)
    users: set = set()
    models: dict[str, int] = defaultdict(int)
    t_min = t_max = None
    n_lines = 0
    bad = 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n_lines += 1
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                bad += 1
                continue
            evs = r.get("timing_events") or []
            users.add(r.get("user"))
            models[f"{r.get('provider')}:{r.get('model')}"] += 1
            for e in evs[:1] + evs[-1:]:
                tt = ts_ms(e.get("timestamp"))
                if tt is not None:
                    t_min = tt if t_min is None else min(t_min, tt)
                    t_max = tt if t_max is None else max(t_max, tt)
            inp = [ts_ms(e.get("timestamp")) for e in evs if e.get("event_type") in INPUT_EVENTS]
            out = [ts_ms(e.get("timestamp")) for e in evs if e.get("event_type") in OUTPUT_EVENTS]
            # input events that precede the first output event (the ones this round is waiting for)
            ready = None
            first_out = None
            for e in evs:
                t = e.get("event_type")
                if t in OUTPUT_EVENTS:
                    first_out = ts_ms(e.get("timestamp"))
                    break
            pre_inputs = []
            for e in evs:
                t = e.get("event_type")
                if t in OUTPUT_EVENTS:
                    break
                if t in INPUT_EVENTS:
                    pre_inputs.append(ts_ms(e.get("timestamp")))
            if pre_inputs:
                ready = max(x for x in pre_inputs if x is not None)
            tools = []
            for t in r.get("tools") or []:
                tools.append({
                    "name": t.get("tool_name"),
                    "emit": ts_ms(t.get("emitted_at")),
                    "res": ts_ms(t.get("result_at")),
                    "wall": t.get("tool_wall_latency_ms"),
                    "internal": t.get("tool_internal_latency_ms"),
                    "err": bool(t.get("is_error")),
                    "rc": t.get("result_chars"),
                    "ic": t.get("input_chars"),
                })
            sessions[r["session_id"]].append({
                "provider": r.get("provider"), "model": r.get("model"), "user": r.get("user"),
                "ri": r.get("round_index"),
                "inp": r.get("input_tokens_total"),
                "prefix": r.get("prefix_tokens"), "new": r.get("newly_append_tokens"),
                "out": r.get("output_tokens"), "first_in": r.get("first_input_event_type"),
                "ready": ready, "first_out": first_out,
                "last_out": max([x for x in out if x is not None], default=None),
                "tools": tools,
                "n_user": r.get("current_user_message_count"),
            })
    print(f"read {n_lines} rounds, {bad} unparseable, {len(sessions)} sessions", file=sys.stderr)
    info = {"n_rounds": n_lines, "n_unparseable": bad, "n_sessions": len(sessions), "n_users": len(users),
            "first_event_utc": datetime.fromtimestamp(t_min / 1000.0).astimezone().isoformat() if t_min else None,
            "last_event_utc": datetime.fromtimestamp(t_max / 1000.0).astimezone().isoformat() if t_max else None,
            "rounds_by_model": dict(sorted(models.items(), key=lambda kv: -kv[1]))}
    with open(os.path.join(outdir, "dataset_info.json"), "w", encoding="utf-8") as fi:
        json.dump(info, fi, indent=1)

    f_calls = open(os.path.join(outdir, "calls.csv"), "w", newline="", encoding="utf-8")
    f_rounds = open(os.path.join(outdir, "rounds.csv"), "w", newline="", encoding="utf-8")
    f_eps = open(os.path.join(outdir, "episodes.csv"), "w", newline="", encoding="utf-8")
    f_sess = open(os.path.join(outdir, "sessions.csv"), "w", newline="", encoding="utf-8")
    w_calls = csv.writer(f_calls)
    w_rounds = csv.writer(f_rounds)
    w_eps = csv.writer(f_eps)
    w_sess = csv.writer(f_sess)
    w_calls.writerow(["session", "provider", "model", "episode", "round", "tool", "cls", "wall_s", "internal_s", "best_s", "is_error", "result_chars", "input_chars"])
    w_rounds.writerow(["session", "provider", "model", "episode", "round", "pos_in_episode", "input_total", "prefix", "new_append", "output_tokens",
                       "n_tools", "classes", "z_round_s", "gap_next_s", "delta_ctx", "ready_to_out_s", "first_input_event"])
    w_eps.writerow(["session", "provider", "episode", "n_rounds", "n_tool_rounds", "first_input_total", "wall_s", "human_gap_before_s"])
    w_sess.writerow(["session", "provider", "n_rounds", "n_episodes", "first_input_total"])

    def s(x):
        return "" if x is None else f"{x:.6g}" if isinstance(x, float) else x

    for sid, rounds in sessions.items():
        rounds.sort(key=lambda d: (d["ri"] if d["ri"] is not None else 0))
        prov = rounds[0]["provider"]
        # episode segmentation
        ep = 0
        pos = 0
        ep_rounds: dict[int, list[int]] = defaultdict(list)
        for i, d in enumerate(rounds):
            d["ep"] = ep
            d["pos"] = pos
            ep_rounds[ep].append(i)
            pos += 1
            if not d["tools"]:
                ep += 1
                pos = 0
        for i, d in enumerate(rounds):
            nxt = rounds[i + 1] if i + 1 < len(rounds) else None
            same_ep_next = nxt is not None and nxt["ep"] == d["ep"]
            tools = d["tools"]
            z_round = None
            if tools:
                emits = [t["emit"] for t in tools if t["emit"] is not None]
                ress = [t["res"] for t in tools if t["res"] is not None]
                if emits and ress:
                    z_round = max(0.0, (max(ress) - max(emits)) / 1000.0)
            gap_next = None
            if same_ep_next and tools and nxt["ready"] is not None:
                end_out = d["last_out"]
                if end_out is not None:
                    gap_next = (nxt["ready"] - end_out) / 1000.0
            delta = None
            if same_ep_next and nxt["inp"] is not None and d["inp"] is not None and d["out"] is not None:
                delta = nxt["inp"] - d["inp"] - d["out"]
            r2o = None
            if d["ready"] is not None and d["first_out"] is not None:
                r2o = (d["first_out"] - d["ready"]) / 1000.0
            w_rounds.writerow([sid, prov, d["model"], d["ep"], i, d["pos"], s(d["inp"]), s(d["prefix"]), s(d["new"]), s(d["out"]),
                               len(tools), "+".join(sorted({tool_class(x["name"]) for x in tools})), s(z_round), s(gap_next), s(delta), s(r2o), d["first_in"]])
            for t in tools:
                wall = t["wall"] / 1000.0 if t["wall"] is not None else None
                internal = t["internal"] / 1000.0 if t["internal"] is not None else None
                best = internal if internal is not None else wall
                w_calls.writerow([sid, prov, d["model"], d["ep"], i, t["name"], tool_class(t["name"]), s(wall), s(internal), s(best), int(t["err"]), s(t["rc"]), s(t["ic"])])
        prev_end = None
        for e, idxs in sorted(ep_rounds.items()):
            rs = [rounds[i] for i in idxs]
            t_first = rs[0]["ready"]
            t_last = max([x for x in (r["last_out"] for r in rs) if x is not None] +
                         [t["res"] for r in rs for t in r["tools"] if t["res"] is not None], default=None)
            wall = (t_last - t_first) / 1000.0 if (t_first is not None and t_last is not None) else None
            gap = (t_first - prev_end) / 1000.0 if (t_first is not None and prev_end is not None) else None
            w_eps.writerow([sid, prov, e, len(rs), sum(1 for r in rs if r["tools"]), s(rs[0]["inp"]), s(wall), s(gap)])
            prev_end = t_last
        w_sess.writerow([sid, prov, len(rounds), len(ep_rounds), s(rounds[0]["inp"])])
    for fh in (f_calls, f_rounds, f_eps, f_sess):
        fh.close()
    print("wrote", outdir, file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
