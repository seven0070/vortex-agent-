"""
Sovereign layer — identity, objectives, state, priorities, lifecycle

Sovereign does NOT directly execute tools.
It sets objectives and constraints:
  Sovereign → Council → Orchestration → Tools
"""
from .identity import IdentityManager
from .objectives import ObjectiveManager
from .state import SovereignState
from .priorities import PriorityManager
from .lifecycle import LifecycleManager

class Sovereign:
    """
    Maintains:
    WHO AM I?
    WHAT AM I TRYING TO ACHIEVE?
    WHAT STATE AM I IN?
    WHAT ARE MY CURRENT PRIORITIES?
    WHAT AM I ALLOWED TO CHANGE?
    WHAT HAVE I LEARNED?
    """
    def __init__(self, memory=None):
        self.memory = memory
        self.identity = IdentityManager(memory=memory)
        self.objectives = ObjectiveManager(memory=memory)
        self.state = SovereignState(memory=memory)
        self.priorities = PriorityManager(memory=memory)
        self.lifecycle = LifecycleManager(memory=memory)

    def context(self) -> dict:
        return {
            "identity": self.identity.describe(),
            "objectives": self.objectives.list_active(),
            "state": self.state.snapshot(),
            "priorities": self.priorities.current(),
            "lifecycle": self.lifecycle.status(),
        }

    def set_objective(self, goal: str, priority: int = 5):
        return self.objectives.add(goal, priority=priority)

    def check_allowed(self, change: str) -> bool:
        # what am I allowed to change?
        return not self.state.is_protected(change)

__all__ = ["Sovereign", "IdentityManager", "ObjectiveManager", "SovereignState", "PriorityManager", "LifecycleManager"]
