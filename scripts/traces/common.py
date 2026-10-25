"""Shared helpers for the agent-trace scripts: tool classes, distribution summaries, lognormal and two-component
lognormal-mixture fits, Kolmogorov-Smirnov distances, empirical quantile tables. numpy/scipy only."""
from __future__ import annotations

import numpy as np
from scipy import stats
from scipy.special import logsumexp

# ---------------------------------------------------------------- tool classes (TraceLab tool names; see notes/lit/AGENT_TRACES.md)
_SHELL = {"Bash", "bash", "exec", "exec_command", "shell_command", "shell", "run", "KillBash", "KillShell"}
_FILE = {"Read", "Edit", "Write", "Grep", "Glob", "apply_patch", "MultiEdit", "NotebookEdit", "LS", "view_image", "LSP"}
_WEB = {"WebFetch", "WebSearch"}
_HUMAN = {"AskUserQuestion", "ExitPlanMode", "EnterPlanMode", "request_user_input"}
_DELEG = {"Agent", "Task", "Explore", "spawn_agent", "wait_agent", "send_message", "SendMessage", "close_agent", "list_agents", "followup_task",
          "send_input", "interrupt_agent", "resume_agent", "create_thread", "read_thread", "read_thread_terminal", "wait_threads",
          "list_threads", "list_projects", "TeamCreate", "Workflow"}
_POLL = {"write_stdin", "wait", "Monitor", "ScheduleWakeup", "TaskOutput", "BashOutput", "TaskStop", "CronCreate", "CronDelete", "CronList"}
_BOOK = {"TaskCreate", "TaskUpdate", "TaskList", "TaskGet", "TaskSearch", "TodoWrite", "update_plan", "ToolSearch", "Skill", "StructuredOutput",
         "get_goal", "update_goal", "create_goal", "SendUserFile", "PushNotification", "Artifact", "ReportFindings", "EnterWorktree",
         "ExitWorktree"}


def tool_class(name: str) -> str:
    if name in _SHELL:
        return "shell"
    if name in _FILE:
        return "file"
    if name in _WEB:
        return "web"
    if name in _HUMAN:
        return "human"
    if name in _DELEG:
        return "deleg"
    if name in _POLL:
        return "poll"
    if name in _BOOK:
        return "book"
    return "other"          # custom_tool_N (MCP), browser_*, list_mcp_*, ...


# ---------------------------------------------------------------- summaries
def dist_summary(x, extra_q=(10, 25, 75, 95)) -> dict:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    n = int(x.size)
    if n == 0:
        return {"n": 0}
    m = float(x.mean())
    sd = float(x.std(ddof=1)) if n > 1 else 0.0
    out = {"n": n, "mean": m, "median": float(np.median(x)), "p90": float(np.percentile(x, 90)), "p99": float(np.percentile(x, 99)),
           "std": sd, "cv": sd / m if m > 0 else float("nan"), "min": float(x.min()), "max": float(x.max()),
           "mean_w999": float(np.minimum(x, np.percentile(x, 99.9)).mean())}      # mean after winsorising at the 99.9th percentile
    for q in extra_q:
        out[f"p{q}"] = float(np.percentile(x, q))
    return out


def quantile_table(x) -> list[float]:
    """1st..99th percentiles (99 values, linear interpolation)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    return [float(v) for v in np.percentile(x, np.arange(1, 100))]


# ---------------------------------------------------------------- KS distance against a continuous CDF
def ks_distance(x, cdf) -> float:
    """sup_x |F_n(x) - F(x)| for a sample that may contain ties (evaluated at both sides of every distinct value)."""
    x = np.sort(np.asarray(x, dtype=float))
    n = x.size
    u, idx_first, counts = np.unique(x, return_index=True, return_counts=True)
    F = cdf(u)
    upper = (idx_first + counts) / n
    lower = idx_first / n
    return float(max(np.max(np.abs(upper - F)), np.max(np.abs(lower - F))))


# ---------------------------------------------------------------- lognormal
def _ks_prepared(x):
    """Precompute distinct values and ECDF levels on both sides so many CDFs can be tested cheaply."""
    x = np.sort(np.asarray(x, dtype=float))
    n = x.size
    u, idx_first, counts = np.unique(x, return_index=True, return_counts=True)
    return u, (idx_first + counts) / n, idx_first / n


def _ks_from_prepared(prep, F) -> float:
    u, upper, lower = prep
    return float(max(np.max(np.abs(upper - F)), np.max(np.abs(lower - F))))


def fit_lognormal(x, floor: float) -> dict:
    """MLE lognormal on max(x, floor). Reports (mu, sigma) of log x, the implied mean and CV and the KS distance, plus
    `mean_preserving`: the lognormal with the SAMPLE MEAN that has the KS-optimal CV (what the simulator's
    tool_time_dist='lognormal' takes as tool_time_mean_s / tool_time_cv; the mean fixes the idle-session count by Little's law)
    and `moment_matched` (same sample mean and CV)."""
    x = np.maximum(np.asarray(x, dtype=float), floor)
    y = np.log(x)
    mu, sg = float(y.mean()), float(y.std())
    prep = _ks_prepared(x)
    u = prep[0]
    lu = np.log(u)
    D = _ks_from_prepared(prep, stats.norm.cdf((lu - mu) / sg))
    mean_fit = float(np.exp(mu + 0.5 * sg * sg))
    cv_fit = float(np.sqrt(np.expm1(sg * sg)))
    m, s = float(x.mean()), float(x.std(ddof=1))
    cvm = s / m
    s2 = np.log1p(cvm * cvm)
    mu_m, sg_m = np.log(m) - 0.5 * s2, np.sqrt(s2)
    Dm = _ks_from_prepared(prep, stats.norm.cdf((lu - mu_m) / sg_m))
    best = None
    for cv in np.geomspace(0.1, 60.0, 300):
        s2c = np.log1p(cv * cv)
        sgc, muc = np.sqrt(s2c), np.log(m) - 0.5 * s2c
        d = _ks_from_prepared(prep, stats.norm.cdf((lu - muc) / sgc))
        if best is None or d < best[0]:
            best = (d, float(cv), float(muc), float(sgc))
    return {"mu": mu, "sigma": sg, "mean_implied": mean_fit, "cv_implied": cv_fit, "ks": D,
            "moment_matched": {"mean": m, "cv": cvm, "mu": float(mu_m), "sigma": float(sg_m), "ks": Dm},
            "mean_preserving": {"mean": m, "cv": best[1], "mu": best[2], "sigma": best[3], "ks": best[0]}, "floor_s": floor}


# ---------------------------------------------------------------- two-component lognormal mixture (EM on log x)
def fit_lognormal_mixture(x, floor: float, seed: int = 0, max_n: int = 300_000, iters: int = 600, tol: float = 1e-10) -> dict:
    x = np.maximum(np.asarray(x, dtype=float), floor)
    y_all = np.log(x)
    rng = np.random.default_rng(seed)
    y = y_all if y_all.size <= max_n else rng.choice(y_all, size=max_n, replace=False)
    best = None
    for q in (0.2, 0.4, 0.6, 0.8):
        thr = np.quantile(y, q)
        lo = y <= thr
        if lo.sum() < 2 or (~lo).sum() < 2:
            continue
        w = np.array([lo.mean(), 1.0 - lo.mean()])
        mu = np.array([y[lo].mean(), y[~lo].mean()])
        sg = np.array([max(y[lo].std(), 0.2), max(y[~lo].std(), 0.2)])
        prev = -np.inf
        ll = -np.inf
        for _ in range(iters):
            logp = np.log(w)[:, None] + stats.norm.logpdf(y[None, :], mu[:, None], sg[:, None])
            lse = logsumexp(logp, axis=0)
            ll = float(lse.sum())
            r = np.exp(logp - lse)
            nk = r.sum(axis=1)
            w = nk / y.size
            mu = (r * y).sum(axis=1) / nk
            sg = np.sqrt(np.maximum((r * (y - mu[:, None]) ** 2).sum(axis=1) / nk, 0.04))
            if abs(ll - prev) < tol * abs(ll):
                break
            prev = ll
        if best is None or ll > best[0]:
            best = (ll, w.copy(), mu.copy(), sg.copy())
    ll, w, mu, sg = best
    order = np.argsort(mu)
    w, mu, sg = w[order], mu[order], sg[order]

    def cdf(v):
        lv = np.log(v)
        return sum(w[i] * stats.norm.cdf((lv - mu[i]) / sg[i]) for i in range(2))

    D = ks_distance(x, cdf)
    mean = float(np.sum(w * np.exp(mu + 0.5 * sg ** 2)))
    m2 = float(np.sum(w * np.exp(2 * mu + 2 * sg ** 2)))
    cv = float(np.sqrt(max(m2 / mean ** 2 - 1.0, 0.0)))
    comps = [{"weight": float(w[i]), "mu": float(mu[i]), "sigma": float(sg[i]),
              "median_s": float(np.exp(mu[i])), "mean_s": float(np.exp(mu[i] + 0.5 * sg[i] ** 2)),
              "cv": float(np.sqrt(np.expm1(sg[i] ** 2)))} for i in range(2)]
    # BIC on the fitted subsample
    k = 5
    return {"components": comps, "mean_implied": mean, "cv_implied": cv, "ks": D, "loglik_per_obs": ll / y.size,
            "bic_sub": float(k * np.log(y.size) - 2 * ll), "n_fit": int(y.size), "floor_s": floor}


def lognormal_bic(x, floor: float, max_n: int = 300_000, seed: int = 0) -> float:
    x = np.maximum(np.asarray(x, dtype=float), floor)
    y = np.log(x)
    if y.size > max_n:
        y = np.random.default_rng(seed).choice(y, size=max_n, replace=False)
    mu, sg = y.mean(), y.std()
    ll = float(np.sum(stats.norm.logpdf(y, mu, sg)))
    return float(2 * np.log(y.size) - 2 * ll)


# ---------------------------------------------------------------- reference: the simulator's current assumption
def ks_vs_exponential(x, mean: float) -> float:
    x = np.maximum(np.asarray(x, dtype=float), 0.0)
    return ks_distance(x, lambda v: 1.0 - np.exp(-v / mean))


def geometric_mean_param(target_mean: float, max_turns: int) -> float:
    """mean_turns m such that E[min(Geometric(1/m), max_turns)] = target_mean (WorkloadParams.effective_mean_turns)."""
    from scipy.optimize import brentq

    def f(m):
        p = 1.0 / m
        return (1.0 - (1.0 - p) ** max_turns) / p - target_mean

    hi = 1e6
    if target_mean >= max_turns:
        return float("inf")
    return float(brentq(f, 1.0 + 1e-9, hi))


# ---------------------------------------------------------------- simulator-facing helpers (tool_time_dist: empirical / bimodal)
def quantile_levels(step: float = 0.005, tail_start: float = 0.01, ratio: float = 2 ** 0.25) -> list[float]:
    """Levels of the empirical quantile table written into the proposed configs: strictly increasing from 0.0 to 1.0
    (what WorkloadParams.tool_time_quantile_levels requires). Steps of `step` up to 1 - tail_start, then 1 - u shrinking by `ratio`
    per point down to 2e-6, and 1.0. A plain 1%-grid underestimates a heavy tail: the piecewise-linear inverse CDF built from the
    1st..99th percentiles alone overstates the mean of the SyFI series by 8% (the slowest 1% of the capped series holds 39% of its total time), this grid by 0.4%."""
    g = [0.0, step / 4.0] + [i * step for i in range(1, int(round((1.0 - tail_start) / step)) + 1) if i * step < 1.0 - tail_start - 1e-12]
    t = tail_start
    while t > 2e-6:
        g.append(1.0 - t)
        t /= ratio
    g.append(1.0)
    out = sorted(set(round(x, 7) for x in g))
    assert out[0] == 0.0 and out[-1] == 1.0 and all(b > a for a, b in zip(out[:-1], out[1:]))
    return out


def empirical_moments(levels, values) -> tuple[float, float]:
    """(mean, CV) of the distribution whose inverse CDF is the piecewise-linear interpolation of the table (exact integrals of
    F^-1 and F^-2). Same formula as prefixmeta.workload.empirical_moments (branch r7/robustness, commit 8c08883), which the
    simulator reports as the 'exact moments' of an empirical tool-time law."""
    lv = np.asarray(levels, dtype=float)
    v = np.asarray(values, dtype=float)
    d = np.diff(lv)
    m1 = float(np.sum(d * (v[:-1] + v[1:]) / 2.0))
    m2 = float(np.sum(d * (v[:-1] ** 2 + v[:-1] * v[1:] + v[1:] ** 2) / 3.0))
    var = max(m2 - m1 * m1, 0.0)
    return m1, (float(np.sqrt(var)) / m1 if m1 > 0 else float("nan"))


def two_point_match(mean: float, cv: float, lo: float) -> dict:
    """Two-point law on {lo, hi} with P(hi) = p that has exactly the given mean and CV (3 unknowns lo, hi, p; `lo` is chosen, the
    mean and the variance fix hi and p): with a = mean - lo, hi - lo = a + var / a and p = a / (hi - lo)."""
    a = mean - lo
    if not (0.0 < lo < mean):
        raise ValueError("need 0 < lo < mean")
    var = (cv * mean) ** 2
    d = a + var / a
    p = a / d
    return {"lo": float(lo), "hi": float(lo + d), "p_hi": float(p), "mean": float(lo + p * d), "cv": float(np.sqrt(p * (1 - p)) * d / (lo + p * d))}
