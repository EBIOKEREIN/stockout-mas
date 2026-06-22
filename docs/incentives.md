# Incentives

## Global objective

The system-level objective is profit under a service constraint:

```text
profit = revenue − holding cost − stockout penalty − ordering / expedite cost − COGS
```

The business wants strong profit, but not by sacrificing availability. A supply-chain run that makes money on average but leaves the shelf empty during spikes is not good enough.

## Local objectives

No individual agent optimizes the full system objective. That is intentional. In the real setting, each role sees a different part of the problem.

| Agent | Local objective | Where it can conflict with the system |
|---|---|---|
| Demand | reduce forecast error | biased forecasts mis-size safety stock downstream |
| Inventory | hit service target with low holding cost | aggressive correction can create bullwhip and expedite costs |
| Supplier | win profitable feasible orders | may charge more, decline, or capacity-limit the order |
| Pricing | increase revenue and clear stock | may cut price during shortage and create more lost sales |
| Approver | enforce policy | slows execution, but protects against bad automated actions |

## The main conflict

The pricing conflict is the clearest example.

During a stockout, observed sales may fall because the product is not available. An ungoverned pricing agent can misread that as weak demand and cut price. The price cut increases demand, but inventory is still low, so the system loses more sales.

The pricing agent's local move makes sense from its narrow view. The system outcome is bad because the cost shows up elsewhere: in lost sales, poor service, and pressure on replenishment.

That is the externality the prototype is designed to show.

## How the governed system corrects incentives

I did not solve the problem by giving every agent one blended reward. That would hide the conflict. Instead, the governed design adds structural checks.

### 1. Shared stock-health signal

The blackboard publishes `stock_health` on a 0-to-1 scale. Pricing is allowed to react to demand, but it cannot mark down when stock-health is too low. This makes the inventory situation visible to the agent that can worsen it.

### 2. Order smoothing and expedite cost

The inventory agent smooths its orders instead of closing the full gap to target every tick. The environment also charges an expedite surcharge when orders run far above recent demand. Together, these make violent order swings more costly and less attractive.

### 3. Human approval

Large purchase orders and large price moves go through the approver. This protects the system when an action is financially large or outside policy.

### 4. Circuit breaker

If an order is far above recent realized demand, the orchestrator clamps it and escalates. This is the final backstop when normal incentives and smoothing are not enough.

## Why not use one global reward?

A single global reward would make the system look cleaner, but it would remove the behaviour I need to study.

I kept local objectives because:

- the pricing-vs-inventory conflict should be visible, not hidden;
- suppliers really are independent actors, not internal functions;
- a human approval gate should not be collapsed into an optimization objective;
- explicit rules like “do not mark down when stock-health is low” are easier to audit than reward weights.

The evaluation results show the effect of these corrections: the governed run has lower order volatility, a more disciplined price path, and a stronger service/profit floor across 200 seeds.
