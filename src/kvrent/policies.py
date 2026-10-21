"""KV retention policies.

A policy returns (tau, action) at tool-call start:
  tau    : seconds to hold the KV resident (inf = hold throughout, 0 = evict now).
           If the tool returns at D <= tau the call counts as "held".
  action : EVICT_SWAP or EVICT_DISCARD, used when the tool outlasts tau.

CONTINUUM_TTL is OUR reimplementation of the idea (per-tool empirical-CDF
TTL), not the authors' code. rent_rate = eta * L / M is a proxy for the
endogenous queueing cost of holding memory (modeling limitation).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

EVICT_SWAP = 0
EVICT_DISCARD = 1
INF = math.inf

POLICY_NAMES = ["ALWAYS_HOLD", "ALWAYS_SWAP", "ALWAYS_DISCARD", "CONTINUUM_TTL",
                "SKI_DET", "SKI_RAND", "ORACLE_STATIC"]
ETA_FREE = {"ALWAYS_HOLD", "ALWAYS_SWAP", "ALWAYS_DISCARD"}


@dataclass(frozen=True)
class Costs:
    p: float   # prefill s/token
    s: float   # swap s/token (each direction)
    M: float   # KV capacity (tokens)

    def buy(self, L: float) -> float:
        """Reload cost avoided by holding (s): min(2 s L, p L)."""
        return min(2.0 * self.s * L, self.p * L)

    def cheaper(self) -> int:
        return EVICT_SWAP if 2.0 * self.s <= self.p else EVICT_DISCARD


class Policy:
    name = "BASE"

    def decide(self, tool: int, L: int, D: float) -> tuple[float, int]:
        raise NotImplementedError

    def observe(self, tool: int, D: float) -> None:
        pass


class AlwaysHold(Policy):
    name = "ALWAYS_HOLD"

    def __init__(self, costs: Costs):
        self.c = costs

    def decide(self, tool, L, D):
        return INF, self.c.cheaper()


class AlwaysSwap(Policy):
    name = "ALWAYS_SWAP"

    def decide(self, tool, L, D):
        return 0.0, EVICT_SWAP


class AlwaysDiscard(Policy):
    name = "ALWAYS_DISCARD"

    def decide(self, tool, L, D):
        return 0.0, EVICT_DISCARD


class SkiDet(Policy):
    """Hold for B = buy/rent_rate, then evict with the cheaper action."""
    name = "SKI_DET"

    def __init__(self, costs: Costs, eta: float):
        self.c, self.eta = costs, eta

    def B(self, L: int) -> float:
        return self.c.buy(L) / (self.eta * L / self.c.M)

    def decide(self, tool, L, D):
        return self.B(L), self.c.cheaper()


class SkiRand(SkiDet):
    """tau ~ density e^{x/B}/(B(e-1)) on [0,B]; inverse CDF B ln(1+u(e-1))."""
    name = "SKI_RAND"

    def __init__(self, costs: Costs, eta: float, rng: np.random.Generator):
        super().__init__(costs, eta)
        self.rng = rng

    def decide(self, tool, L, D):
        u = self.rng.random()
        return self.B(L) * math.log1p(u * (math.e - 1.0)), self.c.cheaper()


class OracleStatic(Policy):
    """Clairvoyant per-call: hold iff rent_rate * D < buy, else evict now."""
    name = "ORACLE_STATIC"

    def __init__(self, costs: Costs, eta: float):
        self.c, self.eta = costs, eta

    def decide(self, tool, L, D):
        rent = self.eta * L / self.c.M
        if rent * D < self.c.buy(L):
            return INF, self.c.cheaper()
        return 0.0, self.c.cheaper()


class ContinuumTTL(Policy):
    """tau* = argmax_tau F(tau)*Benefit - eta*(L/M)*E[min(D,tau)], per-tool empirical CDF.

    Holds (tau=inf) for a tool type until `warmup_obs` observations exist.
    Tables (sorted candidates, F, E[min(D,tau)]) are refreshed every
    `refresh_every` new observations on a <= `grid`-point quantile grid.
    """
    name = "CONTINUUM_TTL"

    def __init__(self, costs: Costs, eta: float, n_tools: int, warmup_obs: int = 200,
                 refresh_every: int = 25, grid: int = 256):
        self.c, self.eta = costs, eta
        self.warm, self.every, self.grid = warmup_obs, refresh_every, grid
        self.obs: list[list[float]] = [[] for _ in range(n_tools)]
        self.tab: list[tuple[np.ndarray, np.ndarray, np.ndarray] | None] = [None] * n_tools
        self.last_refresh = [0] * n_tools

    def observe(self, tool, D):
        o = self.obs[tool]
        o.append(D)
        n = len(o)
        if n >= self.warm and (self.tab[tool] is None or n - self.last_refresh[tool] >= self.every):
            self._refresh(tool)

    def _refresh(self, tool: int) -> None:
        d = np.sort(np.asarray(self.obs[tool]))
        n = len(d)
        cs = np.cumsum(d)
        j = np.arange(1, n + 1)
        F = j / n
        Emin = (cs + (n - j) * d) / n
        if n > self.grid:
            sel = np.unique(np.linspace(0, n - 1, self.grid).astype(int))
            d, F, Emin = d[sel], F[sel], Emin[sel]
        self.tab[tool] = (d, F, Emin)
        self.last_refresh[tool] = n

    def decide(self, tool, L, D):
        t = self.tab[tool]
        if t is None:
            return INF, self.c.cheaper()
        d, F, Emin = t
        val = F * self.c.buy(L) - self.eta * (L / self.c.M) * Emin
        j = int(np.argmax(val))
        tau = float(d[j]) if val[j] > 0.0 else 0.0
        return tau, self.c.cheaper()


def make_policy(name: str, costs: Costs, eta: float, n_tools: int,
                rng: np.random.Generator, pcfg: dict) -> Policy:
    if name == "ALWAYS_HOLD":
        return AlwaysHold(costs)
    if name == "ALWAYS_SWAP":
        return AlwaysSwap()
    if name == "ALWAYS_DISCARD":
        return AlwaysDiscard()
    if name == "SKI_DET":
        return SkiDet(costs, eta)
    if name == "SKI_RAND":
        return SkiRand(costs, eta, rng)
    if name == "ORACLE_STATIC":
        return OracleStatic(costs, eta)
    if name == "CONTINUUM_TTL":
        return ContinuumTTL(costs, eta, n_tools, pcfg["continuum_warmup_obs"],
                            pcfg["continuum_refresh_every"], pcfg["continuum_grid"])
    raise ValueError(name)
