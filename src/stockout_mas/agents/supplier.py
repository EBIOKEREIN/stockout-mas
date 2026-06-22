"""Supplier agent — a contract-net *responder*.

On a Call-For-Proposals it returns a bid: unit cost, lead time, the quantity it
can actually serve (capacity), and a reliability score. Availability is
stochastic, so a supplier can decline — which is exactly the kind of partial
failure the coordination layer must tolerate.
"""
from __future__ import annotations

import random

from .base import Agent


class SupplierAgent(Agent):
    scopes = {"read:cfp", "write:bid"}

    def __init__(self, name, cfg, bb, unit_cost, lead_time, capacity, reliability, rng: random.Random):
        super().__init__(name, cfg, bb)
        self.unit_cost = unit_cost
        self.lead_time = lead_time
        self.capacity = capacity
        self.reliability = reliability
        self.rng = rng

    def bid(self, qty_requested: float) -> dict | None:
        # occasional outage: with prob (1 - reliability) the supplier can't bid
        if self.rng.random() > self.reliability:
            return None
        servable = min(qty_requested, self.capacity)
        if servable <= 0:
            return None
        # mild capacity-driven price surcharge when stretched
        utilization = servable / self.capacity
        surcharge = 1.0 + 0.05 * max(0.0, utilization - 0.8)
        return {
            "supplier": self.name,
            "unit_cost": round(self.unit_cost * surcharge, 3),
            "lead_time": self.lead_time,
            "qty": round(servable, 1),
            "reliability": self.reliability,
        }
