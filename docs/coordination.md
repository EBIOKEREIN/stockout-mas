# Coordination

## Design choice

The system uses a hybrid coordination mechanism:

| Pattern | Used for | Why |
|---|---|---|
| **Supervisor / orchestrator** | tick loop, routing, governance, audit | gives the system one clear control point |
| **Contract-net** | supplier allocation | suppliers are independent and can bid, decline, or be unavailable |
| **Blackboard** | shared forecast, stock position, price, and stock-health | lets agents share state without direct dependencies |

I chose this hybrid because the supply-chain problem has three different coordination needs: sequencing, negotiation, and shared state. No single pattern handles all three cleanly.

## Why not one agent?

A single agent could produce a forecast, an order quantity, a supplier choice, and a price. That would be simpler to code, but it would not represent the actual problem well.

Three boundaries need to stay visible:

1. **Supplier boundary.** Suppliers are outside parties. They have their own costs, capacity, lead times, and reliability. The buyer should ask for bids and handle declines instead of assuming a supplier is just a function call.
2. **Pricing and inventory boundary.** Pricing and inventory can rationally disagree. Pricing wants revenue and stock movement; inventory wants service and stability. Keeping them separate makes the conflict observable.
3. **Human approval boundary.** Approval should not be controlled by the same logic that creates risky actions. The approver must be able to slow, reject, or escalate the system.

The single-agent inventory RL controller from `EBIOKEREIN/inventory-rl` is still relevant, but only as a replenishment sub-policy. It could plug into the inventory agent through `policy_fn`. It does not replace the coordination layer.

## Why not pure contract-net?

If every decision were negotiated through contract-net, the system would lose a reliable tick order. Pricing and ordering could race. The stock-health signal might be stale. There would also be no obvious place to put the circuit breaker or rollback.

In practice, I would end up rebuilding a supervisor to fix those problems. So the supervisor is explicit from the start.

## Why not pure blackboard?

A pure blackboard design lets agents react whenever state changes. That is useful for loose coupling, but it is risky here because ordering matters. If pricing reacts before stock-health is updated, or inventory reacts to stale forecasts, the agents can amplify each other's mistakes.

So I use the blackboard for shared memory, not for full control.

## How the supplier auction works

The orchestrator sends a `CFP` with the requested quantity. Suppliers respond with bids or decline. The orchestrator scores each valid bid with:

```text
score = w_cost·unit_cost + w_lead·lead_time + w_reliability·(1 − reliability)
```

The current weights are:

```text
w_cost = 1
w_lead = 250
w_reliability = 4000
```

These weights mean the system values shorter lead time and reliability, not just the lowest unit cost. This matters during a demand shock because cheap inventory that arrives too late is not actually useful.

In the supplier-outage scenario, the usual faster supplier is knocked out, so the auction reroutes to other suppliers. Service falls because the fallback supply is slower, which is exactly the tradeoff the auction is meant to expose.

## Emergence the coordination design reveals

### Bullwhip

When the inventory agent reacts too aggressively to forecast changes, small demand changes become large order changes. In the ungoverned run, order quantities become jagged and overshoot. In the governed run, smoothing and the breaker reduce that behaviour.

### Pricing-vs-inventory conflict

The pricing agent can make a locally reasonable move that is globally harmful. If it sees sales falling and cuts price during a shortage, it creates extra demand when the shelf is already empty. The governed design prevents this by letting pricing read stock-health from the blackboard.

The point of the coordination design is not to make agents agree all the time. It is to make disagreement visible, route it through a clear process, and stop the most harmful actions before they are committed.
