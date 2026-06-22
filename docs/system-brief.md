# System Brief

## Problem

This prototype models a retailer selling one product during unstable demand. A promotion, viral moment, or sudden market change can lift demand for several ticks and then fade. The retailer has to decide how much to order, which supplier to use, and whether to adjust price while the shock is happening.

The problem is tricky because the levers interact. A price cut can increase demand, but that is dangerous when inventory is already low. A large replenishment order can protect service, but it can also create expensive and unstable ordering behaviour. A cheap supplier can save money, but a slower lead time can hurt service during a spike.

The operational question is:

> How can the system keep the shelf stocked during a demand shock without creating wild supplier orders, pricing into a shortage, or letting an automated loop commit a risky action without human oversight?

## Stakeholders

| Stakeholder | What they care about |
|---|---|
| Store / retailer | high fill rate, stable profit, fewer lost sales |
| Customer | product available when demand spikes |
| Inventory team | enough stock without over-ordering |
| Pricing team | revenue and margin |
| Suppliers | profitable, feasible orders with realistic lead times |
| Human approver | control over expensive or risky actions |

## Why this is a multi-agent system

I separated the system into agents because the real decision is not owned by one actor.

- **Forecasting** looks at demand history and estimates the near future.
- **Inventory** converts the forecast and current stock into an order request.
- **Suppliers** have their own capacity, lead time, reliability, and cost.
- **Pricing** changes demand by moving price.
- **Approval** is a human-accountable gate for risky actions.

A single model could output all the numbers, but that would hide the conflicts I want to study. In a real organization, the supplier is not controlled by the retailer, the pricing function does not naturally own service-level risk, and a human approval gate should not be inside the same optimization loop it is meant to supervise.

Keeping the roles separate lets the prototype show the coordination problem directly: agents can make reasonable local decisions that combine into a bad system outcome.

## What the prototype does

The project runs a 60-tick simulation with six agent types:

1. Demand agent forecasts demand.
2. Inventory agent requests replenishment.
3. Three supplier agents bid or decline.
4. Pricing agent proposes price moves.
5. Approver agent gates high-risk actions.
6. Orchestrator sequences the run, routes messages, runs the auction, applies governance, and logs decisions.

The prototype includes:

- a typed communication contract,
- a supervisor + blackboard + contract-net coordination design,
- a supplier auction,
- governed and ungoverned scenarios,
- a circuit breaker and rollback,
- a human-in-the-loop approval gate,
- charts showing bullwhip and price/inventory behaviour,
- a four-level evaluation harness,
- a 200-seed stress test.

## Failure stakes

This is not a life-critical system, but the failures still matter.

A bad run can:

- lose sales because inventory is not available,
- create supplier whiplash through unstable order quantities,
- cut prices at exactly the wrong time,
- spend too much on urgent replenishment,
- produce recommendations that a human cannot audit after the fact.

That is why the prototype treats audit, approval, rollback, and circuit breaking as core pieces of the system rather than optional extras.

## Headline result

The governed version does not magically maximize every metric on every single run. On one seed, the average profit difference is not dramatic. The stronger result appears in stability and downside protection.

Across 200 random demand draws, the governed system has a higher fill-rate floor and a higher profit floor:

| Metric | Governed | Ungoverned |
|---|---:|---:|
| Fill mean | 98.98% | 97.75% |
| Fill minimum | 95.51% | 93.40% |
| Profit mean | 18,427 | 17,859 |
| Profit minimum | 14,278 | 11,204 |

The honest interpretation is that the base supply chain is deliberately well-buffered, so the ungoverned case does not collapse completely. The guardrails still reduce volatility and protect the tail. In a tighter supply-constrained setting, the same pricing and ordering failures would likely become much more severe.
