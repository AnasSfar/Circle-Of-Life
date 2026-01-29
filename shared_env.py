# shared_env.py
# Shared memory structures accessible to ENV + predator/prey processes (NOT display).

import multiprocessing


class SharedEnv:
    """
    Shared state stored in shared memory primitives (Value) + a Lock.
    Predator/Prey should READ these values.
    Only env should WRITE them.
    """
    def __init__(self):
        self.lock = multiprocessing.Lock()

        self.running = multiprocessing.Value("b", True)     # bool
        self.tick = multiprocessing.Value("i", 0)           # int
        self.grass = multiprocessing.Value("i", 0)          # int
        self.drought = multiprocessing.Value("b", False)    # bool

        self.preys = multiprocessing.Value("i", 0)
        self.predators = multiprocessing.Value("i", 0)

    def set_initial(self, grass: int, drought: bool = False):
        with self.lock:
            self.tick.value = 0
            self.grass.value = int(grass)
            self.drought.value = bool(drought)
            self.preys.value = 0
            self.predators.value = 0

    def get_state(self):
        with self.lock:
            return {
                "running": bool(self.running.value),
                "tick": int(self.tick.value),
                "grass": int(self.grass.value),
                "drought": bool(self.drought.value),
                "preys": int(self.preys.value),
                "predators": int(self.predators.value),
            }
