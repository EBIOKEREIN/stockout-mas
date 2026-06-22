"""The world the agents act on.

Deterministic given a seed. Tracks on-hand inventory, the open-PO pipeline,
realized demand (price-sensitive), and accrues cost. Supports point-in-time
snapshots so the orchestrator can roll back the last committed action.
"""
from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field

from ..config import Config


@dataclass
class PurchaseOrder:
    po_id: str
    supplier: str
    qty: float
    unit_cost: float
    placed_tick: int
    arrival_tick: int
    cancelled: bool = False
    arrived: bool = False


@dataclass
class TickRecord:
    tick: int
    demand: float
    sales: float
    lost_sales: float
    on_hand_end: float
    inv_position: float
    order_qty: float
    price: float
    holding_cost: float
    stockout_cost: float
    order_cost: float
    cogs: float
    revenue: float


class Environment:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rng = random.Random(cfg.seed)
        self.tick = 0
        self.on_hand = cfg.init_on_hand
        self.price = cfg.sell_price
        self.open_pos: list[PurchaseOrder] = []
        self._po_seq = 0
        self.records: list[TickRecord] = []
        self._pending_order_qty = 0.0  # set by orchestrator before step()
        self._recent_demand: list[float] = [cfg.base_demand]

    def expedite_surcharge(self, order_qty: float) -> float:
        """Rush-order premium: orders far above recent demand cost extra
        (overtime, expediting, capacity scramble). This is what makes order
        volatility / bullwhip genuinely expensive, as it is in practice."""
        base = sum(self._recent_demand) / len(self._recent_demand)
        excess = max(0.0, order_qty - self.cfg.expedite_band * base)
        return self.cfg.expedite_rate * excess

    # ---- demand model -------------------------------------------------
    def _demand_mean(self, tick: int) -> float:
        mult = 1.0
        if self.cfg.spike_start <= tick < self.cfg.spike_start + self.cfg.spike_len:
            mult = self.cfg.spike_mult
        price_factor = (self.price / self.cfg.ref_price) ** (-self.cfg.elasticity)
        return self.cfg.base_demand * mult * price_factor

    def realized_demand(self, tick: int) -> float:
        mean = self._demand_mean(tick)
        sigma = max(1.0, mean * self.cfg.demand_noise_cv)
        return max(0.0, self.rng.gauss(mean, sigma))

    # ---- pipeline -----------------------------------------------------
    @property
    def on_order(self) -> float:
        return sum(po.qty for po in self.open_pos if not po.cancelled and not po.arrived)

    @property
    def inv_position(self) -> float:
        return self.on_hand + self.on_order

    def place_order(self, supplier: str, qty: float, unit_cost: float, lead_time: int) -> PurchaseOrder:
        self._po_seq += 1
        po = PurchaseOrder(
            po_id=f"PO{self._po_seq:04d}", supplier=supplier, qty=qty,
            unit_cost=unit_cost, placed_tick=self.tick,
            arrival_tick=self.tick + lead_time,
        )
        self.open_pos.append(po)
        return po

    def cancel_last_order(self) -> str | None:
        """Rollback hook: cancel the most recent not-yet-arrived PO."""
        for po in reversed(self.open_pos):
            if not po.cancelled and po.arrival_tick > self.tick:
                po.cancelled = True
                return po.po_id
        return None

    def set_price(self, price: float) -> None:
        self.price = price

    # ---- snapshot / rollback -----------------------------------------
    def snapshot(self) -> dict:
        return {
            "tick": self.tick, "on_hand": self.on_hand, "price": self.price,
            "open_pos": copy.deepcopy(self.open_pos), "po_seq": self._po_seq,
        }

    def restore(self, snap: dict) -> None:
        self.tick = snap["tick"]
        self.on_hand = snap["on_hand"]
        self.price = snap["price"]
        self.open_pos = copy.deepcopy(snap["open_pos"])
        self._po_seq = snap["po_seq"]

    # ---- advance one tick --------------------------------------------
    def step(self, order_qty: float) -> TickRecord:
        cfg = self.cfg
        # 1. receive arrivals
        for po in self.open_pos:
            if not po.cancelled and not po.arrived and po.arrival_tick == self.tick:
                self.on_hand += po.qty
                po.arrived = True
        # 2. realize demand and fulfil
        demand = self.realized_demand(self.tick)
        sales = min(self.on_hand, demand)
        lost = demand - sales
        self.on_hand -= sales
        # 3. accrue costs
        holding = self.on_hand * cfg.holding_cost
        stockout = lost * cfg.stockout_penalty
        order_cost = (cfg.order_fixed_cost + self.expedite_surcharge(order_qty)) if order_qty > 0 else 0.0
        # COGS is the cost of *this tick's* placed order (recognized on placement)
        cogs = 0.0
        for po in self.open_pos:
            if po.placed_tick == self.tick and not po.cancelled:
                cogs += po.qty * po.unit_cost
        revenue = sales * self.price
        rec = TickRecord(
            tick=self.tick, demand=demand, sales=sales, lost_sales=lost,
            on_hand_end=self.on_hand, inv_position=self.inv_position,
            order_qty=order_qty, price=self.price, holding_cost=holding,
            stockout_cost=stockout, order_cost=order_cost, cogs=cogs, revenue=revenue,
        )
        self.records.append(rec)
        self._recent_demand.append(demand)
        self._recent_demand = self._recent_demand[-5:]
        self.tick += 1
        return rec
