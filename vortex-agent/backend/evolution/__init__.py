"""Vortex Evolution Engine v1 — real candidate patching, sandbox, canary, rollback."""
from .engine import EvolutionEngine, WeaknessFinder, HypothesisGenerator, BenchmarkRunner
from .patcher import CandidatePatcher, CandidateGenerator
from .workspace import CandidateWorkspace, prune_tmp_worktrees
from .sandbox import SandboxRunner
from .security import SecurityScanner
from .promotion import PromotionPolicy
from .canary import CanaryRunner
from .rollback import RollbackManager
from .overlay import Overlay, get_active, activate, load_current, load_last_known_good

__all__ = [
    "EvolutionEngine",
    "WeaknessFinder",
    "HypothesisGenerator",
    "BenchmarkRunner",
    "CandidatePatcher",
    "CandidateGenerator",
    "SandboxRunner",
    "SecurityScanner",
    "PromotionPolicy",
    "CanaryRunner",
    "RollbackManager",
    "Overlay",
    "get_active",
    "activate",
    "load_current",
    "load_last_known_good",
]
