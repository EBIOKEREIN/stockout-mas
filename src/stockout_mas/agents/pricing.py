"""Pricing agent — sets the sell price to shape demand.

Governed mode (pricing_respects_stock=True): the agent reads the stock-health
signal off the blackboard. It only marks DOWN when inventory is genuinely in
excess, and marks UP to dampen demand when a stockout is projected.

Ungoverned mode (False): the agent chases short-term revenue/volume and will
mark down whenever recent sales soften — even mid-stockout. This is the lever
that produces the pricing-vs-inventory conflict described in the emergence doc.
"""
from __future__ import annotations

from .base import Agent


class PricingAgent(Agent):
    scopes = {"read:inventory", "read:stock_health", "write:price"}

    def __init__(self, name, cfg, bb):
        super().__init__(name, cfg, bb)
        self.price = cfg.sell_price
        self.recent_sales: list[float] = []

    def observe(self, sales: float) -> None:
        self.recent_sales.append(sales)
        self.recent_sales = self.recent_sales[-4:]

    def decide(self, tick: int, stock_health: float) -> dict:
        """stock_health in [0,1]: 1 = ample cover, 0 = imminent stockout."""
        old = self.price
        ref = self.cfg.ref_price

        if self.cfg.pricing_respects_stock:
            if stock_health < 0.35:
                target = ref * 1.10          # cool demand to protect service
            elif stock_health > 0.85:
                target = ref * 0.92           # only discount on real excess
            else:
                target = ref
        else:
            # ungoverned: discount whenever sales soften, ignore stock state
            softening = (len(self.recent_sales) >= 2
                         and self.recent_sales[-1] < self.recent_sales[0])
            target = ref * (0.85 if softening else 1.0)

        # move 50% toward target; respect approval band downstream
        new = old + 0.5 * (target - old)
        self.price = round(new, 2)
        decision = {
            "old_price": old, "new_price": self.price,
            "stock_health": round(stock_health, 2),
            "pct_change": round((self.price - old) / old, 3) if old else 0.0,
        }
        self.bb.write(tick, "price", self.price)
        return decision
