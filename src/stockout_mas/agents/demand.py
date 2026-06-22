"""Demand agent — forecasts near-term demand and its uncertainty.

Uses exponential smoothing on observed sales+lost demand (true demand signal).
Posts a forecast vector and a sigma estimate to the blackboard so the inventory
agent can size safety stock and the pricing agent can read demand pressure.
"""
from __future__ import annotations

import statistics

from .base import Agent


class DemandAgent(Agent):
    scopes = {"read:sales", "write:forecast"}

    def __init__(self, name, cfg, bb):
        super().__init__(name, cfg, bb)
        self.level = cfg.base_demand
        self.alpha = 0.35
        self.errors: list[float] = []

    def observe(self, true_demand: float) -> None:
        pred = self.level
        self.errors.append(true_demand - pred)
        self.errors = self.errors[-20:]
        self.level = self.alpha * true_demand + (1 - self.alpha) * self.level

    def forecast(self, tick: int, horizon: int = 4) -> dict:
        sigma = statistics.pstdev(self.errors) if len(self.errors) >= 2 else self.cfg.base_demand * self.cfg.demand_noise_cv
        fc = {
            "mean_per_tick": round(self.level, 2),
            "horizon": horizon,
            "sigma": round(max(sigma, 1.0), 2),
        }
        self.bb.write(tick, "forecast", fc)
        return fc
