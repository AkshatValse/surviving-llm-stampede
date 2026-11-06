"""Every number used in the MIRROR fill-ins, computed only from the registered outputs, the E0a calibration and the tagged
frozen predictions.  Read-only; imports nothing from the repository.

usage: python -I -B claims_numbers.py <worktree> <tagged mirror_predictions.json>
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

wt = Path(sys.argv[1])
pred = json.loads(Path(sys.argv[2]).read_text())
reg = wt / "results/agentload_analysis_r16_mirror/20261105-173136"
runs = pd.read_csv(reg / "mirror_runs.csv")
bins = json.loads((reg / "mirror_bins.json").read_text())
verdict = json.loads((reg / "mirror_verdict.json").read_text())
cal = json.loads((wt / "results/nova/r16_mirror_e0a_1726409x_pulled_20261105-1659/results/agentload_analysis_miss/"
                       "20261105-162735/calibration.json").read_text())
pop = json.loads((wt / "results/nova/r16_mirror_e0a_1726409x_pulled_20261105-1659/results/agentload_analysis_miss_popcheck/"
                       "20261105-162736/calibration.json").read_text())

runs["run"] = runs["run_dir"].str.replace("\\", "/", regex=False).str.split("/").str[-1]
JOB = {"20261105-145227": 17264055, "20261105-145244-2": 17264056, "20261105-145240": 17264057,
       "20261105-145242": 17264058, "20261105-145247": 17264059, "20261105-145248": 17264060,
       "20261105-145244-1": 17264062, "20261105-145246": 17264063, "20261105-145244": 17264064}
lr = float(pred["lambda_ref"])
assert all(abs(runs["lambda_ref"] - lr) < 1e-15)
print(f"lambda_ref {lr}  (pred JSON lambda_ref; mirror_runs.csv lambda_ref identical)")
print(f"lambda_miss_model {pred['lambda_miss_model']} = {pred['lambda_miss_model_over_ref']:.4f} lref")

out = []
for mult in ("1.65", "1.35"):
    cell = pred["cells"][mult]
    print(f"\n=== BURST {mult} x  (rho {cell['rho']:.3f}; asymptotic D/lmiss {cell['asymptotics']['D_over_lam_miss']:.3f}, "
          f"D/lref {cell['asymptotics']['D_over_lam_ref']:.3f}, H {cell['asymptotics']['H_T']:.3f}, "
          f"Gamma {cell['asymptotics']['Gamma_c']:.3f})")
    for seed in (0, 1, 2):
        r = runs[(runs.arm == "burst") & (np.isclose(runs.rate_mult, float(mult))) & (runs.seed == seed)].iloc[0]
        sd = cell["seeds"][str(seed)]
        F_bl = sd["windows"]["blackout"]["completion_over_lam_ref"]
        F_late = sd["windows"]["late"]["completion_over_lam_ref"]
        F_wave = sd["burst_timing"]["median"]
        F_cal = sd["burst_timing"]["median_calibrated"]
        F_S = sd["windows"]["slope"]["slope"]
        F_P = sd["windows"]["w5700"]["P_served_mean"]
        assert abs(F_wave - r.F_wave) < 1e-9 and abs(F_S - r.S_F) < 1e-12 and abs(F_cal - r.F_wave_cal) < 1e-9
        err = r.wave_time - F_wave
        tol = 0.15 * (F_wave - 1200)
        tol5 = 0.05 * (F_cal - 1200)
        late_ceiling_n = 0.85 * lr * 2100.0
        bl_ceiling_n = 0.30 * lr * 1200.0
        d = dict(cell=mult, seed=seed, job=JOB[r.run], run=r.run,
                 blackout=r.blackout_rate, blackout_n=int(r.blackout_n), F_blackout=F_bl,
                 late=r.late_rate, late_n=int(r.late_n), F_late=F_late, late_minus_F=r.late_rate - F_late,
                 wave=r.wave_time, F_wave=F_wave, wave_err=err, M2_tol=tol, err_over_elapsed=err / (F_wave - 1200),
                 ratio_elapsed=(r.wave_time - 1200) / (F_wave - 1200),
                 F_cal=F_cal, W5_err=r.wave_time - F_cal, W5_tol=tol5,
                 S=r.slope, S_F=r.S_F, S_QS=r.S_QS, dF=abs(r.slope - r.S_F), dQS=abs(r.slope - r.S_QS),
                 S_rel_F=(r.slope - r.S_F) / r.S_F, lam_plan=r.lambda_plan_slope_window,
                 P=r.P_served_5700_8700, F_P=F_P, P_rel=(r.P_served_5700_8700 - F_P) / F_P,
                 hit=r.hit_eval, fu_hit=r.fu_hit_5700_8700, stuck=bool(r.stuck), call=r.call,
                 M1=bool(r.M1), M2=bool(r.M2), M3=bool(r.M3), M4=bool(r.M4),
                 W5=bool(r.W5_calibrated_wave), W7=bool(r.W7_composition), W8=bool(r.W8_late_level),
                 burst_completed=int(r.burst_completed), late_ceiling_n=late_ceiling_n, bl_ceiling_n=bl_ceiling_n,
                 late_over_e0a=r.late_rate / (cal["lambda_miss_turns_based"] / lr),
                 late_over_e0a_sess=r.late_rate / (cal["lambda_miss"] / lr),
                 counted=bool(r.counted), plan_ok=bool(r.plan_matches_frozen), bound=bool(r.prereg_bound),
                 run_end=r.run_end_s, slope_bins=int(r.slope_bins))
        out.append(d)
        print(f"seed {seed} job {d['job']} ({r.run}): call {d['call']}  M1-4 {d['M1']}{d['M2']}{d['M3']}{d['M4']}  stuck {d['stuck']} "
              f"hit {d['hit']:.4f} fu_hit {d['fu_hit']:.4f}")
        print(f"   blackout {d['blackout']:.4f} [{d['blackout_n']} of <= {bl_ceiling_n:.2f}] (F {F_bl:.4f})   "
              f"late {d['late']:.4f} [{d['late_n']} of <= {late_ceiling_n:.2f}] (F {F_late:.4f}; late-F {d['late_minus_F']:+.4f})")
        print(f"   wave {d['wave']:.1f} (F {F_wave:.1f}; err {err:+.1f} s = {100*d['err_over_elapsed']:+.2f}% of F-1200; M2 tol {tol:.1f}; "
              f"ratio {d['ratio_elapsed']:.4f})  W5: |wave-Fcal| {abs(d['W5_err']):.1f} vs {tol5:.1f} -> {d['W5']}")
        print(f"   slope {d['S']:.5f} (F {d['S_F']:.5f}, QS {d['S_QS']:.5f}); |S-SF| {d['dF']:.5f} |S-SQS| {d['dQS']:.5f}; "
              f"(S-SF)/SF {100*d['S_rel_F']:+.1f}%; lam_plan {d['lam_plan']:.5f}")
        print(f"   P_served {d['P']:.1f} (F {F_P:.1f}; {100*d['P_rel']:+.2f}%) W7 {d['W7']}  W8 {d['W8']}  "
              f"late/E0a(turns) {d['late_over_e0a']:.3f} late/E0a(sess) {d['late_over_e0a_sess']:.3f}  "
              f"burst done {d['burst_completed']}  counted {d['counted']} plan {d['plan_ok']} bound {d['bound']} "
              f"end {d['run_end']:.3f} bins {d['slope_bins']}")
df = pd.DataFrame(out)
df.to_csv(Path(sys.argv[0]).with_name("claims_numbers_burst.csv"), index=False)

print("\n=== ranges")
for mult in ("1.65", "1.35"):
    c = df[df.cell == mult]
    print(f"{mult}: blackout {c.blackout.min():.3f}-{c.blackout.max():.3f}; late {c.late.min():.3f}-{c.late.max():.3f}; "
          f"wave {c.wave.min():.0f}-{c.wave.max():.0f}; err {c.wave_err.min():+.0f} to {c.wave_err.max():+.0f}; "
          f"|err|/elapsed {100*c.err_over_elapsed.abs().min():.1f}-{100*c.err_over_elapsed.abs().max():.1f}%; "
          f"ratio {c.ratio_elapsed.min():.3f}-{c.ratio_elapsed.max():.3f}; "
          f"S {c.S.min():.4f}-{c.S.max():.4f}; S/S_F-1 {100*c.S_rel_F.min():+.1f} to {100*c.S_rel_F.max():+.1f}%; "
          f"late/E0a {c.late_over_e0a.min():.3f}-{c.late_over_e0a.max():.3f}; hit max {c.hit.max():.4f}")
print(f"all: blackout {df.blackout.min():.3f}-{df.blackout.max():.3f} late {df.late.min():.3f}-{df.late.max():.3f}")
print(f"S_QS range {df.S_QS.min():.4f}-{df.S_QS.max():.4f}; S_F range {df.S_F.min():.4f}-{df.S_F.max():.4f}")
print(f"(S-S_QS)/S_QS: " + ", ".join(f"{(a-b)/b*100:+.0f}%" for a, b in zip(df.S, df.S_QS)))
print(f"S/(lam_plan - lmiss_model): " + ", ".join(f"{a/b:.2f}" for a, b in zip(df.S, df.S_QS)))
print(f"S_F/(S_QS): " + ", ".join(f"{a/b:.2f}" for a, b in zip(df.S_F, df.S_QS)))
print("W6 shifts (wave 1.65 - wave 1.35), measured / model F:")
for seed in (0, 1, 2):
    a = df[(df.cell == "1.65") & (df.seed == seed)].iloc[0]
    b = df[(df.cell == "1.35") & (df.seed == seed)].iloc[0]
    print(f"   seed {seed}: {a.wave - b.wave:.1f} / {a.F_wave - b.F_wave:.1f}")

print("\n=== NOBURST 1.65 x")
for seed in (0, 1, 2):
    r = runs[(runs.arm == "noburst") & (runs.seed == seed)].iloc[0]
    print(f"seed {seed} job {JOB[r.run]} ({r.run}): good {r.good} state {r.state} hit {r.hit_eval:.4f} fu_hit {r.fu_hit_5700_8700:.4f} "
          f"blackout {r.blackout_rate:.4f} [{r.blackout_n}] late {r.late_rate:.4f} [{r.late_n}] slope {r.slope:+.5f} "
          f"counted {r.counted} end {r.run_end_s:.3f}")
nb = runs[runs.arm == "noburst"]
print(f"NOBURST completions, both windows: {min(nb.blackout_rate.min(), nb.late_rate.min()):.3f}-"
      f"{max(nb.blackout_rate.max(), nb.late_rate.max()):.3f}; hit {nb.hit_eval.min():.4f}-{nb.hit_eval.max():.4f}; "
      f"slope {nb.slope.min():+.5f} to {nb.slope.max():+.5f}")

print("\n=== E0a (W10)")
print(f"lambda_miss_turns_based {cal['lambda_miss_turns_based']:.6f} /s = {cal['lambda_miss_turns_based']/lr:.4f} lref; "
      f"sessions-based {cal['lambda_miss']:.6f} = {cal['lambda_miss']/lr:.4f} lref; uncached tok/s {cal['all_miss_uncached_tokens_per_s']:.0f}; "
      f"n_runs {cal['n_runs']}; host {cal['hostnames']}")
print(f"POP-64 check: turns-based {pop['lambda_miss_turns_based']/lr:.4f} lref, sessions {pop['lambda_miss']/lr:.4f}, "
      f"tok/s {pop['all_miss_uncached_tokens_per_s']:.0f} ({100*(pop['all_miss_uncached_tokens_per_s']/cal['all_miss_uncached_tokens_per_s']-1):+.1f}%)")
w10 = verdict["W10_capacity"]
print(f"verdict W10: {w10['over_lambda_ref']:.4f} (model {w10['model_over_lambda_ref']:.4f}); late below: {w10['late_below_measured_capacity']}")
print(f"(E0a - model)/model = {100*(w10['over_lambda_ref']/w10['model_over_lambda_ref']-1):+.2f}%")

print("\n=== verdict")
for k, v in verdict["cells"].items():
    print(k, v["role"], v["verdict"], {s: c for s, c in v["calls"].items()})
print("W6", verdict["W6_order"], "W9", verdict["W9_controls_good"], "predates", verdict["predictions"])

print("\n=== 300-s completion bins (lref), last 1200 s [7500, 8700) and late window, BURST runs")
edges = np.arange(1200.0, 8700.0 + 1e-9, 300.0)
for d in out:
    key = [k for k in bins if k.replace("\\", "/").endswith("/" + d["run"])][0]
    v = np.array(bins[key])
    i0 = int((7500 - 1200) / 300)
    il = int((6600 - 1200) / 300)
    print(f"{d['cell']} s{d['seed']}: late-window bins {np.round(v[il:], 2).tolist()}; mean [7500,8700) {v[i0:].mean():.3f}; "
          f"peak {v.max():.2f} at bin start {edges[int(np.argmax(v))]:.0f}")
    sd = pred["cells"][d["cell"]]["seeds"][str(d["seed"])]["completion_bins"]
    fv = np.array(sd["rate_over_lam_ref"])
    print(f"        model F late bins {np.round(fv[il:], 2).tolist()}; mean [7500,8700) {fv[i0:].mean():.3f}; "
          f"peak {fv.max():.2f} at {sd['bin_start'][int(np.argmax(fv))]:.0f}")

print("\n=== standard-workload comparison numbers quoted by the tagged note: 1.05-1.48 (blackout window), 1.01-1.35 (late)")
print("model F frozen ranges at 1.65: blackout", [round(pred['cells']['1.65']['seeds'][s]['windows']['blackout']['completion_over_lam_ref'], 3) for s in '012'],
      "late", [round(pred['cells']['1.65']['seeds'][s]['windows']['late']['completion_over_lam_ref'], 3) for s in '012'],
      "wave", [round(pred['cells']['1.65']['seeds'][s]['burst_timing']['median'], 1) for s in '012'])
print("model F frozen ranges at 1.35: blackout", [round(pred['cells']['1.35']['seeds'][s]['windows']['blackout']['completion_over_lam_ref'], 3) for s in '012'],
      "late", [round(pred['cells']['1.35']['seeds'][s]['windows']['late']['completion_over_lam_ref'], 3) for s in '012'],
      "wave", [round(pred['cells']['1.35']['seeds'][s]['burst_timing']['median'], 1) for s in '012'])
