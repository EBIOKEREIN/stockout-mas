# Evaluation

The evaluation is designed around how the system can fail. An individual agent can be inaccurate, agents can interact badly, the system can lose service or profit, and the human approval burden can become too high.

All reported numbers are reproducible from the code:

```bash
PYTHONPATH=src python -m stockout_mas.eval.run_eval
PYTHONPATH=src python -m stockout_mas.eval.stress --runs 200
```

The single-scenario tables use `seed=7`. The stress test uses 200 seeds.

## Metric levels

| Level | Metrics | Why it matters |
|---|---|---|
| Agent | forecast MAPE, order mean/standard deviation, price volatility | shows whether each agent is behaving reasonably |
| Interaction | bullwhip ratio, message volume, contract-net rounds, circuit-breaks, rollbacks | shows whether coordination is stable |
| System | fill rate, lost units, profit and cost components | shows business outcome |
| Human | approvals, auto-approvals, escalations pending | shows whether oversight is manageable |

## Scenarios

The scenarios form an ablation ladder. Each one removes or stresses a part of the governed design.

| Scenario | Smoothing | Pricing respects stock | Breaker | Purpose |
|---|---|---|---|---|
| `governed` | yes | yes | yes | full controlled system |
| `no_smoothing` | no | yes | yes | tests whether the breaker catches what smoothing would have prevented |
| `ungoverned` | no | no | no | baseline for harmful local interactions |
| `supplier_outage` | yes | yes | yes | tests resilience when the usual supplier is unavailable |

## Single-seed results

| metric | governed | no_smoothing | ungoverned | supplier_outage |
|---|---:|---:|---:|---:|
| fill rate | **99.0%** | 97.3% | 97.7% | 95.5% |
| units lost | **79** | 197 | 185 | 341 |
| profit ($) | 19,219 | 24,182 | 19,193 | 35,722 |
| bullwhip ratio | 2.49 | 2.48 | 2.63 | 1.94 |
| order σ | **85** | 88 | 94 | 75 |
| price volatility | 0.73 | 0.58 | **0.88** | 0.73 |
| circuit-breaks | 0 | 1 | 0 | 0 |

This single seed should not be overclaimed. The governed system does not dominate every profit number in this one run. `no_smoothing` has higher profit because it holds less inventory and the breaker catches its one runaway order.

The governed system's advantage is clearer in stability: highest fill rate, lowest order volatility, and a controlled price path. That is why I also run a stress test.

## Stress test: 200 random demand draws

| metric | governed | ungoverned |
|---|---:|---:|
| fill mean | **98.98%** | 97.75% |
| fill p05 | **96.86%** | 95.62% |
| fill min | **95.51%** | 93.40% |
| profit mean | **18,427** | 17,859 |
| profit p05 | **16,142** | 14,719 |
| profit min | **14,278** | 11,204 |
| catastrophes below 85% fill | 0 | 0 |

Across 200 seeds, the governed system has better mean performance and a better tail. The most important numbers are the minimums: the governed worst case is materially better than the ungoverned worst case.

That is the practical value of governance here. It does not just improve the average; it reduces the damage when the run is unlucky.

## Reading the charts

`outputs/bullwhip_orders_vs_demand.png` compares demand with order quantities. In the ungoverned run, order quantities swing harder than demand. In the governed run, orders stay smoother.

`outputs/inventory_and_price.png` compares inventory and price. The ungoverned price moves in a sawtooth pattern because pricing keeps reacting to weak sales without respecting stock-health. The governed price path is more stable.

## Limitations

- **Well-buffered chain.** The simulated retailer has enough starting stock and supplier capacity that the ungoverned run degrades rather than collapses. A tighter supply scenario would likely make the ungoverned tail worse.
- **Single SKU.** The model only has one product. Multi-SKU competition for shared suppliers would create harder coordination problems.
- **Mock human.** Approval latency and escalation are simulated. Real humans can get tired, rubber-stamp decisions, or miss context.
- **Simple policies.** The agents use explicit analytic rules, not learned policies. This is a deliberate choice for auditability, but it limits adaptiveness.
- **Local deployment only.** The prototype does not implement production-grade identity, authentication, or tamper-evident logging.

## What I would test next

The next useful experiments would be:

1. reduce supplier capacity and increase lead times to create a harsher tail-risk regime;
2. add multiple SKUs competing for the same supplier capacity;
3. test different approval thresholds to find when human workload becomes too high;
4. plug a learned replenishment policy into `policy_fn` and compare it against the analytic inventory rule.
