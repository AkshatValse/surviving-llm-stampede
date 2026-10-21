"""Evaluate pre-registered predictions (a)-(d) + GO rule for a delay_eos result directory.

Usage: /opt/anaconda3/bin/python experiments/delay_eos_analyze.py results/delay_eos/<timestamp>
Writes <dir>/analysis/{predictions.json, predictions.md, table_main.csv, table_main.md} (refuses to overwrite).
"""
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from delayeos.analysis import eval_a, eval_b, eval_c, eval_d, go_decision, main_table  # noqa: E402


def fmt_pct(x: float) -> str:
    return f"{100 * x:+.1f}%"


def render_md(a: dict, b: dict, c: dict, d: dict, go: dict) -> str:
    L: list[str] = ["# Pre-registered predictions: evaluation", ""]
    L += ["## (a) full batch, Adam", f"verdict: **{a['verdict']}**  (all three bands pass: {a['all_three_bands_pass']})", ""]
    s = a["sync_beta0.9"]
    L += [f"- sync beta1=0.9: max eta*S_P over all runs/times = {s['max_over_all_runs_and_times']:.2f} "
          f"(gate > {s['gate']}: {s['reached_gate']}); median last-1000 by eta: {s['median_last1000_by_eta']}"]
    for key in ("delay_beta0.9", "ef_beta0.9", "delay_beta0.99"):
        r = a[key]
        L.append(f"- {key}: band {r['band']}, etas ok {r['n_eta_ok']}/{len(r['per_eta'])} -> passed={r['passed']}")
        for eta, v in r["per_eta"].items():
            L.append(f"    - eta={eta:g}: per-seed median eta*S_P {v['per_seed']}, in band {v['n_in_band']}/{v['n_seeds']}")
    L += ["", "## (b) minibatch B=64"]
    for key, t in b.items():
        L += [f"- Adam {key}: sync best eta={t['best_eta_sync']:g}; sync eta*S_P there={t['etaSP_sync_at_best_eta']:.3f}; "
              f"delay eta*S_P there={t['etaSP_delay_at_sync_best_eta']:.3f}; loss sync={t['loss_sync'][f'{t['best_eta_sync']:g}']:.4g}, "
              f"delay={t['loss_delay'][f'{t['best_eta_sync']:g}']:.4g}; penalty at sync-best eta={fmt_pct(t['penalty_at_sync_best_eta'])}; "
              f"tuned penalty={fmt_pct(t['penalty_tuned'])} (best delay eta={t['best_eta_delay']:g}); "
              f"downgrade(matched)={t['downgrade_not_stability_effect']}, downgrade(tuned)={t['downgrade_using_tuned_penalty']}, "
              f"GO-clause={t['go_clause']}",
              f"    - matched-eta penalties: { {k: fmt_pct(v) for k, v in t['penalty_matched'].items()} }"]
    L += ["", "## (c) beta1=0.99 vs 0.9 under delay"]
    for key, t in c.items():
        L += [f"- {key}: matched penalties 0.9={ {k: fmt_pct(v) for k, v in t['penalty_matched_beta0.9'].items()} }, "
              f"0.99={ {k: fmt_pct(v) for k, v in t['penalty_matched_beta0.99'].items()} }; tuned 0.9={fmt_pct(t['penalty_tuned_beta0.9'])}, "
              f"0.99={fmt_pct(t['penalty_tuned_beta0.99'])}; smaller at 0.99 for {t['n_eta_with_smaller_penalty_at_0.99']}/{t['n_eta']} etas; "
              f"supported(tuned)={t['supported_tuned']}, supported(matched majority)={t['supported_matched_majority']}"]
    L += ["", "## (d) Muon-like vs Adam delay penalty (tuned eta per mode)"]
    for key, t in d.items():
        L += [f"- {key}: Adam0.9 {fmt_pct(t['adam0.9_penalty_tuned'])}, Adam0.99 {fmt_pct(t['adam0.99_penalty_tuned'])}, "
              f"Muon {fmt_pct(t['muon_penalty_tuned'])} (best eta sync {t['muon_best_eta_sync']:g}, delay {t['muon_best_eta_delay']:g}); "
              f"negative(Muon>=Adam0.9)={t['negative_muon_ge_adam0.9']}, negative(Muon>=Adam0.99)={t['negative_muon_ge_adam0.99']}"]
    L += ["", "## GO rule", json.dumps(go)]
    return "\n".join(L) + "\n"


def main() -> None:
    res = Path(sys.argv[1])
    cfg = yaml.safe_load(open(res / "config.yaml"))
    df = pd.read_csv(res / "runs_summary.csv")
    p = cfg["predictions"]
    a, b, c, d = eval_a(df, p), eval_b(df, p), eval_c(df, p), eval_d(df, p)
    go = go_decision(a, b)
    tab = main_table(df)
    out = res / "analysis"
    out.mkdir(exist_ok=False)
    json.dump({"a": a, "b": b, "c": c, "d": d, "go": go}, open(out / "predictions.json", "w"), indent=2)
    (out / "predictions.md").write_text(render_md(a, b, c, d, go))
    tab.to_csv(out / "table_main.csv", index=False)
    try:
        md = tab.to_markdown(index=False)
    except ImportError:  # tabulate not installed
        md = tab.to_string(index=False)
    (out / "table_main.md").write_text(md)
    print((out / "predictions.md").read_text())


if __name__ == "__main__":
    main()
