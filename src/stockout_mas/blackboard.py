"""Blackboard: the shared-state coordination surface.

Agents post structured facts here (forecast, inventory position, price,
stock-health signal) and read what others posted. Keeping shared state in
one observable place is what makes the blackboard pattern auditable and is
half of why we can reconstruct any decision after the fact.
"""
from __future__ import annotations

from typing import Any


class Blackboard:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._history: list[tuple[int, str, Any]] = []  # (tick, key, value)

    def write(self, tick: int, key: str, value: Any) -> None:
        self._store[key] = value
        self._history.append((tick, key, value))

    def read(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def snapshot(self) -> dict[str, Any]:
        return dict(self._store)

    def history(self, key: str) -> list[tuple[int, Any]]:
        return [(t, v) for (t, k, v) in self._history if k == key]
