# ipc.py

from multiprocessing import Manager, Queue
from dataclasses import dataclass
from typing import Dict, Any, Tuple
import config


@dataclass
class Snapshot:
    tick: int
    predators: int
    preys: int
    grass: int
    drought: bool
    prey_energy_stats: Tuple[float, float, float]
    predator_energy_stats: Tuple[float, float, float]


@dataclass
class DisplayCommand:
    cmd: str
    args: Dict[str, Any] | None = None


def create_shared_state():
    manager = Manager()
    state = manager.dict()
    state["tick"] = 0
    state["predators"] = config.INITIAL_PREDATORS
    state["preys"] = config.INITIAL_PREYS
    state["grass"] = config.INITIAL_GRASS
    state["drought"] = False
    state["running"] = True
    return manager, state


def create_queues():
    env_to_display = Queue(maxsize=config.ENV_DISPLAY_QUEUE_MAXSIZE)
    display_to_env = Queue(maxsize=200)
    energies_to_env = Queue(maxsize=10000)  # telemetry
    events_to_env = Queue(maxsize=10000)    # actions
    log_to_display = Queue(maxsize=5000)
    return env_to_display, display_to_env, energies_to_env, events_to_env, log_to_display
