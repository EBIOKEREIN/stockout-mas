"""Evaluation metrics at four levels: agent, interaction, system, human.

These map directly onto the assignment's required evaluation tiers.
"""
from __future__ import annotations

import statistics

from ..orchestrator import Orchestrator


def compute_metrics(orch: Orchestrator) -> dict:
    recs = orch.env.records
    demand = [r.demand for r in recs]
    sales = [r.sales for r in recs]
    orders = [r.order_qty for r in recs]
    prices = [r.price for r in recs]

    total_demand = sum(demand) or 1.0
    total_sales = sum(sales)
    fill_rate = total_sales / total_demand

    holding = sum(r.holding_cost for r in recs)
    stockout = sum(r.stockout_cost for r in recs)
    ordering = sum(r.order_cost for r in recs)
    cogs = sum(r.cogs for r in recs)
    revenue = sum(r.revenue for r in recs)
    profit = revenue - holding - stockout - ordering - cogs

    # agent level: forecast accuracy (MAPE) and price stability
    fc_hist = orch.bb.history("forecast")
    mape_terms = []
    for (t, fc), r in zip(fc_hist, recs):
        if r.demand > 0:
            mape_terms.append(abs(fc["mean_per_tick"] - r.demand) / r.demand)
    forecast_mape = statistics.mean(mape_terms) if mape_terms else None

    # interaction level: bullwhip + comms volume
    var_d = statistics.pvariance(demand) if len(demand) > 1 else 0.0
    var_o = statistics.pvariance(orders) if len(orders) > 1 else 0.0
    bullwhip = (var_o / var_d) if var_d > 0 else 0.0

    return {
        "system": {
            "fill_rate": round(fill_rate, 4),
            "stockout_ticks": sum(1 for r in recs if r.lost_sales > 0.5),
            "units_lost": round(sum(r.lost_sales for r in recs), 1),
            "profit": round(profit, 0),
            "revenue": round(revenue, 0),
            "holding_cost": round(holding, 0),
            "stockout_cost": round(stockout, 0),
        },
        "interaction": {
            "bullwhip_ratio": round(bullwhip, 3),
            "messages_total": len(orch.audit.messages),
            "messages_per_tick": round(len(orch.audit.messages) / max(1, len(recs)), 1),
            "contract_net_rounds": len(orch.audit.events("no_bids")) + sum(
                1 for m in orch.audit.messages if m.msg_type.value == "AWARD"),
            "circuit_breaks": orch.cb_trips,
            "rollbacks": orch.rollbacks,
        },
        "agent": {
            "forecast_mape": round(forecast_mape, 4) if forecast_mape is not None else None,
            "avg_order_qty": round(statistics.mean(orders), 1),
            "order_qty_stdev": round(statistics.pstdev(orders), 1),
            "price_volatility": round(statistics.pstdev(prices), 3),
        },
        "human": {
            "approval_decisions": len(orch.approver.decisions),
            "auto_approved": sum(1 for d in orch.approver.decisions if d["status"] == "auto_approved"),
            "approved_with_latency": sum(1 for d in orch.approver.decisions if d["status"] == "approved_with_latency"),
            "escalations_pending": sum(1 for q in orch.approver.human_queue if not q.get("cleared", True)),
            "human_queue_len": len(orch.approver.human_queue),
        },
    }


def print_metrics(name: str, m: dict) -> None:
    print(f"\n=== {name} ===")
    for level in ("system", "interaction", "agent", "human"):
        print(f"  [{level}]")
        for k, v in m[level].items():
            print(f"    {k:<22} {v}")
