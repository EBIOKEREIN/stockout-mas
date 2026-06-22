"""Compare scenarios side by side and (optionally) render charts.

    python -m stockout_mas.eval.run_eval
    python -m stockout_mas.eval.run_eval --no-plots
"""
from __future__ import annotations

import argparse
import json
import os

from ..orchestrator import Orchestrator
from ..sim.scenarios import SCENARIOS
from .metrics import compute_metrics

OUT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "outputs")
OUT = os.path.abspath(OUT)


def run_all() -> dict:
    results = {}
    for name, factory in SCENARIOS.items():
        orch = Orchestrator(factory())
        orch.run()
        results[name] = {"metrics": compute_metrics(orch), "orch": orch}
    return results


def comparison_table(results: dict) -> str:
    rows = [
        ("fill_rate", lambda m: f"{m['system']['fill_rate']*100:.1f}%"),
        ("units_lost", lambda m: f"{m['system']['units_lost']:.0f}"),
        ("profit ($)", lambda m: f"{m['system']['profit']:,.0f}"),
        ("bullwhip_ratio", lambda m: f"{m['interaction']['bullwhip_ratio']:.2f}"),
        ("order_qty_stdev", lambda m: f"{m['agent']['order_qty_stdev']:.0f}"),
        ("price_volatility", lambda m: f"{m['agent']['price_volatility']:.2f}"),
        ("circuit_breaks", lambda m: f"{m['interaction']['circuit_breaks']}"),
        ("escalations", lambda m: f"{m['human']['escalations_pending']}"),
    ]
    names = list(results)
    w = 18
    head = "metric".ljust(20) + "".join(n.ljust(w) for n in names)
    lines = [head, "-" * len(head)]
    for label, fn in rows:
        line = label.ljust(20) + "".join(fn(results[n]["metrics"]).ljust(w) for n in names)
        lines.append(line)
    return "\n".join(lines)


def make_plots(results: dict) -> list[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return []
    os.makedirs(OUT, exist_ok=True)
    paths = []

    # 1. orders vs demand for governed vs ungoverned (bullwhip visual)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
    for ax, scen in zip(axes, ["governed", "ungoverned"]):
        recs = results[scen]["orch"].env.records
        ax.plot([r.demand for r in recs], label="demand", color="#1f3b57", lw=1.6)
        ax.plot([r.order_qty for r in recs], label="orders", color="#e8743b", lw=1.6)
        ax.set_title(f"{scen}: orders vs demand")
        ax.set_xlabel("tick"); ax.legend(); ax.grid(alpha=0.25)
    axes[0].set_ylabel("units")
    fig.tight_layout()
    p1 = os.path.join(OUT, "bullwhip_orders_vs_demand.png")
    fig.savefig(p1, dpi=110); plt.close(fig); paths.append(p1)

    # 2. on-hand inventory + price (governed vs ungoverned)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
    for ax, scen in zip(axes, ["governed", "ungoverned"]):
        recs = results[scen]["orch"].env.records
        ax.plot([r.on_hand_end for r in recs], label="on-hand", color="#1f3b57", lw=1.6)
        ax.axhline(0, color="#b00", lw=0.8, ls="--")
        ax2 = ax.twinx()
        ax2.plot([r.price for r in recs], label="price", color="#2a9d8f", lw=1.2, alpha=0.8)
        ax2.set_ylabel("price ($)")
        ax.set_title(f"{scen}: inventory & price"); ax.set_xlabel("tick"); ax.grid(alpha=0.25)
    axes[0].set_ylabel("on-hand units")
    fig.tight_layout()
    p2 = os.path.join(OUT, "inventory_and_price.png")
    fig.savefig(p2, dpi=110); plt.close(fig); paths.append(p2)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args()

    results = run_all()
    table = comparison_table(results)
    print("\n" + table + "\n")

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "metrics.json"), "w") as f:
        json.dump({n: r["metrics"] for n, r in results.items()}, f, indent=2)
    print(f"metrics -> {os.path.join(OUT, 'metrics.json')}")

    if not args.no_plots:
        for p in make_plots(results):
            print(f"chart   -> {p}")


if __name__ == "__main__":
    main()
