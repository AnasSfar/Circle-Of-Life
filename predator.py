# predator.py (final) - Option A: 3 tentatives max + probabilités augmentées

import time
import random
import os
import config


def run_predator(energies_to_env, events_to_env, ctrl_q):
    pid = os.getpid()
    my_energy = config.PREDATOR_INITIAL_ENERGY
    active = False

    # 3 tentatives max (définitif après)
    hunt_tries_left = 3
    repro_tries_left = 3

    # Probabilités (Option A)
    HUNT_PROB = 0.6
    REPRO_PROB = 0.2

    while my_energy > 0:
        time.sleep(config.TICK_DURATION)

        # control messages: die / hunt_result
        try:
            while True:
                msg = ctrl_q.get_nowait()
                if msg[0] == "die":
                    energies_to_env.put(("dead", "predator", pid))
                    return
                elif msg[0] == "hunt_result":
                    success = bool(msg[1])
                    if success:
                        my_energy += config.PREDATOR_EAT_GAIN
        except Exception:
            pass

        my_energy -= config.PREDATOR_ENERGY_DECAY

        # active/passive
        if my_energy < config.H_ENERGY:
            active = True
        elif my_energy > config.H_ENERGY * 1.5:
            active = False

        # Hunt: max 3 attempts total (only while active)
        if active and hunt_tries_left > 0:
            if random.random() < HUNT_PROB:
                events_to_env.put(("hunt", pid))
            else:
                hunt_tries_left -= 1

        # Reproduction: max 3 attempts total (only if energy > R)
        if my_energy > config.R_ENERGY and repro_tries_left > 0:
            if random.random() < REPRO_PROB:
                events_to_env.put(("spawn_predator", 1))
                my_energy -= 20
            else:
                repro_tries_left -= 1

        energies_to_env.put(("predator", pid, float(my_energy), bool(active)))

    energies_to_env.put(("dead", "predator", pid))
