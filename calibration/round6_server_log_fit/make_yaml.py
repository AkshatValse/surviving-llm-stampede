"""Write calibration.yaml: the simulator's engine section with fitted cost parameters + a provenance block."""
from __future__ import annotations

import datetime as dt
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import scipy
import yaml

W = Path(__file__).parent
CFG = Path(__file__).resolve().parents[2] / "configs" / "prefix_meta.yaml"
REPO = CFG.parent.parent
LOGS = {
    "17060165": ("results/nova/s0_smoke_17060165_pulled_20261021-152347/nova_job_logs/17060165-20261021-104104/server.log",
                 "nova22-gpu-1", "s0 smoke, fcfs"),
    "17062103": ("results/nova/stageC_1706210x_pulled_20261022-125454/nova_job_logs/17062103-20261021-153631/server.log",
                 "nova22-gpu-1", "stage C closed, fcfs, n in {16,20,24,32}"),
    "17062104": ("results/nova/stageC_1706210x_pulled_20261022-125454/nova_job_logs/17062104-20261021-164755/server.log",
                 "nova22-gpu-3", "stage C closed, fcfs, n in {48,96,300}"),
    "17062105": ("results/nova/stageC_1706210x_pulled_20261022-125454/nova_job_logs/17062105-20261021-165439/server.log",
                 "nova22-gpu-2", "stage C closed, lpm, n in {48,300}"),
}
ROOT = Path(__file__).resolve().parents[2]


def sig(x, n=3):
    return float(f"{x:.{n}g}")


def sha256(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    fr = json.loads((W / "fit_results.json").read_text())
    va = json.loads((W / "validation.json").read_text())
    hi = json.loads((W / "hits.json").read_text())
    eng = yaml.safe_load(CFG.read_text())["engine"]
    J = fr["joint_simform_mid"]
    names = J["names"]
    est = dict(zip(names, J["est"]))
    cis = dict(zip(names, J["ci"]))
    new = dict(eng)
    for k in names:
        new[k] = sig(est[k])
    new["prefill_attn_ctx"] = "mid"
    assert list(new.keys()) == list(eng.keys())
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()

    def m(d):
        return {k: (sig(v, 4) if isinstance(v, float) else v) for k, v in d.items()}

    prov = dict(
        created=dt.datetime.now().isoformat(timespec="seconds"),
        what="Iteration-time cost model fitted to SGLang 0.5.22 server logs (Qwen2.5-7B-Instruct, 1x A100 80GB PCIe).",
        scripts={p: str(W / p) for p in ("parse_logs.py", "build_datasets.py", "fit.py", "validate.py", "hits.py", "make_yaml.py")},
        environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                         interpreter=sys.executable, machine=platform.machine()),
        simulator_repo=dict(path=str(REPO), commit=commit, dirty=bool(dirty), config_read=str(CFG),
                            previous_values={k: eng[k] for k in names + ["prefill_attn_ctx"]}),
        data=dict(
            logs=[dict(job=j, path=str(ROOT / p), node=n, content=c, sha256=sha256(ROOT / p)) for j, (p, n, c) in LOGS.items()],
            engine="sglang 0.5.22, flashinfer 0.7.1, torch 2.14.1; attention/sampling backend flashinfer; CUDA graphs on; "
                   "overlap scheduler on; enable_mixed_chunk False; chunked_prefill_size 8192; max_prefill_tokens 16384; "
                   "max_running_requests 256; max_total_tokens 300000; page_size 1; decode_log_interval 40; "
                   "model Qwen/Qwen2.5-7B-Instruct rev a09a35458c70; workload ignore_eos, 100 output tokens/turn",
            blindness="Only the two allowed pulled dirs (server.log + run metadata) and read-only SGLang source on Nova were used; "
                      "no E0a/E0b/E2 data, no Nova results/ or logs/, no squeue/sacct."),
        definitions=dict(
            input_throughput="(#new-token + replay tokens) / wall time since the previous Prefill line; both logged at result "
                             "processing of every prefill batch (metrics_reporter.py report_prefill_stats). The interval "
                             "includes any decode iterations and idle time since the previous prefill.",
            gen_throughput="sum of decode-batch sizes over the last 40 decode batches / wall time since the previous Decode line "
                           "(logged when forward_ct_decode % 40 == 0; prefill first tokens not counted). The interval includes "
                           "prefill iterations run in between.",
            decode_token="#token = max_total_num_tokens - (available + evictable) = KV tokens pinned by running requests; "
                         "verified: token usage == #token/300000 to rounding on all decode lines, and #token grows by exactly "
                         "40*R in 1144/1183 candidate windows.",
            cached_token="radix prefix of newly admitted requests; continuation chunks report 0 (add_chunked_req passes "
                         "prefix_len=0), so continuation prefixes were reconstructed from chunk chains."),
        selection=dict(
            decode="consecutive Decode lines, no Prefill line between, equal #running-req R>0, #token growth == 40*R "
                   "=> tau = R / gen_throughput (exact).",
            prefill="previous batch line is a Prefill with #new-token == 8192 (budget exhausted => chunked request, whose "
                    "continuation SGLang always schedules next); single-sequence batch with reconstructable prefix "
                    "=> tau = #new-token / input_throughput.",
            n_decode=fr["n_decode"], n_prefill=fr["n_prefill"], decode_blocks=fr["decode_blocks"],
            prefill_blocks=fr["prefill_blocks"],
            decode_R_range=[1, 142], prefill_X_range=[159, 8192], prefill_prefix_range=[8192, 35069]),
        fit=dict(
            method="joint least squares on relative residuals, simulator form applied to SEPARATE P and D iterations "
                   "(mixed chunk off), decode and prefill sets weighted equally; 'mid' causal pair count "
                   "A = X*prefix + X(X+1)/2.",
            bootstrap=dict(kind="cluster (120 s blocks per job/epoch), resampled independently per set",
                           n_boot=fr["n_boot"], seed=fr["seed"], hits_seed=hi["seed"], hits_n_boot=hi["n_boot"]),
            estimates={k: dict(value=sig(est[k], 4), ci95=[sig(cis[k][0], 3), sig(cis[k][1], 3)]) for k in names},
            iter_fixed_plus_floor_ci95=[sig(x, 4) for x in J["ci_fixed_plus_floor"]],
            metrics_decode=m(J["metrics_decode"]), metrics_prefill=m(J["metrics_prefill"]),
            identifiability="Decode data pin only iter_fixed+iter_floor (~10.5 ms); the split is set by the prefill "
                            "intercept (iter_floor CI is wide). per_token_s is identified by prefill X variation and is "
                            "forced to be the decode per-sequence slope above the knee R = floor/per_token ~ 20; the "
                            "decode-only slope is smaller (see alternatives). prefill_attn_s is identified by the prefix "
                            "variation of 8192-token chunks (8k..35k prefix)."),
        assumed_values_on_same_data=dict(metrics_decode=m(fr["sim_assumed"]["metrics_decode"]),
                                         metrics_prefill_end=m(fr["sim_assumed"]["metrics_prefill_end"])),
        alternatives=dict(
            decode_only_linear=dict(form="tau_D = a + b*R + c*sumctx/8192",
                                    est=dict(zip(["a_s", "per_seq_s", "per_ctx8192_s"], [sig(x, 4) for x in fr["decode_linear"]["est"]])),
                                    ci95=[[sig(x, 3) for x in c] for c in fr["decode_linear"]["ci"]],
                                    metrics=m(fr["decode_linear"]["metrics"])),
            prefill_only_linear_mid=dict(est=dict(zip(["a_s", "per_token_s", "prefill_attn_s"], [sig(x, 4) for x in fr["prefill_linear_mid"]["est"]])),
                                         ci95=[[sig(x, 3) for x in c] for c in fr["prefill_linear_mid"]["ci"]],
                                         metrics=m(fr["prefill_linear_mid"]["metrics"])),
            joint_simform_end=dict(prefill_attn_ctx="end",
                                   est=dict(zip(names, [sig(x, 4) for x in fr["joint_simform_end"]["est"]])),
                                   metrics_decode=m(fr["joint_simform_end"]["metrics_decode"]),
                                   metrics_prefill=m(fr["joint_simform_end"]["metrics_prefill"])),
            hit_prefill_551=dict(form="tau_P(551 new, prefix c) = alpha + beta*c (k=0 tooth of the decode-step comb)",
                                 alpha_s=sig(hi["alpha_s"], 4), alpha_ci95=[sig(x, 3) for x in hi["alpha_ci"]],
                                 beta_s_per_token=sig(hi["beta_s_per_cached_token"], 4), beta_ci95=[sig(x, 3) for x in hi["beta_ci"]],
                                 implied_attn_s_per_pair=sig(hi["e_hit_s_per_pair"], 3), n_k0=hi["n_k0"],
                                 calibrated_model_rel_error_by_prefix=hi["calibrated_model_on_k0_by_cached"])),
        validation=dict(
            unknown_prefix_continuation_chunks=va["val_unknown_prefix_chunks"],
            hit_prefill_comb=dict(
                note="gaps of hit prefills after a prefill form a comb; tooth k sits at k_hat ~ k - 0.35 for k >= 1 "
                     "(a prefill that follows decode steps is ~0.35 tau_D ~ 4 ms cheaper than one following a prefill); "
                     "the spacing between teeth k >= 2 measures tau_D out of sample",
                tooth_median_k_hat={k: sig(v, 3) for k, v in hi["tooth_median_k_hat"].items()},
                tooth_counts=hi["tooth_counts"],
                mean_spacing_teeth_2_to_6_over_model_tauD=sig(float(np.mean(np.diff([hi["tooth_median_k_hat"][str(t)] for t in range(2, 7)]))), 3)),
            per_job_linear=va["per_job"]),
        caveats=[
            "SGLang runs prefill and decode as separate iterations and starves decode while any prefill batch can be formed "
            "('Run prefill first if possible'); the simulator mixes them. With these values a simulator iteration with "
            "X prefill tokens and n_D decoders costs ~(iter_fixed+iter_floor - per_token*n_D) less than SGLang's P+D pair.",
            "Decode per-sequence slope in SGLang is ~4.4e-5 s/seq; the shared per_token_s forces 6.3e-5 above R~20: "
            "+5..12% decode error at R>=80, -6% near R~32 (CUDA-graph bucket structure).",
            "Hit prefills (551 new tokens) have a higher per-pair attention cost (~3.8e-9 s) than 8192 chunks; the "
            "calibrated model is +17% (prefix<4k) .. -11% (prefix>16k) on them, ~0 near 10k.",
            "Node-to-node spread (3 A100 nodes): per-job prefill per_token 6.1e-5..6.5e-5 s, decode intercept 9.0..10.5 ms.",
            "iteration times are wall-clock scheduler cycles (GPU forward plus non-overlapped CPU), which is what the "
            "simulator needs, not pure kernel time."])
    doc = dict(engine=new, provenance=prov)
    with open(W / "calibration.yaml", "w") as fh:
        fh.write("# Calibrated iteration-time cost model for the prefix-meta simulator (keys = configs/prefix_meta.yaml 'engine').\n")
        fh.write("# Only the five cost parameters and prefill_attn_ctx differ from the config; all other engine keys are copied unchanged.\n")
        yaml.safe_dump(doc, fh, sort_keys=False, width=120, default_flow_style=False)
    print((W / "calibration.yaml").read_text()[:1500])


if __name__ == "__main__":
    main()
