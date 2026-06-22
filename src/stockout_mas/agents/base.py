"""Base agent.

Each agent has: a name, an explicit permission set (the MCP-style scopes it is
allowed to touch), and small local memory. Agents expose intent through return
values; only the orchestrator mutates the world. No agent can act outside its
declared scopes — the orchestrator enforces it.
"""
from __future__ import annotations

from ..blackboard import Blackboard
from ..config import Config


class Agent:
    #: scopes this agent is permitted to use (least privilege)
    scopes: set[str] = set()

    def __init__(self, name: str, cfg: Config, bb: Blackboard):
        self.name = name
        self.cfg = cfg
        self.bb = bb
        self.memory: dict = {}

    def can(self, scope: str) -> bool:
        return scope in self.scopes
