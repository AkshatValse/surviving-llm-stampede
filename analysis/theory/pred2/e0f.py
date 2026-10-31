"""E0F: fresh-seed E0b replication on the A100 300k cell (label sglang-fcfs-r1-e0bfresh): from empty, 3000 s, seeds 3-5 at
2.0 x and 2.5 x lambda_ref; registered rule (configs/r11_basin_predict.yaml, commit c600fd7): stable := not aborted AND final
queue < 50 AND OLS rise of the 100 s queue means over the last 1500 s <= 10; REPLICATED iff 2.0 x stable 3/3 AND 2.5 x
unstable in >= 2/3.

    PYTHONPATH="src;." python -m analysis.theory.pred2.e0f           # -> results/theory/pred2/e0f.json

* PRIMARY (frozen F2, exchangeable): per-seed P(unstable) = the frozen F2 escape probability at the nominal rate (it is the
  frozen a100_300k.json p_escape_registered; checked), with the binomial table and P(replicated).
* plan-conditional band (NEW): the frozen F2 escape at each seed's REALIZED mean arrival rate over the 3000 s (the exact
  client plan of configs/agentload_e0_cap.yaml, seed, rate, 3000 s); the arrival noise of F2 is not removed (conservative).
* secondary (A's level crossing on the exact plan, deterministic): the plan's live KV (frozen extras._live_paths fed with
  the plan; good-state service at n1) first reaches D_live(n_u) before 3000 - 50 / (lambda - mu_b) s.
* reference seed 0 (outcome known and read before the freeze: 2.0 x stable, 2.5 x unstable): the same three numbers,
  labelled retrodiction.
"""
from __future__ import annotations

import math
from typing import Dict, List

import numpy as np

from ..fluid_rigorous.edge import escape_probability
from ..fluid_rigorous.model import live_demand, mu_good_of_n, open_equilibria
from .common import E0_CONFIG, LREF_300K_REG, at_least, cell, client_plan, frozen_json, live_path, plan_arrays, poisson_binomial, write_json

CELL = "a100_300k"
MULTS = [2.0, 2.5]
SEEDS = [3, 4, 5]
REF_SEEDS = [0]
H = 3000.0
Q_FINAL = 50.0


def level_crossing(c, lam: float, plan) -> Dict[str, object]:
    ng, _ = mu_good_of_n(c.cs)
    pts = c.cs.pts[: len(ng)]
    n_arr = np.array([p["n"] for p in pts])
    D_arr = np.array([live_demand(c.m, p) for p in pts])
    S_arr = np.array([p["S_bar"] for p in pts])
    o = np.argsort(n_arr)
    eq = open_equilibria(c.cs, lam)
    V2 = float(np.interp(eq.n_u, n_arr[o], D_arr[o]))
    S_good = float(np.interp(eq.n1, n_arr[o], S_arr[o]))
    t_lim = H - Q_FINAL / (lam - c.cs.mu_b)
    arr, T, Z = plan_arrays(plan)
    V = live_path(c.m, arr, T, Z, S_good, H)
    idx = np.nonzero(V >= V2)[0]
    t_x = float(idx[0]) if len(idx) else math.nan
    return dict(V2=V2, S_good=S_good, t_lim=t_lim, first_crossing_s=t_x, peak_live_kv=float(V.max()),
                unstable=bool(len(idx) and idx[0] < t_lim))


def run() -> Dict[str, object]:
    c = cell(CELL)
    fz = frozen_json(CELL)["from_empty_edge"]["p_escape_registered"]
    out: Dict[str, object] = dict(cell=CELL, horizon_s=H, mults=MULTS, seeds=SEEDS, rows={})
    for mult in MULTS:
        lam = mult * c.lam_ref
        p_ex = escape_probability(c.mu_f, lam, c.I_D, c.cs.n_b, H)["p_escape"]
        assert abs(p_ex - fz[f"{mult}"]) < 1e-12, (p_ex, fz[f"{mult}"])
        per = {}
        for sd in SEEDS + REF_SEEDS:
            plan, rate = client_plan(E0_CONFIG, sd, mult, H, 0)
            n_arr = sum(1 for s in plan if s.arrival_s < H)
            real = n_arr / (H * LREF_300K_REG)
            p_real = escape_probability(c.mu_f, real * c.lam_ref, c.I_D, c.cs.n_b, H)["p_escape"]
            per[str(sd)] = dict(role="retrodiction (outcome known)" if sd in REF_SEEDS else "prediction", n_sessions=n_arr,
                                realized_mult=real, p_unstable_exchangeable=p_ex, p_unstable_realized_rate=p_real,
                                level_crossing=level_crossing(c, lam, plan))
        pr = [per[str(s)]["p_unstable_realized_rate"] for s in SEEDS]
        out["rows"][f"{mult}"] = dict(lam=lam, p_unstable_exchangeable=p_ex, per_seed=per,
                                      binomial_exchangeable=poisson_binomial([p_ex] * 3), poisson_binomial_realized=poisson_binomial(pr),
                                      level_crossing_unstable_count=sum(per[str(s)]["level_crossing"]["unstable"] for s in SEEDS))
    r2, r25 = out["rows"]["2.0"], out["rows"]["2.5"]
    def rep(pmf2, pmf25):
        return dict(p_2x_stable_3of3=pmf2[0], p_2p5x_unstable_ge2of3=pmf25[2] + pmf25[3], p_replicated=pmf2[0] * (pmf25[2] + pmf25[3]))
    out["replication_rule"] = dict(
        statement="replicated iff 2.0 x stable 3/3 AND 2.5 x unstable >= 2/3",
        primary_exchangeable=rep(r2["binomial_exchangeable"], r25["binomial_exchangeable"]),
        band_realized_rate=rep(r2["poisson_binomial_realized"], r25["poisson_binomial_realized"]),
        secondary_level_crossing=dict(unstable_2x=r2["level_crossing_unstable_count"], unstable_2p5x=r25["level_crossing_unstable_count"],
                                      replicated=bool(r2["level_crossing_unstable_count"] == 0 and r25["level_crossing_unstable_count"] >= 2)))
    return out


def main() -> None:
    p = write_json("e0f", run(), [E0_CONFIG])
    print("wrote", p)


if __name__ == "__main__":
    main()
