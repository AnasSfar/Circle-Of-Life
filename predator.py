# predator.py (final corrigé) - Option A: 3 tentatives max
# Tentative = essai réel (on décrémente à chaque essai, succès ou échec)

import time
import random
import os
import config


def run_predator(energies_to_env, events_to_env, ctrl_q):
    pid = os.getpid()
    my_energy = config.PREDATOR_INITIAL_ENERGY
    active = False

    hunt_tries_left = 3
    repro_tries_left = 3

    # Probabilités
    HUNT_PROB = config.PRED_HUNT_PROB
    REPRO_PROB = config.PRED_REPRO_PROB

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

        # Hunt: max 3 tentatives (tentative consommée à chaque essai)
        if active and hunt_tries_left > 0:
            hunt_tries_left -= 1
            if random.random() < HUNT_PROB:
                events_to_env.put(("hunt", pid))

        # Reproduction: max 3 tentatives (tentative consommée à chaque essai)
        if my_energy > config.R_ENERGY and repro_tries_left > 0:
            repro_tries_left -= 1
            if random.random() < REPRO_PROB:
                events_to_env.put(("spawn_predator", 1))
                my_energy -= 20

        energies_to_env.put(("predator", pid, float(my_energy), bool(active)))

    energies_to_env.put(("dead", "predator", pid))
