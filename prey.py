# prey.py (final) - Option A: 3 tentatives max (tentative = essai réel)

import time
import random
import os
import config


def run_prey(energies_to_env, events_to_env, ctrl_q):
    pid = os.getpid()
    my_energy = config.PREY_INITIAL_ENERGY
    active = False

    eat_tries_left = 3
    repro_tries_left = 3

    # Probabilités (tes valeurs)
    EAT_PROB = config.PREY_EAT_PROB
    REPRO_PROB = config.PREY_REPRO_PROB


    while my_energy > 0:
        time.sleep(config.TICK_DURATION)

        # messages de contrôle: die / grass_grant
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

        # actif/passif
        if my_energy < config.H_ENERGY:
            active = True
        elif my_energy > config.H_ENERGY * 1.5:
            active = False

        # Manger: max 3 tentatives (tentative consommée à chaque essai)
        if active and eat_tries_left > 0:
            eat_tries_left -= 1
            requested = random.randint(
                config.PREY_MIN_EAT,
                int(config.R_ENERGY * config.PREY_MAX_EAT_FACTOR)
            )
            if random.random() < EAT_PROB:
                events_to_env.put(("eat_grass", pid, requested))

        # Reproduction: max 3 tentatives (tentative consommée à chaque essai)
        if my_energy > config.R_ENERGY and repro_tries_left > 0:
            repro_tries_left -= 1
            if random.random() < REPRO_PROB:
                events_to_env.put(("spawn_prey", 1))
                my_energy -= 15

        energies_to_env.put(("prey", pid, float(my_energy), bool(active)))

    energies_to_env.put(("dead", "prey", pid))
