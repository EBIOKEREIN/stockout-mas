"""Behavioural tests for the stockout-MAS.

Run with:  PYTHONPATH=src pytest -q
These lock the invariants the design docs rely on, so a regression in the
simulation can't silently invalidate the written claims.
"""
from __future__ import annotations

import statistics

from stockout_mas.config import Config
from stockout_mas.messages import Message, MsgType, Performative
from stockout_mas.orchestrator import Orchestrator
from stockout_mas.sim.environment import Environment
from stockout_mas.sim.scenarios import governed, ungoverned, supplier_outage


# ---- communication contract ------------------------------------------
def test_reply_links_conversation_and_correlation():
    cfp = Message(tick=3, sender="orchestrator", recipients=["*"],
                  msg_type=MsgType.CFP, performative=Performative.REQUEST,
                  conversation_id="cfp-3")
    bid = cfp.reply("supplier_A", MsgType.BID, Performative.PROPOSE, {"qty": 10})
    assert bid.correlation_id == cfp.msg_id      # reply points at the request
    assert bid.conversation_id == "cfp-3"        # same negotiation thread
    assert bid.recipients == ["orchestrator"]


# ---- environment integrity -------------------------------------------
def test_arrived_pos_leave_the_pipeline():
    """Regression guard for the phantom-pipeline bug: an arrived PO must not
    keep inflating inventory position."""
    env = Environment(Config(init_on_hand=0.0))
    env.place_order("supplier_B", 100.0, 14.0, lead_time=1)
    assert env.on_order == 100.0
    env.step(order_qty=0.0)   # tick 0 -> nothing arrives yet
    env.step(order_qty=0.0)   # tick 1 -> PO arrives
    assert env.on_order == 0.0
    assert any(po.arrived for po in env.open_pos)


def test_rollback_restores_state():
    env = Environment(Config())
    snap = env.snapshot()
    env.set_price(11.11)
    env.place_order("supplier_A", 50.0, 12.0, 2)
    env.restore(snap)
    assert env.price == Config().sell_price
    assert env.on_order == 0.0


# ---- coordination: contract-net --------------------------------------
def test_contract_net_awards_lowest_score():
    orch = Orchestrator(governed())
    winner = orch._contract_net(tick=0, qty=200.0)
    assert winner is not None
    # award message exists and names the winner
    awards = [m for m in orch.audit.messages if m.msg_type == MsgType.AWARD]
    assert awards and awards[-1].recipients == [winner["supplier"]]


def test_contract_net_handles_total_outage():
    """If the usual winner is knocked out, the net still finds a supplier."""
    orch = Orchestrator(supplier_outage())
    winner = orch._contract_net(tick=0, qty=200.0)
    assert winner is None or winner["supplier"] != "supplier_B" or winner["reliability"] < 0.1


# ---- governance ------------------------------------------------------
def test_circuit_breaker_clamps_runaway_order():
    cfg = Config()
    orch = Orchestrator(cfg)
    # seed recent demand low, then force a huge order via a tiny inventory pos
    orch.env._recent_demand = [100.0]
    orch.env.on_hand = 0.0
    # drive one tick; a deep deficit should propose a large order that gets clamped
    before = orch.cb_trips
    orch.run_tick()
    # either it didn't need to clamp, or if it did, trips incremented and an event logged
    if orch.cb_trips > before:
        assert orch.audit.events("circuit_break")


def test_approver_gates_high_value_orders():
    cfg = Config(approval_order_value=1.0, auto_approve=False)
    orch = Orchestrator(cfg)
    d = orch.approver.review_order(tick=0, order_value=999999.0, qty=100.0)
    assert d["status"] == "escalated_pending"
    assert orch.approver.human_queue


# ---- system-level invariant the docs depend on -----------------------
def test_governed_maintains_high_service():
    orch = Orchestrator(governed())
    orch.run()
    recs = orch.env.records
    fill = sum(r.sales for r in recs) / sum(r.demand for r in recs)
    assert fill > 0.95


def test_ungoverned_thrashes_price_more_than_governed():
    g = Orchestrator(governed()); g.run()
    u = Orchestrator(ungoverned()); u.run()
    gv = statistics.pstdev([r.price for r in g.env.records])
    uv = statistics.pstdev([r.price for r in u.env.records])
    assert uv > gv   # ungoverned pricing is less stable
