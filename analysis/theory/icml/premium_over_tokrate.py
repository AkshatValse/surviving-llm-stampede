"""Youth premium net of a faster congested engine (referee finding R6 on the reframed draft).

Reads the committed retrospective check results/theory/icml/trap_check.json (from run_check.py) and writes
results/theory/icml/premium_over_tokrate.json. For each E2-protocol stuck run it divides the measured completion rate over the
window, in units of the cell's lambda_ref, by the run's measured token-rate ratio: its uncached prompt tokens per second over its
cell's E0a all-miss token rate (`tokens_ref`). A ratio above 1 means the congested engine computed prompt tokens faster than the
all-miss reference; dividing it out removes that speed-up from the completion rate. Nothing is fitted; no run data is read beyond
the JSON.

    python analysis/theory/icml/premium_over_tokrate.py
"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SRC = os.path.join(ROOT, "results", "theory", "icml", "trap_check.json")
OUT = os.path.join(ROOT, "results", "theory", "icml", "premium_over_tokrate.json")


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    rows = []
    for g in data["groups"]:
        if g["kind"] != "e2":
            continue
        m = g["measured"]
        tref = m["tokens_ref"]
        assert isinstance(tref, (int, float)) and tref > 0, (g["label"], g["rate_mult"], tref)
        for i in range(g["n_runs"]):
            comp = m["completion_rate"][i] / g["lam_ref"]
            tok = m["uncached_tok_per_s"][i] / tref
            rows.append({"label": g["label"], "cell": g["cell"], "rate_mult": g["rate_mult"], "seed": g["seeds"][i],
                         "completions_over_lref": comp, "token_rate_ratio": tok, "completions_over_lref_per_token_ratio":
                         comp / tok, "D_over_lref": g["asym"]["D"] / g["lam_ref"]})
    lo = min(rows, key=lambda r: r["completions_over_lref_per_token_ratio"])
    hi = max(rows, key=lambda r: r["completions_over_lref_per_token_ratio"])
    summary = {"n_runs": len(rows),
               "adjusted_min": lo["completions_over_lref_per_token_ratio"], "adjusted_min_run": {k: lo[k] for k in
               ("label", "rate_mult", "seed", "completions_over_lref", "token_rate_ratio")},
               "adjusted_max": hi["completions_over_lref_per_token_ratio"], "adjusted_max_run": {k: hi[k] for k in
               ("label", "rate_mult", "seed", "completions_over_lref", "token_rate_ratio")},
               "token_rate_ratio_min": min(r["token_rate_ratio"] for r in rows),
               "token_rate_ratio_max": max(r["token_rate_ratio"] for r in rows),
               "completions_over_lref_min": min(r["completions_over_lref"] for r in rows),
               "all_adjusted_above_1": all(r["completions_over_lref_per_token_ratio"] > 1 for r in rows)}
    out = {"source": "results/theory/icml/trap_check.json", "definition": "(completion_rate / lam_ref) / (uncached_tok_per_s / "
           "tokens_ref) per E2-protocol stuck run; tokens_ref is the cell's E0a all-miss token rate", "summary": summary,
           "runs": rows}
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
        fh.write("\n")
    print(json.dumps(summary, indent=1))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
