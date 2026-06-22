# Agent Roster

Each agent has one clear responsibility. I kept the roles narrow because it makes the system easier to explain, test, and audit. Agents do not directly mutate the environment. They send messages or write to shared state, and the orchestrator commits actions after routing, approval, and governance checks.

This is also a least-privilege design: an agent only gets the information and permissions it needs for its job.

| Agent | Count | Local objective | Reads | Writes / emits | Scopes |
|---|---:|---|---|---|---|
| **Demand** | 1 | Produce a useful short-term forecast | realized demand | `FORECAST` with mean, sigma, horizon | `read:sales`, `write:forecast` |
| **Inventory** | 1 | Maintain service level without over-ordering | forecast, inventory position | `REPLENISH_REQUEST` | `read:forecast`, `read:inventory`, `write:replenish_request` |
| **Supplier** | 3 | Win feasible profitable orders | `CFP` | `BID` or decline | `read:cfp`, `write:bid` |
| **Pricing** | 1 | Improve revenue and clear excess stock | inventory, stock-health | `PRICE_UPDATE` | `read:inventory`, `read:stock_health`, `write:price` |
| **Approver / HITL** | 1 | Enforce policy on risky actions | `APPROVAL_REQUEST` | `APPROVAL_RESPONSE`, human queue item | `read:approval_request`, `write:approval_response`, `write:human_queue` |
| **Orchestrator** | 1 | Sequence, route, audit, and govern the run | all routed messages and state needed for governance | `CFP`, `AWARD`, `CIRCUIT_BREAK`, `ROLLBACK` | routing + governance |

## Demand agent

The demand agent uses exponential smoothing with `α = 0.35`. It observes realized demand and emits a short-term forecast with an estimated error band. The inventory agent uses that error band to size safety stock.

I kept this agent simple on purpose. A perfect forecast would make the rest of the system look better than it is. In the spike scenario, the forecast is useful but imperfect, so the other agents have to cope with real forecast error.

## Inventory agent

The inventory agent uses a base-stock policy. It calculates an order-up-to target:

```text
S = μ·(L+R) + z·σ·√(L+R)
```

where `μ` is forecast demand, `σ` is forecast error, `L` is lead time, `R` is review period, and `z` is the service-level buffer.

The important design choice is smoothing. Instead of chasing the full gap to the target every tick, the agent closes only a fraction of the gap. That prevents forecast jumps from turning into huge order jumps. When smoothing is turned off, the bullwhip effect becomes visible.

The inventory agent also exposes a `policy_fn` hook. A learned replenishment policy could be plugged in there later without changing the rest of the system.

## Supplier agents

The supplier agents are the contract-net responders. Each supplier has a different unit cost, lead time, capacity, and reliability. When the orchestrator sends a `CFP`, a supplier either returns a bid or declines.

The suppliers are intentionally not identical:

- Supplier A is cheaper but slower and more capacity-limited.
- Supplier B is faster and larger but more expensive.
- Supplier C sits in the middle and is less reliable.

That makes supplier choice a real tradeoff instead of a lookup table.

## Pricing agent

The pricing agent is where the main incentive conflict appears.

In the governed scenario, pricing reads the stock-health signal before changing price. If inventory is low, it avoids marking down because a discount would create more demand when stock is already scarce.

In the ungoverned scenario, pricing ignores stock-health and reacts mainly to recent sales. During a shortage, sales can look weak simply because there is nothing available to sell. The ungoverned pricing agent can misread that as weak demand and cut price, which makes the shortage worse.

## Approver / HITL agent

The approver represents a human policy gate. It checks two types of actions:

- purchase orders above the value threshold,
- price moves beyond the allowed percentage band.

Actions inside policy are auto-approved with simulated latency. Actions outside policy are escalated to a human queue. The other agents cannot clear that queue themselves, which keeps the human control point separate from the local optimization decisions.

## Orchestrator

The orchestrator is the supervisor. It owns the tick sequence, routes messages, runs the supplier auction, applies the circuit breaker, performs rollback when needed, and writes the audit log.

This agent is not trying to be the “smartest” worker. Its job is control, sequencing, and accountability.
