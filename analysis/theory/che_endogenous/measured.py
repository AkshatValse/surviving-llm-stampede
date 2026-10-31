"""Measured validation targets (NOT model inputs).  Every value with its source file; see paper/NUMBERS.md for commits and jobs.

Model INPUTS are only: the workload (configs/agentload_e2_burst.yaml), the pool size M, the calibrated iteration-time cost
model (calibration/round6_server_log_fit/calibration.yaml, fitted to SGLang server-log batch timing only), and, for a cell
whose costs differ from that calibration (vLLM, H200), the cell's own E0a all-miss token rate (one scale factor).
"""

SC_300K = "results/nova/stageC_1706210x_pulled_20261022-125454/analysis_local/agentload_analysis_closed/20261022-125619/mu_curve.csv"
SC_NATIVE = "results/nova/r7_native_grid_vllm_pulled_20261025-145126/results/agentload_analysis_closed/20261025-144228/mu_curve.csv"
SC_VLLM = "results/nova/stageC_vllm_1716295x_pulled_20261030-153621/results/agentload_analysis_closed/20261030-153533/mu_curve.csv"

MEASURED = {
    "a100_300k": dict(
        M=300_000,
        curve={  # n: (mu sessions/s, mu turns-based, all-turn hit fraction); SC_300K
            16: (0.17555, 0.17576, 0.9321), 20: (0.22389, 0.21502, 0.9268), 24: (0.23333, 0.22552, 0.8877),
            32: (0.11500, 0.11577, 0.5052), 48: (0.04889, 0.06293, 0.0), 96: (0.06111, 0.07298, 0.0),
            300: (0.10778, 0.11144, 0.0)},
        curve_source=SC_300K,
        peak_n="20-24 (argmax 24, n=20 within 4%)", mu_max=0.23333, hit_cross=32.2,
        floor_throughput_implied=(0.072, 0.081),   # SCV review_calc_log (mu_allmiss_proj); mu(300) is biased by the synchronized start
        lambda_miss_turns=0.071534, allmiss_tok_s=11243.18,     # E0A calibration.json
        e0b={1.25: True, 1.5: True, 1.75: True, 2.0: True, 2.5: False, 3.0: False},   # E0B stable_runs.csv (stable?)
        e0b_note="2.5 x run of seed 0 realized 2.73 x (notes/PREDICTIONS_r11_basin.md, plan read)",
        lambda_ref=0.071534,
        e2_points=(1.35, 1.65),
        e2_burst={  # E2 trap_v2_runs.csv (BURST rows): backlog_eval_mean, token ratio, rate_sessions, slope
            1.35: dict(backlog=(232.2, 199.7, 221.4), ratio=(1.0250, 1.0092, 1.0191), rate=(0.0810, 0.0913, 0.0840),
                       slope=(0.02222, 0.00360, 0.01861), min_after=(146.7, 146.8, 135.2), t_min_after=(1050, 1300, 900),
                       capped_drain=(1546.7, 1846.7, 1904.1)),   # paper/derived/e2_capped_drain.csv (s after the burst)
            1.65: dict(backlog=(331.8, 282.7, 311.0), ratio=(1.0252, 1.0294, 1.0256), rate=(0.0897, 0.0967, 0.0960),
                       slope=(0.03201, 0.02766, 0.03621), min_after=(172.1, 170.4, 162.4), t_min_after=(300, 1200, 900),
                       capped_drain=(2693.2, 2020.6, 2127.1))},
        # frozen loopvars (analysis/r11/loopvars_frozen.py @ f1338e3) over [5700, 8700) s, recomputed here on the committed runs
        loopvars={1.35: dict(burst_gap_over_R=(6.916, 6.354, 6.790), good_gap_over_R=(0.019, 0.016, 0.020),
                             burst_R=(25.8, 26.2, 25.9), good_R=(264.9, 306.6, 255.1)),
                  1.65: dict(burst_gap_over_R=(9.672, 8.183, 8.478), good_gap_over_R=(0.024, 0.022, 0.028),
                             burst_R=(25.7, 25.6, 25.7), good_R=(213.4, 229.6, 188.1))},
        stagec_trap_gauge={48: dict(evictable=71e3, running=17.3, queue=23.9), 96: dict(evictable=34e3, running=22.5, queue=66.1),
                           300: dict(evictable=125e3, running=20.3, queue=269)},   # notes/STAGEC_VERIFICATION.md
        survival_vs_gap={16: (131, 5), 24: (50, 5.1), 32: (10.5, 9.1), 48: (6.3, 30.6), 96: (2.9, 66)},
    ),
    "a100_native": dict(
        M=955_757,
        curve={24: (0.2650, 0.252, 0.929), 48: (0.4311, 0.414, 0.929), 64: (0.47889, 0.466, 0.930), 80: (0.47722, 0.464, 0.922),
               96: (0.12278, 0.116, 0.4189), 128: (0.06667, 0.073, 0.0072), 300: (0.10055, 0.107, 0.0)},
        curve_source=SC_NATIVE,
        peak_n="64 (n=80 within 0.4%)", mu_max=0.47889, hit_cross=93.4,
        lambda_miss_turns=0.071797, allmiss_tok_s=11282.0,
        e0b={1.5: True, 2.5: True, 3.5: True, 4.5: True, 5.5: True, 6.5: False},
        lambda_ref=0.0717974,
        e2_points=(2.5, 4.0),
        e2_burst={2.5: dict(backlog=(601.2, 557.0, 583.2), ratio=(1.0784, 1.0736, 1.0740), rate=(0.1093, 0.1033, 0.1120),
                            slope=(0.0848, 0.0829, 0.0794), min_after=(167.7, 161.1, 154.8), t_min_after=(150, 150, 200),
                            capped_drain=(582.8, 511.6, 542.0)),   # paper/derived/e2_native_capped_drain.csv
                  4.0: dict(backlog=(1139.2, 1098.2, 1113.7), ratio=(1.1103, 1.1055, 1.1240), rate=(0.1340, 0.1370, 0.1460),
                            slope=(0.1643, 0.1465, 0.1555), min_after=(231.1, 228.7, 201.5), t_min_after=(100, 100, 100),
                            capped_drain=(936.8, 836.6, 900.4))},
        loopvars={2.5: dict(burst_gap_over_R=(4.572, 4.141, 4.272), good_gap_over_R=(0.012, 0.010, 0.011),
                            burst_R=(77.5, 77.9, 77.8), good_R=(445.7, 505.2, 449.8)),
                  4.0: dict(burst_gap_over_R=(6.862, 6.682, 6.960), good_gap_over_R=(0.022, 0.018, 0.019),
                            burst_R=(75.1, 75.4, 74.2), good_R=(271.6, 309.5, 306.1))},
    ),
    "vllm_300k": dict(
        M=300_000,
        curve={16: (0.17500, 0.17399, 0.9319), 20: (0.21944, 0.21076, 0.9261), 24: (0.21833, 0.20963, 0.8792),
               28: (0.11889, 0.12284, 0.6584), 32: (0.04333, 0.05438, 0.0830), 40: (0.04111, 0.05551, 0.0075),
               48: (0.04389, 0.05924, 0.0), 96: (0.057, 0.069, 0.0), 300: (0.105, 0.105, 0.0)},
        curve_source=SC_VLLM,
        peak_n="20 (n=24 within 0.5%)", mu_max=0.21944, hit_cross=29.1,
        lambda_miss_turns=0.065663, allmiss_tok_s=10348.97,
        e0b={1.25: True, 1.5: True, 1.75: True, 2.0: True, 2.5: False, 3.0: False},
        lambda_ref=0.065663,
        e2_points=(1.35, 1.65),
        e2_burst={1.35: dict(backlog=(227.3, 202.8, 217.6), ratio=(0.9965, 1.0005, 1.0071)),
                  1.65: dict(backlog=(308.7, 276.6, 300.1), ratio=(1.0309, 1.0252, 1.0263))},
        loopvars={1.35: dict(burst_gap_over_R=(6.709, 6.508, 6.715), burst_R=(28.8, 28.7, 28.5)),
                  1.65: dict(burst_gap_over_R=(8.627, 8.054, 8.297), burst_R=(27.8, 28.0, 27.9))},
    ),
}

# Allowed out-of-sample INPUTS (known before the freeze)
H200_E0A = dict(lambda_miss_turns=0.19388, allmiss_tok_s=29866.0, pop64_token_ratio=1.046)
