"""B2 (remedy N1): the basin dose-response at 1.65 x lambda_ref on the A100 300k cell, with per-seed P(STUCK) on the exact
client plans of seeds 0-2 (registrations configs/agentload_prereg_2026-10-31_b{40,50,60}.yaml on branch r11/strengthen,
commit 621d88f: BURST arm only, burst n in 60 s at 1200 s, seeds 0-2, STUCK := hit < 0.2 over [5700, 8700) s, GOOD :=
RECOVERED or (hit > 0.8 and slope <= threshold); rule: bracketed iff b = 40 GOOD in >= 2/3 and b = 60 STUCK in >= 2/3).

    PYTHONPATH="src;." python -m analysis.theory.pred2.b2            # -> results/theory/pred2/b2_basin.json

Layers (all frozen except where marked NEW):
  * deterministic critical burst b_c: the frozen F3 (fluid_rigorous.model.critical_burst_fresh);
  * committor: the frozen extras.burst_trap_probability, X0 = D_live^-1(D_live(n1) + b * 4,331), P(STUCK) = q + (1 - q) P_esc
    (escape before the stuck-by time 6,344 s);
  * NEW (GOOD side): P(GOOD) = (1 - q)(1 - P_esc(until 8,275 s)), 8,275 s being the earliest escape that still leaves
    the window hit above 0.8; P(neither) = the rest.  The frozen B1 P(PASS) counted every non-trapped run as GOOD;
  * NEW (exact plans, PRIMARY per seed): the frozen layer's expected cohort peak b * 4,331 is replaced by the seed's
    REALIZED cohort peak, the maximum over t of the live KV of the plan's burst sessions (the frozen extras._live_paths fed
    with their arrival times, turn counts and tool times; good-state service S(n1) = 1.33 s per turn), on the frozen mean
    background D_live(n1): b_eff = cohort peak / 4,331.  Review fix (2026-10-31): that time maximum does not average to b (it
    picks up the cohort's own noise, +29% at b = 10, +6% at b = 40 over the synthetic seeds), so it is CALIBRATED to the
    frozen layer's scale, b_cal = b_eff * b / E_synth[b_eff(b)], and b_cal is passed to the frozen committor.  This keeps the
    frozen construction and conditions only on the burst sessions' deviation from an average cohort (the treatment); the
    raw b_eff is kept as a band (band_raw_time_maximum);
  * bands: the lockstep cohort peak with the realized turn counts (max_j E_j #{T_i >= j}); the cohort at a 2.5 s service
    time; the realized background of the plan at the cohort's peak instant (X0 = D_live^-1(background(t*) + cohort(t*)));
    the background escape at the realized post-burst arrival rate.  (A maximum over a window of background + cohort is NOT
    used: it double counts the background noise that the committor already carries; over synthetic seeds it gives P(STUCK)
    0.18 at b = 25 against the 0.03 background escape of F2.)
  * NEW (reference): the composition-averaged P(STUCK) of a seed whose plan is unknown (400 synthetic seeds of the same
    client generator, 1000-1399), which shows how much of the per-seed spread is cohort composition;
  * secondary (A's level crossing on the exact plan, deterministic): the plan's live KV of all sessions (base + burst)
    first reaches D_live(n_u) before the stuck-by time (STUCK) / not before 8,275 s (GOOD).
"""
from __future__ import annotations

import argparse
import math
from typing import Dict, List, Sequence

import numpy as np

from ..fluid_rigorous.edge import escape_probability
from ..fluid_rigorous.model import cohort_peak_kv, critical_burst_fresh, live_demand, mu_good_of_n, open_equilibria
from ..merged import extras as X
from .common import (E2_CONFIG, LREF_300K_REG, at_least, burst_cohort, cell, client_plan, eval_times, frozen_json,
                     live_path, plan_arrays, write_json)

CELL = "a100_300k"
T_B, WIDTH, WIN = 1200.0, 60.0, (5700.0, 8700.0)
SIZES = [0, 10, 25, 40, 50, 60, 75, 100, 150, 200]
PLAN_SIZES = [10, 25, 40, 50, 60, 75, 100, 150, 200]   # registered (B1: 25, 100; B2: 40, 50, 60) or committed (E2: 200)
SEEDS = [0, 1, 2]
SYNTH_SEEDS = list(range(1000, 1400))
REG_FILES = ["configs/agentload_e2_burst.yaml"]


def _rows(c, lam: float, bursts: Sequence[float], stuck_by: float, good_from: float) -> Dict[str, object]:
    """Frozen committor rows for (possibly non-integer) burst sizes, plus the NEW GOOD / neither split."""
    r = X.burst_trap_probability(c.m, c.cs, lam, list(bursts), c.I_D, t_b=T_B, burst_w=WIDTH, stuck_by_s=stuck_by)
    H_good = max(good_from - (T_B + WIDTH + r["peak_delay_s"]), 0.0)
    p_bg_good = escape_probability(c.mu_f, lam, c.I_D, c.cs.n_b, H_good)["p_escape"]
    for row in r["rows"]:
        q = row["committor"]
        row["p_stuck"] = row["p_trapped"]
        row["p_good"] = (1.0 - q) * (1.0 - p_bg_good)
        row["p_neither"] = max(0.0, 1.0 - row["p_stuck"] - row["p_good"])
    r["horizon_good_s"] = H_good
    r["p_escape_background_good_horizon"] = p_bg_good
    return r


def _noburst(c, lam: float, stuck_by: float, good_from: float) -> Dict[str, float]:
    """b = 0 under the NOBURST protocol: F2 escape from empty at t = 0 (horizon = the stuck-by / good-from times)."""
    pe_s = escape_probability(c.mu_f, lam, c.I_D, c.cs.n_b, stuck_by)["p_escape"]
    pe_g = escape_probability(c.mu_f, lam, c.I_D, c.cs.n_b, good_from)["p_escape"]
    return dict(burst=0.0, p_stuck=pe_s, p_good=1.0 - pe_g, p_neither=pe_g - pe_s, horizon_stuck_s=stuck_by,
                horizon_good_s=good_from, note="NOBURST protocol (from empty at t = 0); the frozen function's b = 0 row "
                                               "uses the post-burst horizon instead")


def _crit(c, lam: float, stuck_by: float, good_from: float) -> Dict[str, float]:
    det = critical_burst_fresh(c.m, c.cs, lam)
    grid = np.round(np.arange(20.0, 70.0001, 0.05), 4)
    r = _rows(c, lam, grid, stuck_by, good_from)
    q = np.array([row["committor"] for row in r["rows"]])
    ps = np.array([row["p_stuck"] for row in r["rows"]])

    def cross(y):
        j = int(np.argmax(y >= 0.5))
        return float(grid[j - 1] + (0.5 - y[j - 1]) / (y[j] - y[j - 1]) * (grid[j] - grid[j - 1])) if j > 0 else math.nan

    return dict(b_crit_deterministic=det["b_fresh"], b_stat=det["b_stat"], n1=det["n1"], n_u=det["n_u"],
                b_committor_50=cross(q), b_p_stuck_50=cross(ps))


def _cohort_peaks(c, lam: float, sessions, S: float) -> Dict[str, float]:
    """Realized peak live KV of a burst cohort: time-resolved (frozen _live_paths on the plan) and lockstep."""
    cpk, _ = cohort_peak_kv(c.m.wl)
    arr, T, Z = plan_arrays(sessions)
    V = live_path(c.m, arr, T, Z, S, T_B + 1500.0)
    Tn = np.asarray(T)
    lock = _lockstep(c, T)
    return dict(peak_time_resolved=float(V.max()), t_peak_after_burst_s=float(np.argmax(V) - T_B),
                peak_lockstep=lock, b_eff=float(V.max()) / cpk, b_eff_lockstep=lock / cpk, mean_turns=float(Tn.mean()))


def _lockstep(c, n_turns) -> float:
    """Lockstep peak live KV of a cohort with the given turn counts: max_j E_j #{T_i >= j}."""
    Tn = np.asarray(n_turns)
    surv = np.array([(Tn >= j).sum() for j in range(1, c.m.wl.K + 1)])
    return float((surv * c.m.wl.E).max())


BRACKET_TAGS = ("primary", "band_raw_time_maximum", "band_lockstep", "band_service_2p5s", "band_realized_background_at_peak",
                "band_raw_lockstep", "band_raw_service_2p5s", "band_raw_realized_background_at_peak")


def _level_crossing(V: np.ndarray, V2: float, stuck_by: float, good_from: float) -> Dict[str, object]:
    idx = np.nonzero(V >= V2)[0]
    t_x = float(idx[0]) if len(idx) else math.nan
    label = "STUCK" if (len(idx) and t_x < stuck_by) else ("GOOD" if (not len(idx) or t_x >= good_from) else "neither")
    return dict(first_crossing_s=t_x, label=label, peak_live_kv=float(V.max()), V2=V2)


def _paths(c, sessions, S: float) -> np.ndarray:
    arr, T, Z = plan_arrays(sessions)
    return live_path(c.m, arr, T, Z, S, WIN[1])


def run(mult: float = 1.65, synth: int = len(SYNTH_SEEDS), quick: bool = False, plans: bool = True) -> Dict[str, object]:
    c = cell(CELL)
    lam = mult * c.lam_ref
    gs = X.good_state(c.m, c.cs, lam)
    stuck_by, good_from = eval_times(gs["hit"], *WIN)
    S1 = float(gs["S_bar"])
    out: Dict[str, object] = dict(cell=CELL, mult=mult, lam=lam, lambda_ref_theory=c.lam_ref, lambda_ref_plans=LREF_300K_REG,
                                  good_state=gs, stuck_by_s=stuck_by, good_from_s=good_from, S_bar_n1=S1,
                                  cohort_peak_kv=cohort_peak_kv(c.m.wl)[0])
    # ---- exchangeable rows (frozen layer, cohort at its mean) + the NOBURST protocol row
    ex = _rows(c, lam, SIZES, stuck_by, good_from)
    out["exchangeable"] = ex
    out["noburst_protocol"] = _noburst(c, lam, stuck_by, good_from)
    out["critical"] = _crit(c, lam, stuck_by, good_from)
    # ---- frozen-record check (the B1 rows of the tag must be reproduced exactly)
    if abs(mult - 1.65) < 1e-12:
        fz = {float(r["burst"]): r for r in frozen_json("b1_basin_300k")["tests"]["B1"]["result"]["rows"]}
        out["frozen_check_max_abs_diff"] = max(abs(r["p_trapped"] - fz[r["burst"]]["p_trapped"]) for r in ex["rows"] if r["burst"] in fz)
    # ---- demand levels of the frozen good curve (for the plan-conditional mapping)
    ng, _ = mu_good_of_n(c.cs)
    pts = c.cs.pts[: len(ng)]
    n_arr = np.array([p["n"] for p in pts])
    D_arr = np.array([live_demand(c.m, p) for p in pts])
    o = np.argsort(n_arr)
    eq = open_equilibria(c.cs, lam)
    V2 = float(np.interp(eq.n_u, n_arr[o], D_arr[o]))
    D1 = float(np.interp(eq.n1, n_arr[o], D_arr[o]))            # the frozen layer's background demand D_live(n1)
    cpk = cohort_peak_kv(c.m.wl)[0]
    i0, i1 = int(T_B), int(T_B + 600.0)
    out["demand_levels"] = dict(D_live_n1=D1, D_live_n_u=V2, D_live_n_b=float(D_arr[o][-1]), peak_window_s=[T_B, T_B + 600.0])
    # ---- composition-averaged reference and the CALIBRATION of the plan statistic (review fix, 2026-10-31): synthetic seeds of
    #      the same client generator (full plans: base + burst).  The time maximum of a realized cohort's live KV does not
    #      average to b * cpk: it picks up the cohort's own noise (mean b_eff 12.9 / 27.6 / 42.3 / 51.5 / 61.2 at b = 10 / 25 /
    #      40 / 50 / 60 over seeds 1000-1399), the noise that the committor's F2 diffusion carries a second time.  The plan
    #      statistic is therefore put on the frozen layer's scale, b_cal = b_eff * b / E_synth[b_eff(b)], before the frozen
    #      committor is called (lockstep: its own factor; 2.5 s service: the time-resolved factor at S(n1), so that the service
    #      shift is kept; realized background: the cohort part calibrated, the background deviation added as it is).  The raw
    #      (uncalibrated) statistics are kept as bands.
    seeds = SYNTH_SEEDS[: (60 if quick else synth)]
    grid_b = sorted(set(SIZES[1:]) | set(range(30, 71, 5)))
    raw = dict(coh=[], bg=[], lock=[])
    keys, sids = [], []
    for sd in seeds:
        p0, _ = client_plan(E2_CONFIG, sd, mult, WIN[1], 0)
        Vbg = _paths(c, p0, S1)
        for b in grid_b:
            coh = burst_cohort(sd, b, T_B, WIDTH)
            Vb = _paths(c, coh, S1)
            j = int(np.argmax(Vb))
            raw["coh"].append(float(Vb[j]) / cpk)
            raw["bg"].append((float(Vbg[j]) - D1) / cpk)
            raw["lock"].append(_lockstep(c, [t for _, t, _ in coh]) / cpk)
            keys.append(b)
            sids.append(sd)
    mean_raw = {st: {b: float(np.mean([v for v, k in zip(raw[st], keys) if k == b])) for b in grid_b} for st in ("coh", "lock")}
    cal = {st: {b: mean_raw[st][b] / b for b in grid_b} for st in ("coh", "lock")}
    out["calibration"] = dict(
        rule="b_cal = b_eff * b / E_synth[b_eff(b)] (per burst size b, over the synthetic seeds), so that E_synth[b_cal] = b: the "
             "plan statistic on the frozen layer's scale (the frozen layer maps b to D_live(n1) + b * cpk)",
        n_seeds=len(seeds), seeds=[seeds[0], seeds[-1]],
        factor_time_resolved={str(b): cal["coh"][b] for b in grid_b}, factor_lockstep={str(b): cal["lock"][b] for b in grid_b},
        mean_b_eff_raw_time_resolved={str(b): mean_raw["coh"][b] for b in grid_b},
        mean_b_eff_raw_lockstep={str(b): mean_raw["lock"][b] for b in grid_b},
        mean_background_deviation_at_peak=float(np.mean(raw["bg"])))
    coh_cal = [v / cal["coh"][k] for v, k in zip(raw["coh"], keys)]
    stats = {"primary_calibrated": coh_cal,
             "band_realized_background_at_peak_calibrated": [x + g for x, g in zip(coh_cal, raw["bg"])],
             "band_raw_time_maximum": raw["coh"],
             "band_raw_realized_background_at_peak": [x + g for x, g in zip(raw["coh"], raw["bg"])]}
    comp = {}
    for tag, vals in stats.items():
        rr = _rows(c, lam, vals, stuck_by, good_from)["rows"]
        rows = {}
        for b in grid_b:
            sel = [row for row, k in zip(rr, keys) if k == b]
            be = np.array([row["burst"] for row in sel])
            rows[str(b)] = dict(b_eff_mean=float(be.mean()), b_eff_sd=float(be.std()), b_eff_q10=float(np.quantile(be, 0.1)),
                                b_eff_q90=float(np.quantile(be, 0.9)), p_stuck=float(np.mean([row["p_stuck"] for row in sel])),
                                p_good=float(np.mean([row["p_good"] for row in sel])),
                                p_neither=float(np.mean([row["p_neither"] for row in sel])), n_seeds=len(sel))
        bs = np.array(grid_b, float)
        ps = np.array([rows[str(b)]["p_stuck"] for b in grid_b])
        j = int(np.argmax(ps >= 0.5))
        comp[tag] = dict(rows=rows, b_p_stuck_50=float(bs[j - 1] + (0.5 - ps[j - 1]) / (ps[j] - ps[j - 1]) * (bs[j] - bs[j - 1]))
                         if j > 0 else math.nan)
        # the bracketing rule for three random seeds: per synthetic seed, the joint law of (b40 GOOD, b60 STUCK) (runs
        # independent given the seed), averaged over seeds; then three i.i.d. seeds
        pg = {sd: row["p_good"] for row, k, sd in zip(rr, keys, sids) if k == 40}
        pst = {sd: row["p_stuck"] for row, k, sd in zip(rr, keys, sids) if k == 60}
        cell4 = {(1, 1): float(np.mean([pg[x] * pst[x] for x in pg])), (1, 0): float(np.mean([pg[x] * (1 - pst[x]) for x in pg])),
                 (0, 1): float(np.mean([(1 - pg[x]) * pst[x] for x in pg])),
                 (0, 0): float(np.mean([(1 - pg[x]) * (1 - pst[x]) for x in pg]))}
        comp[tag]["p_rule_three_random_seeds"] = sum(cell4[a] * cell4[b] * cell4[cc] for a in cell4 for b in cell4 for cc in cell4
                                                     if a[0] + b[0] + cc[0] >= 2 and a[1] + b[1] + cc[1] >= 2)
    comp["seeds"] = [seeds[0], seeds[-1]]
    out["composition_averaged"] = comp
    if not plans:
        return out
    # ---- exact plans, seeds 0-2 (PRIMARY per seed: the calibrated time-resolved cohort peak)
    per_seed = {}
    for sd in SEEDS:
        recs = {}
        p0, rate0 = client_plan(E2_CONFIG, sd, mult, WIN[1], 0)
        base0 = [s for s in p0 if s.origin == "base"]
        Vbg = _paths(c, base0, S1)
        n_post = sum(1 for s in base0 if T_B <= s.arrival_s < stuck_by)
        lam_post = n_post / (stuck_by - T_B) * (c.lam_ref / LREF_300K_REG)      # realized rate in theory units
        recs["0"] = dict(n_base=len(base0), realized_rate_mult_0_8700=len(base0) / (WIN[1] * LREF_300K_REG),
                         realized_rate_mult_post_burst=n_post / ((stuck_by - T_B) * LREF_300K_REG),
                         background_live_kv=dict(mean_600_8700=float(Vbg[600:8700].mean()), sd_600_8700=float(Vbg[600:8700].std()),
                                                 max_peak_window=float(Vbg[i0:i1].max())),
                         level_crossing=_level_crossing(Vbg, V2, stuck_by, good_from))
        for b in PLAN_SIZES:
            plan, _ = client_plan(E2_CONFIG, sd, mult, WIN[1], b, T_B, WIDTH)
            burst = [s for s in plan if s.origin == "burst"]
            base = [s for s in plan if s.origin == "base"]
            assert [(s.arrival_s, s.n_turns, s.tool_times_s) for s in base] == \
                   [(s.arrival_s, s.n_turns, s.tool_times_s) for s in base0], "CRN: base sessions identical to NOBURST"
            fast = burst_cohort(sd, b, T_B, WIDTH)
            assert [(s.arrival_s, s.n_turns, tuple(s.tool_times_s)) for s in burst] == [(a, t, tuple(z)) for a, t, z in fast]
            pk = _cohort_peaks(c, lam, burst, S1)
            pk25 = _cohort_peaks(c, lam, burst, 2.5)
            Vb = _paths(c, burst, S1)
            j = int(np.argmax(Vb))
            bg_dev = (float(Vbg[j]) - D1) / cpk
            kc, kl = cal["coh"][b], cal["lock"][b]
            vals = dict(primary=pk["b_eff"] / kc, band_lockstep=pk["b_eff_lockstep"] / kl, band_service_2p5s=pk25["b_eff"] / kc,
                        band_realized_background_at_peak=float(Vb[j]) / cpk / kc + bg_dev,
                        band_raw_time_maximum=pk["b_eff"], band_raw_lockstep=pk["b_eff_lockstep"],
                        band_raw_service_2p5s=pk25["b_eff"], band_raw_realized_background_at_peak=float(Vb[j]) / cpk + bg_dev)
            rws = _rows(c, lam, list(vals.values()), stuck_by, good_from)["rows"]
            post = _rows(c, lam_post, [vals["primary"]], stuck_by, good_from)["rows"][0]
            rec = dict(cohort=pk, b_eff_S2p5=pk25["b_eff"], b_eff_used=vals, calibration_factor=dict(time_resolved=kc, lockstep=kl),
                       realized_background_at_peak=dict(t_peak_s=float(j), background=float(Vbg[j]), cohort=float(Vb[j]),
                                                        b_eff=vals["band_realized_background_at_peak"],
                                                        b_eff_raw=vals["band_raw_realized_background_at_peak"]))
            for k, row in zip(vals, rws):
                rec[k] = row
            rec["band_realized_post_burst_rate"] = dict(lam=lam_post, p_stuck=post["p_stuck"], p_good=post["p_good"])
            rec["level_crossing"] = _level_crossing(Vbg + Vb, V2, stuck_by, good_from)
            recs[str(b)] = rec
        per_seed[str(sd)] = recs
    out["per_seed"] = per_seed
    # ---- the registered bracketing rule (b40 GOOD >= 2/3 and b60 STUCK >= 2/3)
    out["bracketing_rule"] = bracket_probability(per_seed, ex)
    return out


def _rule_prob(pg40: List[float], ps60: List[float], coupling: str) -> float:
    """P(#GOOD(40) >= 2 and #STUCK(60) >= 2) over three independent seeds; within a seed the two runs are independent or
    comonotone (one 'susceptibility' uniform per seed: STUCK(60) at the low end, GOOD(40) at the high end, so
    P(both) = max(0, pG40 + pS60 - 1))."""
    joint = []
    for g, s in zip(pg40, ps60):
        both = g * s if coupling == "independent" else max(0.0, g + s - 1.0)
        joint.append({(1, 1): both, (1, 0): g - both, (0, 1): s - both, (0, 0): 1.0 - g - s + both})
    tot = 0.0
    for a in joint[0]:
        for b in joint[1]:
            for cc in joint[2]:
                if a[0] + b[0] + cc[0] >= 2 and a[1] + b[1] + cc[1] >= 2:
                    tot += joint[0][a] * joint[1][b] * joint[2][cc]
    return tot


def bracket_probability(per_seed: Dict[str, Dict], ex: Dict[str, object]) -> Dict[str, object]:
    out = {}
    for key in BRACKET_TAGS:
        tag = key
        pg40 = [per_seed[str(s)]["40"][key]["p_good"] for s in SEEDS]
        ps60 = [per_seed[str(s)]["60"][key]["p_stuck"] for s in SEEDS]
        out[tag] = dict(p_good_40_per_seed=pg40, p_stuck_60_per_seed=ps60, p_40_good_ge2of3=at_least(pg40, 2),
                        p_60_stuck_ge2of3=at_least(ps60, 2), p_rule_independent=_rule_prob(pg40, ps60, "independent"),
                        p_rule_comonotone=_rule_prob(pg40, ps60, "comonotone"))
    lab40 = [per_seed[str(s)]["40"]["level_crossing"]["label"] for s in SEEDS]
    lab60 = [per_seed[str(s)]["60"]["level_crossing"]["label"] for s in SEEDS]
    out["secondary_level_crossing_deterministic"] = dict(
        labels_40=lab40, labels_60=lab60,
        rule_holds=bool(sum(x == "GOOD" for x in lab40) >= 2 and sum(x == "STUCK" for x in lab60) >= 2))
    exr = {r["burst"]: r for r in ex["rows"]}
    pg, ps = exr[40.0]["p_good"], exr[60.0]["p_stuck"]
    out["exchangeable_frozen_layer"] = dict(p_good_40=pg, p_stuck_60=ps, p_40_good_ge2of3=at_least([pg] * 3, 2),
                                            p_60_stuck_ge2of3=at_least([ps] * 3, 2),
                                            p_rule_independent=_rule_prob([pg] * 3, [ps] * 3, "independent"),
                                            note="the remedy plan's 0.947 counted every non-trapped run as GOOD")
    pt = exr[40.0]["p_stuck"]
    out["exchangeable_not_trapped_as_good"] = dict(p_not_stuck_40=1 - pt, p_rule=at_least([1 - pt] * 3, 2) * at_least([ps] * 3, 2))
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args(argv)
    res = run(1.65, quick=a.quick)
    res135 = run(1.35, synth=100, plans=False)
    res["row_1p35x"] = {k: res135[k] for k in ("mult", "lam", "stuck_by_s", "good_from_s", "exchangeable", "noburst_protocol",
                                                "critical", "composition_averaged", "calibration")}
    p = write_json("b2_basin", res, REG_FILES)
    print("wrote", p)


if __name__ == "__main__":
    main()
