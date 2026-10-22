"""Right-censored time-to-event summaries for the escape experiment: Kaplan-Meier, restricted mean, median and the
exponential-MLE mean with an exact (Garwood) Poisson interval. Pure NumPy/SciPy, no simulator dependencies."""
from __future__ import annotations

from typing import Dict, Sequence, Tuple

import numpy as np
from scipy import stats


def kaplan_meier(durations: Sequence[float], events: Sequence[bool]) -> Dict[str, np.ndarray]:
    """Kaplan-Meier estimate. Returns arrays over the distinct EVENT times t_1 < t_2 < ...:
    ``time``, ``at_risk`` (n_i), ``deaths`` (d_i) and ``surv`` (S(t_i) = prod_{j<=i} (1 - d_j / n_j)).
    Observations censored at time c are at risk at every event time <= c (an event at exactly c counts first)."""
    t = np.asarray(durations, dtype=float)
    e = np.asarray(events, dtype=bool)
    if t.shape != e.shape:
        raise ValueError("durations and events must have the same shape")
    ev_times = np.unique(t[e])
    at_risk = np.array([(t >= u).sum() for u in ev_times], dtype=float)
    deaths = np.array([((t == u) & e).sum() for u in ev_times], dtype=float)
    surv = np.cumprod(1.0 - deaths / at_risk) if len(ev_times) else np.zeros(0)
    return {"time": ev_times, "at_risk": at_risk, "deaths": deaths, "surv": surv}


def km_survival_at(km: Dict[str, np.ndarray], t: float) -> float:
    """S(t) from a Kaplan-Meier fit (right-continuous step function, S(0) = 1)."""
    idx = np.searchsorted(km["time"], t, side="right") - 1
    return 1.0 if idx < 0 else float(km["surv"][idx])


def km_restricted_mean(km: Dict[str, np.ndarray], horizon: float) -> float:
    """Restricted mean survival time: integral of S(t) over [0, horizon]. It equals the mean event time only if
    S(horizon) = 0; otherwise it is a LOWER bound on the mean."""
    times = np.concatenate([[0.0], km["time"][km["time"] < horizon], [horizon]])
    surv = np.concatenate([[1.0], km["surv"][km["time"] < horizon]])
    return float(np.sum(surv * np.diff(times)))


def km_median(km: Dict[str, np.ndarray]) -> float:
    """Smallest event time with S <= 0.5; NaN if the curve never reaches 0.5."""
    idx = np.nonzero(km["surv"] <= 0.5)[0]
    return float(km["time"][idx[0]]) if len(idx) else float("nan")


def km_median_ci(durations: Sequence[float], events: Sequence[bool], alpha: float = 0.05
                 ) -> Tuple[float, float, float]:
    """Kaplan-Meier median with a (1 - alpha) interval from the pointwise Greenwood log-log confidence band of S(t)
    (Brookmeyer-Crowley style: the interval is the set of event times at which the band contains 0.5). Returns
    (median, lo, hi); each is NaN when the corresponding curve never reaches 0.5 within the follow-up (the median
    is then censored, a lower bound is the largest observation). Pure NumPy/SciPy."""
    km = kaplan_meier(durations, events)
    n_ev = len(km["time"])
    if n_ev == 0:
        return float("nan"), float("nan"), float("nan")
    z = stats.norm.ppf(1.0 - alpha / 2.0)
    S, n, d = km["surv"], km["at_risk"], km["deaths"]
    with np.errstate(divide="ignore", invalid="ignore"):
        gw = np.cumsum(d / (n * (n - d)))                           # Greenwood sum
        se_loglog = np.sqrt(gw) / np.abs(np.log(S))
        lo_s = S ** np.exp(z * se_loglog)                            # lower band of S
        hi_s = S ** np.exp(-z * se_loglog)                           # upper band of S
    lo_s = np.where(S <= 0, 0.0, lo_s)
    hi_s = np.where(S <= 0, 0.0, hi_s)
    med = float(km["time"][np.nonzero(S <= 0.5)[0][0]]) if (S <= 0.5).any() else float("nan")
    i_lo = np.nonzero(lo_s <= 0.5)[0]
    i_hi = np.nonzero(hi_s <= 0.5)[0]
    return med, (float(km["time"][i_lo[0]]) if len(i_lo) else float("nan")), \
        (float(km["time"][i_hi[0]]) if len(i_hi) else float("nan"))


def exponential_mle(durations: Sequence[float], events: Sequence[bool], alpha: float = 0.05
                    ) -> Dict[str, float]:
    """Exponential MLE with right censoring: rate = d / T (d events, T total exposure). Returns the mean time
    1/rate and an exact two-sided (1 - alpha) interval from the chi-square (Garwood) bound on the Poisson count.
    With d = 0 the mean is infinite (NaN here) and only the lower bound is finite."""
    t = np.asarray(durations, dtype=float)
    d = int(np.sum(np.asarray(events, dtype=bool)))
    T = float(np.sum(t))
    if T <= 0:
        return {"n_events": d, "exposure": T, "rate": float("nan"), "mean": float("nan"),
                "mean_ci_lo": float("nan"), "mean_ci_hi": float("nan")}
    rate_hi = stats.chi2.ppf(1.0 - alpha / 2.0, 2 * d + 2) / (2.0 * T)
    rate_lo = stats.chi2.ppf(alpha / 2.0, 2 * d) / (2.0 * T) if d > 0 else 0.0
    mean = T / d if d > 0 else float("nan")
    return {"n_events": d, "exposure": T, "rate": d / T, "mean": mean,
            "mean_ci_lo": 1.0 / rate_hi, "mean_ci_hi": (1.0 / rate_lo) if rate_lo > 0 else float("inf")}


def summarize_escape(durations: Sequence[float], events: Sequence[bool], horizon: float) -> Dict[str, float]:
    """One-row summary: n, n_events, S(horizon), KM restricted mean, KM median, exponential-MLE mean and CI."""
    km = kaplan_meier(durations, events)
    ex = exponential_mle(durations, events)
    return {"n": int(len(durations)), "n_events": int(np.sum(np.asarray(events, dtype=bool))),
            "surv_at_horizon": km_survival_at(km, horizon), "km_rmst": km_restricted_mean(km, horizon),
            "km_median": km_median(km), "exp_mean": ex["mean"], "exp_mean_ci_lo": ex["mean_ci_lo"],
            "exp_mean_ci_hi": ex["mean_ci_hi"], "exposure": ex["exposure"], "horizon": float(horizon)}


def slopes_log_mean_vs_k(ks: Sequence[float], means: Sequence[float]) -> Tuple[float, ...]:
    """Successive slopes d log(mean) / dk between consecutive sizes."""
    k = np.asarray(ks, dtype=float)
    m = np.log(np.asarray(means, dtype=float))
    return tuple(float(x) for x in np.diff(m) / np.diff(k))
