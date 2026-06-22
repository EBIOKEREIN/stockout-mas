"""Approver agent — the human-in-the-loop proxy.

Gates two action classes against policy thresholds:
  * purchase orders above a dollar value
  * price moves beyond a +/- percentage band

In the mock it auto-approves anything *within* policy (with a simulated latency)
and ESCALATES anything outside policy to a human queue. Swap `auto_approve` off
to force every gated action to a real person. Every decision is logged.
"""
from __future__ import annotations

from .base import Agent


class ApproverAgent(Agent):
    scopes = {"read:approval_request", "write:approval_response", "write:human_queue"}

    def __init__(self, name, cfg, bb):
        super().__init__(name, cfg, bb)
        self.human_queue: list[dict] = []   # items a real human must clear
        self.decisions: list[dict] = []

    def review_order(self, tick: int, order_value: float, qty: float) -> dict:
        needs_human = order_value > self.cfg.approval_order_value
        return self._resolve(tick, "order", needs_human,
                             {"order_value": round(order_value, 2), "qty": qty})

    def review_price(self, tick: int, pct_change: float) -> dict:
        needs_human = abs(pct_change) > self.cfg.approval_price_pct
        return self._resolve(tick, "price", needs_human, {"pct_change": pct_change})

    def _resolve(self, tick: int, kind: str, needs_human: bool, ctx: dict) -> dict:
        if not needs_human:
            d = {"tick": tick, "kind": kind, "status": "auto_approved", **ctx}
        elif self.cfg.auto_approve:
            # within-escalation but auto policy says approve after latency
            d = {"tick": tick, "kind": kind, "status": "approved_with_latency",
                 "latency": self.cfg.human_latency_ticks, **ctx}
            self.human_queue.append({**d, "cleared": True})
        else:
            d = {"tick": tick, "kind": kind, "status": "escalated_pending", **ctx}
            self.human_queue.append({**d, "cleared": False})
        self.decisions.append(d)
        return d
