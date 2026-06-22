"""Inventory agent — decides whether and how much to replenish.

Base-stock (order-up-to) policy: target S = expected demand over the lead time
plus review period, plus z-sigma safety stock. The raw order is the gap between
S and current inventory position.

Two guardrails live here:
  * order_smoothing  -- only close a fraction of the gap each tick (anti-bullwhip)
  * max_order_qty    -- hard clamp on any single PO

`policy_fn` is a pluggable hook: drop in a learned policy (e.g. the DQN from
EBIOKEREIN/inventory-rl) and the rest of the system is unchanged. That seam is
exactly where the MARL bridge would attach.
"""
from __future__ import annotations

import math
from typing import Callable, Optional

from .base import Agent


class InventoryAgent(Agent):
    scopes = {"read:forecast", "read:inventory", "write:replenish_request"}

    def __init__(self, name, cfg, bb, policy_fn: Optional[Callable] = None):
        super().__init__(name, cfg, bb)
        self.policy_fn = policy_fn  # optional override: (state) -> order_qty
        self.last_order = 0.0

    def _base_stock_target(self, lead_time: int, fc: dict) -> float:
        mu = fc["mean_per_tick"]
        sigma = fc["sigma"]
        cover = lead_time + self.cfg.review_period
        safety = self.cfg.service_z * sigma * math.sqrt(cover)
        return mu * cover + safety

    def decide(self, tick: int, inv_position: float, expected_lead: int) -> dict:
        fc = self.bb.read("forecast", {"mean_per_tick": self.cfg.base_demand, "sigma": 15.0})
        mu_r = fc["mean_per_tick"] * self.cfg.review_period   # demand to replace this period
        target = self._base_stock_target(expected_lead, fc)
        gap = target - inv_position                            # may be negative if overstocked

        if self.policy_fn is not None:
            order = float(self.policy_fn({
                "tick": tick, "inv_position": inv_position, "target": target,
                "forecast": fc, "lead": expected_lead,
            }))
        elif self.cfg.order_smoothing:
            # proportional order-up-to (APIOBPCS-style): replace demand, chase a
            # FRACTION of the inventory gap -> damps order variance (anti-bullwhip)
            order = mu_r + self.cfg.smoothing_alpha * gap
        else:
            # pure base-stock: chase the WHOLE gap every tick (bullwhip-prone when
            # the forecast jumps, since the full correction lands in one order)
            order = max(0.0, target - inv_position)

        order = max(0.0, order)
        raw_gap = max(0.0, gap)
        # hard clamp on any single PO
        clamped = min(order, self.cfg.max_order_qty)

        self.last_order = clamped
        req = {
            "target": round(target, 1),
            "raw_gap": round(raw_gap, 1),
            "order_qty": round(clamped, 1),
            "clamped": clamped < order,
        }
        if clamped > 0:
            self.bb.write(tick, "replenish_request", req)
        return req
