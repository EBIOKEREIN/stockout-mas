"""Run one scenario and print an annotated transcript + metrics.

    python -m stockout_mas.run --scenario governed
    python -m stockout_mas.run --scenario ungoverned --transcript 24
"""
from __future__ import annotations

import argparse

from .orchestrator import Orchestrator
from .sim.scenarios import SCENARIOS
from .eval.metrics import compute_metrics, print_metrics


def main() -> None:
    ap = argparse.ArgumentParser(description="stockout-MAS runner")
    ap.add_argument("--scenario", choices=list(SCENARIOS), default="governed")
    ap.add_argument("--transcript", type=int, default=0,
                    help="print the message transcript up to this tick (0 = none)")
    ap.add_argument("--audit", default=None, help="path to write JSONL audit log")
    args = ap.parse_args()

    cfg = SCENARIOS[args.scenario]()
    orch = Orchestrator(cfg, audit_path=args.audit)
    orch.run()

    if args.transcript:
        print(f"\n--- message transcript (ticks 0..{args.transcript - 1}) ---")
        for m in orch.audit.messages:
            if m.tick < args.transcript:
                print(m.short())

    m = compute_metrics(orch)
    print_metrics(args.scenario, m)

    # plain-language headline
    s = m["system"]
    print(f"\nHeadline: fill rate {s['fill_rate']*100:.1f}%  |  "
          f"profit ${s['profit']:,.0f}  |  "
          f"bullwhip {m['interaction']['bullwhip_ratio']}  |  "
          f"circuit-breaks {m['interaction']['circuit_breaks']}")


if __name__ == "__main__":
    main()
