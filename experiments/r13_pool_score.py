"""Score the A100 KV-pool sweep (150k / 600k; jobs 17168864-17168881) against the frozen round-13 theory.

Read-only on the pulled data.  Frozen inputs are read from git objects (never from a working tree):
  r13-theory-pred  (997d2c4)  results/theory/merged/a100_pool{150k,600k}.json, analysis/theory/merged/scoring.yaml
  r13-theory-pred2 (cfa7712)  results/theory/pred2/blind_tables.json (pool lookups, rival curves, Corollary C values)
Rules applied as frozen (notes/THEORY_r13_scoring.md, notes/PREDICTIONS_r13_pred2.md section 6 and 8):
  primary estimator turns-based; mu_max / window +-10%; peak n inside the measured flat top (grid points within 2% of the
  grid maximum) or the grid point next to it; n_half +-3 sessions; E0b bracket equal = hit, one grid step = near miss,
  two or more = miss; log-likelihood of the six E0b outcomes under F2 and under A's level crossing (floored at 1e-3);
  Corollary C rival rule: the predictor nearest the measured 0.5-hit crossing wins (M/E_S, M/E_lb, frozen n_half).

Usage (repo root):  python -I experiments/r13_pool_score.py <pull_dir>   -> <pull_dir>/derived/*
"""
from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from pathlib import Path

LREF = 0.07153402100919228          # prereg/inputs/2026-10-23/calibration.json (registered, full precision)
H = 3000.0                          # E0b horizon (s)
CELLS = {
    "150k": dict(label="sglang-fcfs-r1-p150k", closed="20261031-112201", stable="20261031-112204",
                 frozen="a100_pool150k", jobs_c="17168867-17168869", jobs_b="17168876-17168881"),
    "600k": dict(label="sglang-fcfs-r1-p600k", closed="20261031-112200", stable="20261031-112202",
                 frozen="a100_pool600k", jobs_c="17168864-17168866", jobs_b="17168870-17168875"),
}


def git_json(ref: str, path: str):
    out = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, check=True).stdout
    return json.loads(out)


def read_csv(p: Path):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def crossing(ns, hs, level=0.5):
    for (n0, h0), (n1, h1) in zip(zip(ns, hs), zip(ns[1:], hs[1:])):
        if h0 >= level > h1:
            return n0 + (n1 - n0) * (h0 - level) / (h0 - h1), [n0, n1]
    return math.nan, None


def interp_table(tab: dict, x: float) -> float:
    """Linear interpolation in a {str(mult): p} table; clamps to the end values."""
    pts = sorted((float(k), v) for k, v in tab.items())
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return math.nan


def p_escape_f2(lookup: dict, window_fluid: float, mult: float) -> float:
    """pred2 0.01-multiple F2 table; above the fluid window there is no good state (P = 1)."""
    if mult >= window_fluid:
        return 1.0
    return interp_table(lookup, mult)


def loglik(ps_unstable, outcomes_unstable, floor=1e-3):
    s = 0.0
    for p, u in zip(ps_unstable, outcomes_unstable):
        q = p if u else 1.0 - p
        s += math.log(max(q, floor))
    return s


def bracket_score(pred, meas, grid):
    """pred / meas = (largest stable, first unstable) with None for 'below the grid'; steps counted on the
    first-unstable index (the bracket's upper end), the grid being the run multiples."""
    def idx(v):
        return -1 if v is None else grid.index(v) if v in grid else None
    di = abs(idx(pred[1]) - idx(meas[1])) if idx(pred[1]) is not None and idx(meas[1]) is not None else None
    if di is None:
        return "n/a", None
    return ("hit" if di == 0 else "near miss" if di == 1 else "miss"), di


def main(pull: Path) -> None:
    res = pull / "results"
    out_dir = pull / "derived"
    out_dir.mkdir(exist_ok=True)
    scoring = subprocess.run(["git", "show", "r13-theory-pred:analysis/theory/merged/scoring.yaml"],
                             capture_output=True, check=True).stdout.decode()
    bt = git_json("r13-theory-pred2", "results/theory/pred2/blind_tables.json")
    report = dict(lambda_ref=LREF, frozen_tags=dict(pred="r13-theory-pred 997d2c4", pred2="r13-theory-pred2 cfa7712"),
                  scoring_yaml_sha_note="read from r13-theory-pred", cells={})
    point_rows, e0b_rows, score_rows = [], [], []
    for pool, c in CELLS.items():
        fz = git_json("r13-theory-pred", f"results/theory/merged/{c['frozen']}.json")
        lk = bt["pool_lookup"][c["frozen"]]
        rv = bt["rivals"][c["frozen"]]
        cc, win, edge = fz["closed_curve"], fz["window"], fz["from_empty_edge"]
        pts = [r for r in read_csv(res / "agentload_analysis_closed" / c["closed"] / "mu_curve.csv") if r["label"] == c["label"]]
        ns = [int(r["n"]) for r in pts]
        mt = [float(r["mu_turns_based"]) for r in pts]
        ms = [float(r["mu_sessions"]) for r in pts]
        hh = [float(r["hit_frac_turns"]) for r in pts]
        q = [float(r["queue_mean"]) for r in pts]
        finite = [i for i, n in enumerate(ns) if n < 300]
        it = max(finite, key=lambda i: mt[i])
        isn = max(finite, key=lambda i: ms[i])
        flat = [ns[i] for i in finite if mt[i] >= 0.98 * mt[it]]
        nh, nh_br = crossing([ns[i] for i in finite], [hh[i] for i in finite])
        # theory at the grid
        for i, n in enumerate(ns):
            g = lk["points_every_integer_n"].get(str(n))
            src = "pred2 lookup"
            fg = cc["grid_points"].get(f"{float(n)}") or cc["grid_points"].get(str(n))
            if g is None and fg is not None:
                g, src = fg, "frozen JSON grid point"
            sync = (fg or {}).get("stagec_synchronized") or {}
            point_rows.append(dict(pool=pool, n=n, theory_source=src if g else "",
                                   mu_turns=mt[i], mu_sessions=ms[i], hit=hh[i], queue_mean=q[i],
                                   sync_start_mu_turns_A=sync.get("mu_turns_based", ""),
                                   mu_F1=g["mu_annealed"] if g else "", hit_F1=g["hit_annealed"] if g else "",
                                   mu_fluid=g["mu_fluid"] if g else "", hit_fluid=g["hit_fluid"] if g else "",
                                   rel_err_F1_turns=(g["mu_annealed"] / mt[i] - 1) if g else "",
                                   che_hit=rv["che_W_eq_Z_hit"].get(str(n), ""),
                                   yao_little_hit=rv["yao_little_no_service_hit"].get(str(n), ""),
                                   below_n_b=n < fz["all_miss"]["n_b"]))
        mu_max_F1 = cc["annealed"]["mu_max"]
        window_F1 = win["annealed_vs_lambda_ref"]
        meas = dict(
            n=ns, mu_turns=mt, mu_sessions=ms, hit=hh, queue_mean=q,
            peak_n_turns=ns[it], mu_max_turns=mt[it], peak_n_sessions=ns[isn], mu_max_sessions=ms[isn],
            peak_ratio_turns=mt[it] / LREF, peak_ratio_sessions=ms[isn] / LREF, flat_top_2pct=flat,
            n_half=nh, n_half_grid_bracket=nh_br,
            mu_large_n={str(ns[i]): dict(turns=mt[i], sessions=ms[i], hit=hh[i]) for i in range(len(ns)) if hh[i] < 0.2},
        )
        # E0b
        st = read_csv(res / "agentload_analysis_stable" / c["stable"] / "stable_runs.csv")
        st = sorted([r for r in st if r["label"] == c["label"]], key=lambda r: float(r["rate_mult"]))
        grid = [float(r["rate_mult"]) for r in st]
        unstable = [r["stable"] != "True" for r in st]
        A_tab = edge["secondary_level_crossing"]["p_unstable_all"]
        rows = []
        for r, u in zip(st, unstable):
            m = float(r["rate_mult"])
            rd = pull / r["run_dir"]
            plan = read_csv(rd / "plan.csv")
            n_arr = sum(1 for p in plan if float(p["arrival_s"]) < H)
            real = n_arr / (H * LREF)
            p_f2 = p_escape_f2(lk["p_escape_every_0p01_mult"], win["vs_lambda_ref"], m)
            p_f2_real = p_escape_f2(lk["p_escape_every_0p01_mult"], win["vs_lambda_ref"], real)
            a_key = next((k for k in A_tab if abs(float(k) - m) < 1e-9), None)
            p_A = A_tab[a_key] if a_key else interp_table(A_tab, m)
            row = dict(pool=pool, mult=m, stable=not u, final_queue=float(r["final_queue"]), trend_rise=float(r["trend_rise"]),
                       aborted=r["aborted"], run_dir=r["run_dir"], sessions_arrived_lt_3000s=n_arr, realized_mult=real,
                       p_unstable_F2=p_f2, p_unstable_F2_realized=p_f2_real, p_unstable_A=p_A,
                       p_A_source="frozen table" if a_key else "linear interpolation of the frozen table")
            rows.append(row)
            e0b_rows.append(row)
        ls = max([r["mult"] for r in rows if r["stable"]], default=None)
        fu = min([r["mult"] for r in rows if not r["stable"] and (ls is None or r["mult"] > ls)], default=None)
        monotone = all(r["stable"] for r in rows if r["mult"] <= (ls or 0)) and all(not r["stable"] for r in rows if fu and r["mult"] >= fu)
        ls_real = max([r["realized_mult"] for r in rows if r["stable"]], default=None)
        fu_real = min([r["realized_mult"] for r in rows if not r["stable"]], default=None)
        # predicted bracket on THIS grid from the F2 50% edge
        e = edge["edge_mult"]
        pred_ls = max([m for m in grid if m < e], default=None)
        pred_fu = min([m for m in grid if m >= e], default=None)
        bscore, bsteps = bracket_score((pred_ls, pred_fu), (ls, fu), grid)
        eA = edge["secondary_level_crossing"]["edge50_mult"]
        predA = (max([m for m in grid if m < eA], default=None), min([m for m in grid if m >= eA], default=None))
        bscoreA, bstepsA = bracket_score(predA, (ls, fu), grid)
        ll_f2 = loglik([r["p_unstable_F2"] for r in rows], unstable)
        ll_f2r = loglik([r["p_unstable_F2_realized"] for r in rows], unstable)
        ll_A = loglik([r["p_unstable_A"] for r in rows], unstable)
        meas_e0b = dict(grid=grid, largest_stable=ls, first_unstable=fu, monotone=monotone,
                        realized_largest_stable=ls_real, realized_first_unstable=fu_real)
        # scoring rows (frozen rules)
        def rel(p, m_):
            return p / m_ - 1
        sc = []
        sc.append(("mu_max (turns, F1)", mu_max_F1, mt[it], rel(mu_max_F1, mt[it]), "hit" if abs(rel(mu_max_F1, mt[it])) <= 0.10 else "miss"))
        sc.append(("mu_max (sessions, F1; also reported)", mu_max_F1, ms[isn], rel(mu_max_F1, ms[isn]), "hit" if abs(rel(mu_max_F1, ms[isn])) <= 0.10 else "miss"))
        sc.append(("window mu_max/lambda_ref (turns, F1)", window_F1, mt[it] / LREF, rel(window_F1, mt[it] / LREF), "hit" if abs(rel(window_F1, mt[it] / LREF)) <= 0.10 else "miss"))
        fin_n = [ns[i] for i in finite]
        k = fin_n.index(ns[it])
        nbrs = set(flat) | {fin_n[j] for j in (k - 1, k + 1) if 0 <= j < len(fin_n)}
        pk = cc["annealed"]["peak_n"]
        lo, hi = min(nbrs), max(nbrs)
        sc.append(("peak n (F1)", pk, ns[it], None, "hit" if lo <= pk <= hi else "miss"))
        sc.append(("n_half 0.5-hit crossing (fluid)", cc["fluid"]["n_half"], nh, cc["fluid"]["n_half"] - nh, "hit" if abs(cc["fluid"]["n_half"] - nh) <= 3 else "miss"))
        sc.append(("n_half (F1; band)", cc["annealed"]["n_half"], nh, cc["annealed"]["n_half"] - nh, "hit" if abs(cc["annealed"]["n_half"] - nh) <= 3 else "miss"))
        sc.append(("E0b bracket (F2 edge %.2f x)" % e, f"[{pred_ls}, {pred_fu}]", f"[{ls}, {fu}]", bsteps, bscore))
        sc.append(("E0b bracket (A's crossing %.2f x; secondary)" % eA, f"[{predA[0]}, {predA[1]}]", f"[{ls}, {fu}]", bstepsA, bscoreA))
        refs = fz["scoring"]["cell"]["refutation"]
        if pool == "150k":
            i24 = ns.index(24)
            refuted = (mt[it] / LREF >= 2.5) or (hh[i24] >= 0.5)
            ref_txt = f"window {mt[it]/LREF:.3f} (< 2.5), hit(24) {hh[i24]:.3f} (< 0.5)"
        else:
            i48 = ns.index(48)
            refuted = (mt[it] / LREF < 4.5) or (hh[i48] < 0.5)
            ref_txt = f"window {mt[it]/LREF:.3f} (>= 4.5), hit(48) {hh[i48]:.3f} (>= 0.5)"
        sc.append(("refutation rules: " + "; ".join(refs), "", ref_txt, None, "REFUTED" if refuted else "not refuted"))
        for row in sc:
            score_rows.append(dict(pool=pool, quantity=row[0], predicted=row[1], measured=row[2], error=row[3], verdict=row[4]))
        # below-n_b mu points (F1 vs turns)
        below = [p for p in point_rows if p["pool"] == pool and p["below_n_b"] and p["mu_F1"] != ""]
        rms = math.sqrt(sum(p["rel_err_F1_turns"] ** 2 for p in below) / len(below)) if below else math.nan
        # rivals (Corollary C + Che / Yao)
        cands = {"M/E_S": rv["M_over_E_S"], "M/E_lb": rv["M_over_E_lb"], "frozen n_half (fluid)": rv["n_half_fluid"]}
        winner = min(cands, key=lambda kk: abs(cands[kk] - nh))
        thr = rv["M_over_E_S"] + 0.5 * (rv["n_b"] - rv["M_over_E_S"])
        rivals = dict(candidates=cands, errors={kk: v - nh for kk, v in cands.items()}, winner=winner,
                      tool_call_term_threshold=thr, tool_call_term_supported=nh > thr,
                      che_half_crossing=rv["che_half_crossing"], yao_little_half_crossing=rv["yao_little_half_crossing"],
                      che_error=rv["che_half_crossing"] - nh, yao_error=rv["yao_little_half_crossing"] - nh,
                      exogenous_nearest=min({"Che W=Z": rv["che_half_crossing"], "Yao-Little": rv["yao_little_half_crossing"],
                                             "frozen n_half (fluid)": rv["n_half_fluid"]}.items(), key=lambda kv: abs(kv[1] - nh))[0],
                      M_over_E_bar=rv["M_over_E_bar"], n_b=rv["n_b"], tool_call_part=rv["tool_call_part"])
        report["cells"][pool] = dict(
            label=c["label"], jobs_stage_c=c["jobs_c"], jobs_e0b=c["jobs_b"],
            analysis_closed=f"results/agentload_analysis_closed/{c['closed']}",
            analysis_stable=f"results/agentload_analysis_stable/{c['stable']}",
            measured=meas, e0b=meas_e0b, e0b_runs=rows,
            predicted=dict(F1=cc["annealed"], fluid={k2: cc["fluid"][k2] for k2 in ("peak_n", "mu_max", "hit_at_peak", "n_half", "n_b")},
                           window_F1=window_F1, window_fluid=win["vs_lambda_ref"], mu_b=fz["all_miss"]["lambda_miss_model_turns"],
                           edge_F2=e, edge_A=eA, edge_F2_bracket_frozen=edge["predicted_bracket"],
                           bracket_on_this_grid_F2=[pred_ls, pred_fu], bracket_on_this_grid_A=list(predA)),
            loglik=dict(F2=ll_f2, F2_realized_rate_band=ll_f2r, A_level_crossing=ll_A, floor=1e-3),
            rms_rel_err_F1_vs_turns_below_n_b=rms, n_points_below_n_b=len(below),
            rivals=rivals, refuted=refuted)
    with open(out_dir / "pool_sweep_scored.json", "w") as f:
        json.dump(report, f, indent=2, default=lambda o: None if isinstance(o, float) and math.isnan(o) else o)
    for name, rows in (("pool_sweep_mu_points.csv", point_rows), ("pool_sweep_e0b.csv", e0b_rows), ("pool_sweep_scoring.csv", score_rows)):
        with open(out_dir / name, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(json.dumps({p: dict(peak=v["measured"]["peak_n_turns"], ratio_t=v["measured"]["peak_ratio_turns"],
                              ratio_s=v["measured"]["peak_ratio_sessions"], n_half=v["measured"]["n_half"],
                              e0b=v["e0b"], ll=v["loglik"], rms=v["rms_rel_err_F1_vs_turns_below_n_b"],
                              rivals=v["rivals"]["winner"], refuted=v["refuted"]) for p, v in report["cells"].items()}, indent=1))
    for r in score_rows:
        print(r)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
