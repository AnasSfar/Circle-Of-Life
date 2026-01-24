# ipc.py

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, Tuple


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

