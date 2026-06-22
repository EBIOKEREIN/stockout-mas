"""Scenarios are Config variants. The governed/ungoverned pair differs ONLY in
guardrail flags, so any behavioural gap is attributable to coordination design,
not to a different model.
"""
from __future__ import annotations

from ..config import Config


def governed() -> Config:
    """All guardrails on. The system we'd actually ship behind a human."""
    return Config()


def ungoverned() -> Config:
    """Guardrails off: no order smoothing, pricing ignores stock, no breaker.
    Demonstrates bullwhip + the pricing-vs-inventory conflict."""
    return Config(
        order_smoothing=False,
        pricing_respects_stock=False,
        circuit_breaker=False,
    )


def no_smoothing() -> Config:
    """Smoothing OFF, but pricing-respect + breaker ON. Isolates the breaker:
    it must catch the order blowups that smoothing would otherwise prevent."""
    return Config(order_smoothing=False)


def supplier_outage() -> Config:
    """Most reliable/fast supplier is knocked out -> contract-net must reroute."""
    cfg = Config()
    s = dict(cfg.suppliers)
    s["supplier_B"] = (14.5, 1, 1500.0, 0.05)  # near-total outage
    cfg.suppliers = s
    return cfg


SCENARIOS = {
    "governed": governed,
    "no_smoothing": no_smoothing,
    "ungoverned": ungoverned,
    "supplier_outage": supplier_outage,
}
