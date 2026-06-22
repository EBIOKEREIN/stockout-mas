"""Single source of truth for simulation parameters and guardrail toggles.

The two headline scenarios differ ONLY in the guardrail flags here, so the
failure demo is a controlled experiment, not a different codebase.
"""
from __future__ import annotations

from pydantic import BaseModel


class Config(BaseModel):
    # --- horizon / RNG ---
    horizon: int = 60
    seed: int = 7

    # --- demand process (single SKU) ---
    base_demand: float = 100.0        # units / tick at reference price
    demand_noise_cv: float = 0.15     # coefficient of variation of demand
    ref_price: float = 20.0
    elasticity: float = 1.4           # demand ~ (price/ref)^(-elasticity)

    # --- demand spike scenario ---
    spike_start: int = 20
    spike_len: int = 8
    spike_mult: float = 2.5           # demand multiplier during the spike

    # --- economics ---
    sell_price: float = 20.0          # starting price (pricing agent may move it)
    holding_cost: float = 0.5         # $ / unit / tick
    stockout_penalty: float = 5.0     # $ / unit of unmet demand
    order_fixed_cost: float = 100.0   # $ / purchase order

    # --- inventory policy (base-stock with safety stock) ---
    review_period: int = 1
    service_z: float = 1.95           # ~97.5% cycle service level
    init_on_hand: float = 360.0

    # --- expediting / rush-order economics ---
    expedite_band: float = 1.6        # orders above 1.6x recent demand incur a premium
    expedite_rate: float = 4.0        # $ per unit of "rush" volume above the band

    # --- guardrails (the only thing scenarios toggle) ---
    order_smoothing: bool = True      # damp order swings -> tames bullwhip
    smoothing_alpha: float = 0.45     # fraction of the gap closed per order
    max_order_qty: float = 1200.0     # hard clamp on a single PO
    pricing_respects_stock: bool = True   # pricing may not mark down when stock is at risk
    circuit_breaker: bool = True      # clamp runaway orders + escalate on instability

    # --- circuit breaker thresholds ---
    bullwhip_window: int = 8
    bullwhip_trip_ratio: float = 3.0  # rolling Var(order)/Var(demand) trip level
    cb_order_mult: float = 3.5        # an order above this x recent demand is "runaway" -> clamp
    projected_stockout_trip: float = 0.6  # projected fill-rate floor before tripping

    # --- HITL approval thresholds ---
    approval_order_value: float = 15000.0   # POs above this need human approval
    approval_price_pct: float = 0.15        # price moves beyond +/-15% need approval
    auto_approve: bool = True               # mock human auto-approves within policy
    human_latency_ticks: int = 1            # simulated approval latency

    # --- suppliers (contract-net responders) ---
    # name: (unit_cost, lead_time, capacity_per_order, reliability)
    suppliers: dict[str, tuple] = {
        "supplier_A": (12.0, 2, 800.0, 0.98),   # cheap, slow, capacity-limited
        "supplier_B": (14.5, 1, 1500.0, 0.95),  # pricey, fast, high capacity
        "supplier_C": (13.0, 3, 1200.0, 0.90),  # mid cost, slow, less reliable
    }
    # award scoring weights (lower score = better)
    w_cost: float = 1.0
    w_lead: float = 250.0             # $ value placed on each tick of lead time
    w_reliability: float = 4000.0     # penalty weight on (1 - reliability)
