# Communication Contract

Every interaction uses the same typed `Message` envelope from `messages.py`. I used one message format because it makes routing, logging, testing, and later interoperability much easier.

Agents do not call each other directly. They send messages through the orchestrator and use the blackboard for shared state. That means every important action can be traced through a message or a governance event.

## Message envelope

| Field | Meaning |
|---|---|
| `msg_id` | unique message id |
| `tick` | logical simulation time |
| `sender` | agent or component that created the message |
| `recipients` | one or more recipients; `['*']` means broadcast |
| `msg_type` | message category such as `FORECAST`, `BID`, or `AWARD` |
| `performative` | intent of the message: `inform`, `request`, `propose`, `accept`, `reject`, `escalate` |
| `conversation_id` | groups a full negotiation or decision thread |
| `correlation_id` | points to the message being answered |
| `payload` | typed body of the message |
| `wall_clock` | timestamp used for auditability |

`conversation_id` and `correlation_id` matter most during supplier negotiation. If a supplier wins an order, the system can reconstruct the original `CFP`, all received bids, declined bids, and the final award.

## Message types

| `msg_type` | Typical performative | From → To | Payload |
|---|---|---|---|
| `FORECAST` | inform | demand → blackboard / orchestrator | `mean_per_tick`, `sigma`, `horizon` |
| `STATE_UPDATE` | inform | environment → blackboard | inventory, arrivals, demand, cost fields |
| `REPLENISH_REQUEST` | request | inventory → orchestrator | `order_qty`, `target`, `raw_gap` |
| `CFP` | request | orchestrator → suppliers | requested quantity |
| `BID` | propose | supplier → orchestrator | unit cost, lead time, quantity, reliability |
| `AWARD` | accept | orchestrator → winning supplier | winning bid details |
| `NO_AWARD` | reject | orchestrator → losing suppliers | reason |
| `PRICE_UPDATE` | inform | pricing → orchestrator / environment | proposed price and approval status |
| `APPROVAL_REQUEST` | request | orchestrator → approver | action type and value |
| `APPROVAL_RESPONSE` | accept / reject / escalate | approver → orchestrator | approval status |
| `CIRCUIT_BREAK` | escalate | orchestrator → audit / human queue | reason and before/after action |
| `ROLLBACK` | inform | orchestrator → environment | reverted fields |

## Worked exchange

This is a simplified transcript from the governed scenario at tick 0:

```text
[t00]     demand -> *            FORECAST         {mean_per_tick: 100.0, sigma: 15.0}
[t00]    pricing -> environment  PRICE_UPDATE     {price: 20.0, approval: auto_approved}
[t00]  inventory -> orchestrator REPLENISH_REQUEST {order_qty: 95.8}
[t00] orchestrator -> *          CFP              {qty: 95.8}
[t00] supplier_A -> orchestrator BID              {unit_cost: 12.0, lead_time: 2, qty: 95.8, reliability: 0.98}
[t00] supplier_B -> orchestrator BID              {declined: true}
[t00] supplier_C -> orchestrator BID              {unit_cost: 13.0, lead_time: 3, qty: 95.8, reliability: 0.90}
[t00] orchestrator -> supplier_A AWARD            {supplier: supplier_A, ...}
[t00] orchestrator -> supplier_C NO_AWARD         {reason: outbid}
```

Supplier B is unavailable in this tick, so the system awards to another supplier instead of failing. That is one reason contract-net is useful here: supplier failure becomes part of the negotiation rather than an exception path.

Regenerate a transcript with:

```bash
PYTHONPATH=src python -m stockout_mas.run --scenario governed --transcript 2
```

## Routing and escalation

The orchestrator routes every message. It also decides when a proposed action needs an approval request or a circuit-break check.

| Trigger | What happens |
|---|---|
| order value above threshold | send `APPROVAL_REQUEST` |
| price move outside allowed band | send `APPROVAL_REQUEST` |
| order far above recent demand | emit `CIRCUIT_BREAK`, clamp order, escalate |
| price move worsens a shortage | governed pricing blocks the move through stock-health logic |
| no supplier bids | no award; system records the failure and continues |

## Interoperability boundary

The prototype is local, but the boundaries are placed where real interoperability would matter.

- **A2A-style boundary:** suppliers are independent agents. The `CFP → BID → AWARD` flow is the natural place for agent-to-agent communication.
- **MCP-style boundary:** the environment and blackboard are tool/data boundaries. An agent should only access the tools and resources it has scopes for, such as reading inventory or proposing a price.

I did not implement those protocols directly because the assignment is about a working prototype, not deployment infrastructure. The important part is that the message contract and permissions are already shaped around those boundaries.
