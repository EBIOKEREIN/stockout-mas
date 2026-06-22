"""Monte-Carlo stress test.

A single seed can flatter a fragile design. The argument for governance is a
TAIL argument: across many demand draws, the ungoverned system occasionally
falls into a stockout death-spiral (pricing marks down into a shortage, no
breaker to catch the runaway), while the governed system stays bounded.

    python -m stockout_mas.eval.stress --runs 200
"""
from __future__ import annotations

import argparse
import statistics

from ..config import Config
from ..orchestrator import Orchestrator
from ..sim.scenarios import governed, ungoverned


def _percentile(xs: list[float], p: float) -> float:
    s = sorted(xs)
    k = max(0, min(len(s) - 1, int(round((p / 100) * (len(s) - 1)))))
    return s[k]


def sweep(make_cfg, runs: int, base_seed: int = 1000) -> dict:
    fills, profits = [], []
    worst_fill = 1.0
    for i in range(runs):
        cfg = make_cfg()
        cfg.seed = base_seed + i
        orch = Orchestrator(cfg)
        orch.run()
        recs = orch.env.records
        td = sum(r.demand for r in recs) or 1.0
        fr = sum(r.sales for r in recs) / td
        profit = sum(r.revenue - r.holding_cost - r.stockout_cost
                     - r.order_cost - r.cogs for r in recs)
        fills.append(fr)
        profits.append(profit)
        worst_fill = min(worst_fill, fr)
    return {
        "runs": runs,
        "fill_mean": round(statistics.mean(fills), 4),
        "fill_p05": round(_percentile(fills, 5), 4),
        "fill_min": round(min(fills), 4),
        "profit_mean": round(statistics.mean(profits), 0),
        "profit_p05": round(_percentile(profits, 5), 0),
        "profit_min": round(min(profits), 0),
        "catastrophes": sum(1 for f in fills if f < 0.85),   # runs below 85% fill
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=200)
    args = ap.parse_args()

    g = sweep(governed, args.runs)
    u = sweep(ungoverned, args.runs)

    print(f"\nMonte-Carlo stress test  ({args.runs} seeds each)\n")
    cols = ["fill_mean", "fill_p05", "fill_min", "profit_mean",
            "profit_p05", "profit_min", "catastrophes"]
    print("metric".ljust(16) + "governed".ljust(16) + "ungoverned".ljust(16))
    print("-" * 48)
    for c in cols:
        print(c.ljust(16) + str(g[c]).ljust(16) + str(u[c]).ljust(16))
    print(f"\ncatastrophe = run with fill rate < 85%")


if __name__ == "__main__":
    main()
