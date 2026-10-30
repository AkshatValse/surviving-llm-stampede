"""F7 (double column): the registered paired kill test with the native KV pool (native E2), at 2.5 and 4.0 x lambda_ref.

Same layout and computation as F1 (fig1_e2_timeseries.draw): per arm (BURST, NOBURST, CAPPED) and seed, the registered hit
metric in 100 s windows (analysis.windows.window_table) and the verdict's backlog series (sessions in the system, 50 s bins).
SGLang 0.5.22, Qwen2.5-7B-Instruct, one A100 80GB PCIe, KV pool sized by SGLang (955,757 tokens); registration
configs/agentload_prereg_2026-10-25_native.yaml (cell sglang-fcfs-r1-native, lambda_ref = 0.07180 sessions/s, native E0a
turns-based; cap n_cap = 64); jobs 17102173-90; verdict results/agentload_analysis_burst2/20261026-100653 in the pull.
Run:  python figures/paper/fig7_e2_native_timeseries.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fig1_e2_timeseries as F1  # noqa: E402

PULL = "results/nova/e2_native_vllm_burst_pulled_20261026-101256"
VERDICT = f"{PULL}/results/agentload_analysis_burst2/20261026-100653"
N_CAP_NATIVE = 64                  # registered cap (configs/agentload_prereg_2026-10-25_native.yaml, measured.n_cap)


def main() -> None:
    F1.draw(PULL, VERDICT, (2.5, 4.0), N_CAP_NATIVE, "fig7_e2_native_timeseries", bl_ylim=(1, 3000),
            bl_ticks=(1, 10, 100, 1000), height=3.6, top=0.925, bottom=0.18, label_dx=700.0)


if __name__ == "__main__":
    main()
