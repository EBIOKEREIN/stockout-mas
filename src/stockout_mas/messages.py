"""Communication contract for the stockout-response MAS.

Every inter-agent interaction is a typed `Message` with a common envelope.
Agents never read each other's internals; they only exchange messages and
read/write the shared blackboard. This is the single chokepoint the
orchestrator routes, logs, and audits.
"""
from __future__ import annotations

import itertools
import time
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

_counter = itertools.count(1)


def _msg_id() -> str:
    return f"m{next(_counter):06d}"


class MsgType(str, Enum):
    # control / state
    FORECAST = "FORECAST"                 # demand -> blackboard/inventory
    STATE_UPDATE = "STATE_UPDATE"         # environment -> blackboard
    ALERT = "ALERT"                       # any -> orchestrator (guardrail trips)
    # replenishment + contract-net
    REPLENISH_REQUEST = "REPLENISH_REQUEST"   # inventory -> orchestrator
    CFP = "CFP"                               # orchestrator -> suppliers (broadcast)
    BID = "BID"                               # supplier -> orchestrator
    AWARD = "AWARD"                           # orchestrator -> winning supplier
    NO_AWARD = "NO_AWARD"                     # orchestrator -> losing suppliers
    # pricing
    PRICE_UPDATE = "PRICE_UPDATE"             # pricing -> blackboard/environment
    # human-in-the-loop
    APPROVAL_REQUEST = "APPROVAL_REQUEST"     # any -> approver
    APPROVAL_RESPONSE = "APPROVAL_RESPONSE"   # approver -> requester
    # governance
    ROLLBACK = "ROLLBACK"                     # orchestrator -> environment
    CIRCUIT_BREAK = "CIRCUIT_BREAK"           # orchestrator -> all


class Performative(str, Enum):
    """FIPA-style speech acts — makes routing + intent explicit and auditable."""
    INFORM = "inform"
    REQUEST = "request"
    PROPOSE = "propose"
    ACCEPT = "accept"
    REJECT = "reject"
    ESCALATE = "escalate"


class Message(BaseModel):
    """The envelope. `payload` is type-specific and validated by the receiver."""
    msg_id: str = Field(default_factory=_msg_id)
    tick: int
    sender: str
    recipients: list[str]                       # ["*"] == broadcast
    msg_type: MsgType
    performative: Performative
    conversation_id: Optional[str] = None       # ties a CFP -> BIDs -> AWARD together
    correlation_id: Optional[str] = None        # reply links to the msg_id it answers
    payload: dict[str, Any] = Field(default_factory=dict)
    wall_clock: float = Field(default_factory=time.time)

    def reply(self, sender: str, msg_type: MsgType, performative: Performative,
              payload: dict[str, Any], recipients: Optional[list[str]] = None) -> "Message":
        return Message(
            tick=self.tick,
            sender=sender,
            recipients=recipients or [self.sender],
            msg_type=msg_type,
            performative=performative,
            conversation_id=self.conversation_id,
            correlation_id=self.msg_id,
            payload=payload,
        )

    def short(self) -> str:
        rcpt = ",".join(self.recipients)
        return f"[t{self.tick:02d}] {self.sender:>10} -> {rcpt:<12} {self.msg_type.value:<17} {self.payload}"
