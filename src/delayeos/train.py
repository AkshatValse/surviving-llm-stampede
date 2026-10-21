"""One training run (optimizer x mode x batch x eta x seed) with periodic curvature measurement."""
from __future__ import annotations

import itertools
from typing import Any, Iterator, Optional

import numpy as np

from .curvature import sharpness
from .mlp import MLPSpec, init_params, loss_and_grad, loss_only
from .optim import Adam, BaseOptimizer, DelayedStepper, MuonLike

RUN_KEYS = ("optimizer", "beta1", "mode", "batch", "eta", "seed")


def expand_grid(cfg: dict) -> list[dict]:
    """All runs of the grid, full-batch runs first (so a truncated grid still has the priority runs)."""
    runs: list[dict] = []
    n = cfg["data"]["n"]
    for batch in sorted(cfg["batches"], reverse=True):
        for opt_name, ocfg in cfg["optimizers"].items():
            beta1s = ocfg["beta1"] if opt_name == "adam" else [float("nan")]
            for beta1, mode, eta, seed in itertools.product(beta1s, ocfg["modes"], cfg["etas"], cfg["seeds"]):
                runs.append({"optimizer": opt_name, "beta1": float(beta1), "mode": mode,
                             "batch": int(min(batch, n)), "eta": float(eta), "seed": int(seed)})
    return runs


def make_optimizer(run: dict, cfg: dict, spec: MLPSpec) -> BaseOptimizer:
    ocfg = cfg["optimizers"][run["optimizer"]]
    if run["optimizer"] == "adam":
        return Adam(spec.n_params, run["eta"], run["beta1"], ocfg["beta2"], ocfg["eps"])
    if run["optimizer"] == "muon":
        return MuonLike(spec, run["eta"], ocfg["momentum"], ocfg["bias_beta1"], ocfg["bias_beta2"],
                        ocfg["bias_eps"], ocfg["rank_rtol"])
    raise ValueError(f"unknown optimizer {run['optimizer']!r}")


def batch_stream(rng: np.random.Generator, n: int, batch: int) -> Iterator[Optional[np.ndarray]]:
    """Epoch-wise shuffled minibatch indices (drop-last); yields None for the full batch."""
    if batch >= n:
        while True:
            yield None
    while True:
        perm = rng.permutation(n)
        for i in range(n // batch):
            yield perm[i * batch:(i + 1) * batch]


def run_one(run: dict, cfg: dict, X: np.ndarray, Y: np.ndarray) -> dict[str, Any]:
    """Train one configuration; returns {'summary': dict, 'curv': list[dict], 'loss': ndarray (per step), 'theta': final params}.

    Per-seed streams (SeedSequence(seed).spawn(3)) = (init, batches, probe/power-iteration); they do not depend on
    optimizer/mode/eta, so configurations with the same seed share the init and the minibatch sequence.
    Gradient delay: the gradient evaluated at x_t (on batch B_t) is computed at step t and consumed by the
    optimizer at step t+tau (see DelayedStepper); logged loss is the full-data loss at x_t.
    """
    n, d_in = X.shape
    spec = MLPSpec(d_in, cfg["model"]["d_hidden"], Y.shape[1])
    steps = int(cfg["steps"])
    ccfg, mcfg = cfg["curvature"], cfg["metrics"]
    every = int(ccfg["every"])
    s_init, s_batch, s_probe = np.random.SeedSequence(run["seed"]).spawn(3)
    rng_init, rng_batch, rng_probe = (np.random.default_rng(s) for s in (s_init, s_batch, s_probe))

    theta = init_params(spec, rng_init)
    probe_idx = rng_probe.choice(n, size=min(int(cfg["probe_batch"]), n), replace=False)
    full_batch = run["batch"] >= n
    Xp, Yp = (X, Y) if full_batch else (X[np.sort(probe_idx)], Y[np.sort(probe_idx)])
    v_sp = rng_probe.standard_normal(spec.n_params)  # warm-start vectors for the power iterations
    v_s = rng_probe.standard_normal(spec.n_params)

    stream = batch_stream(rng_batch, n, run["batch"])
    base = make_optimizer(run, cfg, spec)
    stepper = DelayedStepper(base, run["mode"], tau=int(cfg["delay_tau"]))

    losses = np.full(steps, np.nan)
    curv: list[dict] = []
    diverged, div_step = False, -1
    div_thr = float(mcfg["divergence_loss"])
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        for t in range(steps):
            idx = next(stream)
            if idx is None:
                L_b, g = loss_and_grad(theta, X, Y, spec)
                L_full = L_b
            else:
                L_b, g = loss_and_grad(theta, X[idx], Y[idx], spec)
                L_full = loss_only(theta, X, Y, spec)
            if not np.isfinite(L_full) or L_full > div_thr:
                diverged, div_step = True, t
                break
            losses[t] = L_full
            try:
                theta, _ = stepper.step(theta, g)
            except np.linalg.LinAlgError:
                diverged, div_step = True, t
                break
            if not np.all(np.isfinite(theta)):
                diverged, div_step = True, t
                break
            if every > 0 and (t + 1) % every == 0:
                D = base.precond_diag()
                row = {"step": t + 1, "loss": L_full, "eta_SP": np.nan, "eta_S": np.nan, "resid_SP": np.nan,
                       "resid_S": np.nan, "shifted_SP": 0, "shifted_S": 0}
                if D is not None:
                    r = sharpness(theta, Xp, Yp, spec, v_sp, D, ccfg["power_iters"], ccfg["fd_rel"])
                    v_sp = r["v"]
                    row.update(eta_SP=run["eta"] * r["lam"], resid_SP=r["resid"], shifted_SP=int(r["shifted"]))
                r = sharpness(theta, Xp, Yp, spec, v_s, None, ccfg["power_iters"], ccfg["fd_rel"])
                v_s = r["v"]
                row.update(eta_S=run["eta"] * r["lam"], resid_S=r["resid"], shifted_S=int(r["shifted"]))
                curv.append(row)

    summary = summarize(run, cfg, losses, curv, diverged, div_step)
    return {"summary": summary, "curv": curv, "loss": losses, "theta": theta}


def summarize(run: dict, cfg: dict, losses: np.ndarray, curv: list[dict], diverged: bool, div_step: int) -> dict:
    steps = int(cfg["steps"])
    mcfg = cfg["metrics"]
    wl, wc = int(mcfg["final_loss_window"]), int(mcfg["curvature_window"])
    out: dict[str, Any] = {k: run[k] for k in RUN_KEYS}
    out["diverged"] = int(diverged)
    out["div_step"] = div_step
    out["final_loss"] = float("nan") if diverged else float(np.mean(losses[steps - wl:]))
    out["loss_init"] = float(losses[0]) if np.isfinite(losses[0]) else float("nan")
    out["loss_min"] = float(np.nanmin(losses)) if np.any(np.isfinite(losses)) else float("nan")
    last = [r for r in curv if r["step"] > steps - wc]
    for key in ("eta_SP", "eta_S"):
        vals = np.array([r[key] for r in last], dtype=float)
        allv = np.array([r[key] for r in curv], dtype=float)
        out[f"med_{key}_last"] = float(np.nanmedian(vals)) if vals.size and np.any(np.isfinite(vals)) else float("nan")
        out[f"max_{key}_all"] = float(np.nanmax(allv)) if allv.size and np.any(np.isfinite(allv)) else float("nan")
    out["n_meas_last"] = len(last)
    out["n_shifted_SP"] = int(sum(r["shifted_SP"] for r in curv))
    out["n_shifted_S"] = int(sum(r["shifted_S"] for r in curv))
    resid = np.array([r["resid_SP"] for r in last], dtype=float)
    out["med_resid_SP_last"] = float(np.nanmedian(resid)) if resid.size and np.any(np.isfinite(resid)) else float("nan")
    resid = np.array([r["resid_S"] for r in last], dtype=float)
    out["med_resid_S_last"] = float(np.nanmedian(resid)) if resid.size and np.any(np.isfinite(resid)) else float("nan")
    return out
