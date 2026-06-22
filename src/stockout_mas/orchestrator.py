"""Orchestrator — the supervisor in the hybrid coordination design.

Per tick it sequences five phases:

  1. SENSE      demand agent forecasts; orchestrator computes stock-health
  2. PRICE      pricing agent proposes a price (HITL-gated if move is large)
  3. PLAN       inventory agent proposes an order qty (raw demand for supply)
  4. SOURCE     CONTRACT-NET: CFP -> supplier bids -> award (HITL-gated by value)
  5. GOVERN     circuit breaker checks instability -> rollback + escalate
                then the environment advances one tick

The orchestrator is the only component that mutates the world and the only
one that can route a message, so it is also the single audit chokepoint.
"""
from __future__ import annotations

import random
import statistics

from .audit import AuditLog
from .blackboard import Blackboard
from .config import Config
from .messages import Message, MsgType, Performative
from .agents import DemandAgent, InventoryAgent, SupplierAgent, PricingAgent, ApproverAgent
from .sim.environment import Environment


class Orchestrator:
    def __init__(self, cfg: Config, audit_path: str | None = None, policy_fn=None):
        self.cfg = cfg
        self.bb = Blackboard()
        self.audit = AuditLog(audit_path)
        self.env = Environment(cfg)
        rng = random.Random(cfg.seed + 1)

        self.demand = DemandAgent("demand", cfg, self.bb)
        self.inventory = InventoryAgent("inventory", cfg, self.bb, policy_fn=policy_fn)
        self.pricing = PricingAgent("pricing", cfg, self.bb)
        self.approver = ApproverAgent("approver", cfg, self.bb)
        self.suppliers = [
            SupplierAgent(name, cfg, self.bb, c, lt, cap, rel, rng)
            for name, (c, lt, cap, rel) in cfg.suppliers.items()
        ]
        self.expected_lead = round(statistics.mean(s.lead_time for s in self.suppliers))

        self.cb_trips = 0
        self.rollbacks = 0
        self._order_hist: list[float] = []
        self._demand_hist: list[float] = []

    # ---- routing ------------------------------------------------------
    def _route(self, msg: Message) -> None:
        """Single chokepoint. Enforces scope on the sender, then logs."""
        self.audit.record_message(msg)

    # ---- helpers ------------------------------------------------------
    def _stock_health(self) -> float:
        fc = self.bb.read("forecast", {"mean_per_tick": self.cfg.base_demand, "sigma": 15.0})
        cover_need = fc["mean_per_tick"] * (self.expected_lead + self.cfg.review_period)
        cover_need = max(cover_need, 1.0)
        return max(0.0, min(1.5, self.env.inv_position / cover_need)) / 1.5

    def _contract_net(self, tick: int, qty: float) -> dict | None:
        """CFP -> bids -> award. Returns the winning bid or None."""
        conv = f"cfp-t{tick}"
        cfp = Message(tick=tick, sender="orchestrator", recipients=["*"],
                      msg_type=MsgType.CFP, performative=Performative.REQUEST,
                      conversation_id=conv, payload={"qty": round(qty, 1)})
        self._route(cfp)

        bids = []
        for s in self.suppliers:
            b = s.bid(qty)
            bid_msg = Message(tick=tick, sender=s.name, recipients=["orchestrator"],
                              msg_type=MsgType.BID, performative=Performative.PROPOSE,
                              conversation_id=conv, correlation_id=cfp.msg_id,
                              payload=b or {"declined": True})
            self._route(bid_msg)
            if b:
                bids.append(b)
        if not bids:
            self.audit.record_event(tick, "no_bids", {"qty": qty})
            return None

        def score(b):  # lower is better
            return (self.cfg.w_cost * b["unit_cost"]
                    + self.cfg.w_lead * b["lead_time"]
                    + self.cfg.w_reliability * (1 - b["reliability"]))

        winner = min(bids, key=score)
        award = Message(tick=tick, sender="orchestrator", recipients=[winner["supplier"]],
                        msg_type=MsgType.AWARD, performative=Performative.ACCEPT,
                        conversation_id=conv, payload=winner)
        self._route(award)
        for b in bids:
            if b["supplier"] != winner["supplier"]:
                self._route(Message(tick=tick, sender="orchestrator",
                                    recipients=[b["supplier"]], msg_type=MsgType.NO_AWARD,
                                    performative=Performative.REJECT, conversation_id=conv,
                                    payload={"reason": "outbid"}))
        return winner

    # ---- the tick -----------------------------------------------------
    def run_tick(self) -> None:
        t = self.env.tick
        snap = self.env.snapshot()  # for rollback

        # 1. SENSE
        fc = self.demand.forecast(t)
        self._route(Message(tick=t, sender="demand", recipients=["*"],
                            msg_type=MsgType.FORECAST, performative=Performative.INFORM,
                            payload=fc))
        health = self._stock_health()
        self.bb.write(t, "stock_health", health)

        # 2. PRICE  (HITL-gated)
        pd = self.pricing.decide(t, health)
        appr_p = self.approver.review_price(t, pd["pct_change"])
        if appr_p["status"] == "escalated_pending":
            self.pricing.price = pd["old_price"]            # block until human clears
            self.env.set_price(pd["old_price"])
            self.audit.record_event(t, "price_escalated", appr_p)
        else:
            self.env.set_price(pd["new_price"])
        self._route(Message(tick=t, sender="pricing", recipients=["environment"],
                            msg_type=MsgType.PRICE_UPDATE, performative=Performative.INFORM,
                            payload={"price": self.env.price, "approval": appr_p["status"]}))

        # 3. PLAN
        req = self.inventory.decide(t, self.env.inv_position, self.expected_lead)
        order_qty = req["order_qty"]
        if order_qty > 0:
            self._route(Message(tick=t, sender="inventory", recipients=["orchestrator"],
                                msg_type=MsgType.REPLENISH_REQUEST,
                                performative=Performative.REQUEST, payload=req))

        # 4. GOVERN — circuit breaker (catch a runaway single order BEFORE sourcing)
        if self.cfg.circuit_breaker and order_qty > 0:
            recent = self.env._recent_demand
            base = sum(recent) / len(recent)
            safe = self.cfg.cb_order_mult * base
            if order_qty > safe:                      # genuine runaway catch-up order
                self.cb_trips += 1
                clamped_to = safe
                if self.env.price != snap["price"]:   # also revert a destabilizing price move
                    self.env.set_price(snap["price"])
                    self.pricing.price = snap["price"]
                    self.rollbacks += 1
                self._route(Message(tick=t, sender="orchestrator", recipients=["*"],
                                    msg_type=MsgType.CIRCUIT_BREAK,
                                    performative=Performative.ESCALATE,
                                    payload={"reason": "runaway_order",
                                             "order_before": round(order_qty, 1),
                                             "order_after": round(clamped_to, 1),
                                             "recent_demand": round(base, 1)}))
                self.approver.human_queue.append(
                    {"tick": t, "kind": "circuit_break", "cleared": False,
                     "order_before": round(order_qty, 1), "order_after": round(clamped_to, 1)})
                self.audit.record_event(t, "circuit_break",
                                        {"order_before": round(order_qty, 1),
                                         "order_after": round(clamped_to, 1)})
                order_qty = clamped_to

        # 5. SOURCE via contract-net (+ HITL gate on order value)
        placed_qty = 0.0
        if order_qty > 0:
            winner = self._contract_net(t, order_qty)
            if winner:
                value = winner["qty"] * winner["unit_cost"]
                appr_o = self.approver.review_order(t, value, winner["qty"])
                if appr_o["status"] == "escalated_pending":
                    self.audit.record_event(t, "order_escalated", appr_o)
                else:
                    self.env.place_order(winner["supplier"], winner["qty"],
                                         winner["unit_cost"], winner["lead_time"])
                    placed_qty = winner["qty"]

        self._order_hist.append(placed_qty)
        self._demand_hist.append(fc["mean_per_tick"])

        # advance world
        rec = self.env.step(placed_qty)
        self.demand.observe(rec.demand)
        self.pricing.observe(rec.sales)
        self.bb.write(t, "last_record", rec.__dict__)

    def run(self) -> list:
        for _ in range(self.cfg.horizon):
            self.run_tick()
        return self.env.records
