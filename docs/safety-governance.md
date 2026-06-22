# Safety and Governance

The system can place purchase orders and move prices. Even in a prototype, those are the kinds of actions that need controls. My safety design assumes agents will sometimes be wrong, so the goal is containment and recovery, not perfection.

## 1. Human-in-the-loop approval

The approver gates two action classes:

- purchase orders above `approval_order_value` (`$15,000`),
- price moves beyond `approval_price_pct` (`±15%`).

Actions inside policy are auto-approved with simulated latency. Actions outside policy are escalated to a human queue. Other agents cannot clear that queue themselves.

This matters because the human should not be part of the same local objective as pricing or inventory. The approver's job is not to maximize this tick's reward; it is to enforce policy and slow down risky actions.

## 2. Append-only audit trail

Every routed message and governance event is appended to the audit log. If `--audit` is provided, the run writes a JSONL file.

Because the orchestrator is the only router, the audit log has a complete view of the decision path. For a supplier award, the log can show:

1. the original replenishment request,
2. the request for proposal,
3. all supplier bids and declines,
4. the winning bid,
5. any approval decision,
6. the final committed action.

That is the difference between “the system ordered 1,200 units” and “here is the exact chain of messages that led to the order.”

## 3. Circuit breaker

The circuit breaker runs between planning and sourcing. It checks whether the proposed order is far above recent realized demand. The current threshold is `cb_order_mult = 3.5`.

If the order looks like a runaway, the orchestrator:

- clamps the order to a safer band,
- reverts any destabilizing price move from the same tick,
- emits a `CIRCUIT_BREAK` event,
- adds an escalation item for human review.

I chose clamp rather than cancel because canceling every suspicious order can create the opposite failure: the system refuses to buy stock during a real spike and causes a stockout. Clamping is a more balanced response.

## 4. Rollback

The environment snapshots state at the start of every tick. If governance needs to undo a price move or cancel a not-yet-arrived order, the environment can restore the earlier state.

Rollback is included because prevention is not always enough. A system that can act should also have a defined recovery path.

## Failure modes considered

| Failure | What happens | Mitigation |
|---|---|---|
| Supplier unavailable | supplier declines the bid | contract-net can award another supplier |
| Runaway order | order is much larger than recent demand | breaker clamps and escalates |
| Price cut during shortage | demand increases into low inventory | governed pricing uses stock-health; breaker can revert |
| Forecast bias | safety stock is too high or too low | forecast error is measured; service buffer absorbs some error |
| Human approval overload | too many escalations | known gap; thresholds should be tuned and escalation rate monitored |
| Audit tampering | history could be changed | prototype is append-only; production version should be hash-chained or write-once |
| Tool misuse | agent accesses state or actions outside its job | scopes define the intended least-privilege boundary |

## Observability

The monitoring plan follows the four evaluation levels:

| Level | Operational signal |
|---|---|
| Agent | rising forecast MAPE, unstable price changes, unusually large order variance |
| Interaction | bullwhip ratio, message volume, failed supplier negotiations, circuit-break count |
| System | fill rate, lost units, profit, stockout penalty |
| Human | escalation rate, pending queue size, approval latency |

A real deployment would alert an operator when escalation rate rises, bullwhip ratio climbs, fill rate drops, or the circuit breaker trips repeatedly.

## Rollback and safe mode

During an incident, the safest mode is to make the system propose actions but require a human to commit them.

In this prototype, that can be approximated by:

- setting `auto_approve=False`,
- lowering the circuit-break threshold,
- reviewing the audit log before accepting large actions.

That gives the human control while still preserving the agent-generated analysis.

## Known gaps

This is not a production safety system yet. The main gaps are:

- no production identity or authentication at the agent boundary,
- no rate limit on escalations,
- mocked human approval,
- no tamper-evident audit store,
- single-process execution rather than distributed services.

The boundaries are still useful because they show where those controls would attach: identity at the supplier/A2A edge, scoped tool access at the MCP-style tool edge, and stronger audit storage around the log.
