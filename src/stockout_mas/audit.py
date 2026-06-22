"""Append-only audit trail.

Every message routed and every governance event (approval, circuit-break,
rollback) is appended here. This is the record an auditor or post-incident
review reads. Optionally mirrored to JSONL on disk.
"""
from __future__ import annotations

import json
from typing import Optional

from .messages import Message


class AuditLog:
    def __init__(self, path: Optional[str] = None):
        self.entries: list[dict] = []
        self.messages: list[Message] = []
        self._path = path
        if path:
            open(path, "w").close()  # truncate

    def record_message(self, msg: Message) -> None:
        self.messages.append(msg)
        self._append({"kind": "message", "tick": msg.tick, "sender": msg.sender,
                      "recipients": msg.recipients, "type": msg.msg_type.value,
                      "performative": msg.performative.value,
                      "conversation_id": msg.conversation_id, "payload": msg.payload})

    def record_event(self, tick: int, event: str, detail: dict) -> None:
        self._append({"kind": "event", "tick": tick, "event": event, "detail": detail})

    def _append(self, row: dict) -> None:
        self.entries.append(row)
        if self._path:
            with open(self._path, "a") as f:
                f.write(json.dumps(row, default=str) + "\n")

    def events(self, name: str) -> list[dict]:
        return [e for e in self.entries if e.get("event") == name]
