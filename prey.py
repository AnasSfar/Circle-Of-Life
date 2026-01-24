# prey.py (final) - Option A: 3 tentatives max + probabilités augmentées

import time
import random
import os
import config


def run_prey(energies_to_env, events_to_env, ctrl_q):
    pid = os.getpid()
    my_energy = config.PREY_INITIAL_ENERGY
    active = False

    # 3 tentatives max (définitif après)
    eat_tries_left = 3
    repro_tries_left = 3

    # Probabilités (Option A)
    EAT_PROB = 0.8
    REPRO_PROB = 0.5

    while my_energy > 0:
        time.sleep(config.TICK_DURATION)

        # control messages: die / grass_grant
        try:
            while True:
                msg = ctrl_q.get_nowait()
                if msg[0] == "die":
                    energies_to_env.put(("dead", "prey", pid))
                    return
                elif msg[0] == "grass_grant":
                    granted = int(msg[1])
                    my_energy += granted  # 1 herbe = 1 énergie
        except Exception:
            pass

        my_energy -= config.PREY_ENERGY_DECAY

        # active/passive
        if my_energy < config.H_ENERGY:
            active = True
        elif my_energy > config.H_ENERGY * 1.5:
            active = False

        # Eat: max 3 attempts total (only while active)
        if active and eat_tries_left > 0:
            requested = random.randint(
                config.PREY_MIN_EAT,
                int(config.R_ENERGY * config.PREY_MAX_EAT_FACTOR)
            )
            if random.random() < EAT_PROB:
                events_to_env.put(("eat_grass", pid, requested))
            else:
                eat_tries_left -= 1

        # Reproduction: max 3 attempts total (only if energy > R)
        if my_energy > config.R_ENERGY and repro_tries_left > 0:
            if random.random() < REPRO_PROB:
                events_to_env.put(("spawn_prey", 1))
                my_energy -= 15
            else:
                repro_tries_left -= 1

        energies_to_env.put(("prey", pid, float(my_energy), bool(active)))

    energies_to_env.put(("dead", "prey", pid))

