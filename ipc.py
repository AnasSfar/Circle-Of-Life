# ipc.py

from dataclasses import dataclass, asdict
from typing import Any, Dict, Tuple
import multiprocessing


@dataclass
class DisplayCommand:
    cmd: str
    args: Dict[str, Any]


@dataclass
class Snapshot:
    tick: int
    predators: int
    preys: int
    grass: int
    drought: bool
    prey_energy_stats: Tuple[float, float, float]
    predator_energy_stats: Tuple[float, float, float]
    prey_probs: Tuple[float, float]
    pred_probs: Tuple[float, float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def create_queues():
    """
    Backward-compatible helper expected by older main/env code.
    Returns: (env_to_display, display_to_env, log_to_display, energies_to_env, events_to_env)
    """
    env_to_display = multiprocessing.Queue()
    display_to_env = multiprocessing.Queue()
    log_to_display = multiprocessing.Queue()
    energies_to_env = multiprocessing.Queue()
    events_to_env = multiprocessing.Queue()
    return env_to_display, display_to_env, log_to_display, energies_to_env, events_to_env


def create_shared_state():
    """
    Backward-compatible helper expected by older code.
    Preferred shared state implementation lives in shared_env.SharedEnv.
    """
    from shared_env import SharedEnv
    return SharedEnv()
