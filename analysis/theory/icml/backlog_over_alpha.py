"""Backlog slope over model F's asymptotic alpha, per stuck run (referee finding R12 on the reframed draft).

Reads the committed retrospective check results/theory/icml/trap_check.json (from run_check.py) and writes
results/theory/icml/backlog_over_alpha.json. For each run group it gives the measured backlog slope over the window divided by
the group's asymptotic alpha (Theorem 1(c)) per seed, and the quasi-static reading's ratio (lambda - lambda_miss) / alpha, the
slope the quasi-static equation gives with completions at lambda_miss. Nothing is fitted; no run data is read beyond the JSON.

    python analysis/theory/icml/backlog_over_alpha.py
"""
import json
import os
import statistics

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SRC = os.path.join(ROOT, "results", "theory", "icml", "trap_check.json")
OUT = os.path.join(ROOT, "results", "theory", "icml", "backlog_over_alpha.json")


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    groups = []
    per_kind = {}
    for g in data["groups"]:
        a = g["asym"]
        alpha = a["alpha"]
        slopes = g["measured"]["backlog_slope"]
        ratios = [s / alpha for s in slopes]
        qs = (a["lam"] - a["lam_miss"]) / alpha
        # the same slopes over the excess load lam - lam_miss (the quasi-static rate), and the plans' window arrivals
        # over the nominal rate (the R16 check of the from-empty excess)
        over_excess = [s / (a["lam"] - a["lam_miss"]) for s in slopes]
        arr = [x / a["lam"] for x in g["measured"]["arrival_rate_window"]]
        groups.append({"kind": g["kind"], "label": g["label"], "cell": g["cell"], "rate_mult": g["rate_mult"],
                       "n_runs": g["n_runs"], "seeds": g.get("seeds"), "alpha": alpha, "slopes": slopes,
                       "slope_over_alpha": ratios, "quasi_static_over_alpha": qs,
                       "alpha_over_excess": a["alpha_over_excess"], "slope_over_excess": over_excess,
                       "window_arrivals_over_nominal": arr})
        per_kind.setdefault(g["kind"], {"ratios": [], "qs": [], "excess": [], "arr": []})
        per_kind[g["kind"]]["ratios"] += ratios
        per_kind[g["kind"]]["qs"].append(qs)
        per_kind[g["kind"]]["excess"] += over_excess
        per_kind[g["kind"]]["arr"] += arr
    summary = {}
    for kind, v in per_kind.items():
        r = v["ratios"]
        summary[kind] = {"n_runs": len(r), "mean": statistics.fmean(r), "median": statistics.median(r), "min": min(r),
                         "max": max(r), "quasi_static_min": min(v["qs"]), "quasi_static_max": max(v["qs"]),
                         "slope_over_excess_mean": statistics.fmean(v["excess"]),
                         "slope_over_excess_median": statistics.median(v["excess"]),
                         "slope_over_excess_min": min(v["excess"]), "slope_over_excess_max": max(v["excess"]),
                         "window_arrivals_over_nominal_min": min(v["arr"]),
                         "window_arrivals_over_nominal_max": max(v["arr"])}
    out = {"source": "results/theory/icml/trap_check.json", "definition": "measured backlog slope over the window / asymptotic "
           "alpha of Theorem 1(c) at the group's nominal rate; quasi_static = (lam - lam_miss) / alpha",
           "summary": summary, "groups": groups}
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")
    for g in groups:
        r = g["slope_over_alpha"]
        print(f"{g['kind']:4s} {g['label']:34s} {g['rate_mult']:5.2f}x n={g['n_runs']}  slope/alpha {min(r):6.2f}..{max(r):5.2f}"
              f"  quasi-static {g['quasi_static_over_alpha']:.2f}")
    for kind, v in summary.items():
        print(kind, {k: round(x, 3) if isinstance(x, float) else x for k, x in v.items()})
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
