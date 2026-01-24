# predator.py
# Predator process: reads shared env (grass/drought/tick) but does not write it.
# It requests hunts via events_to_env and receives results via ctrl_q.

import os
import random
import time
import socket
import config


def _join_env_socket(kind: str, host: str, port: int, pid: int):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect((host, port))
        msg = f"{kind} {pid}\n".encode("utf-8")
        s.sendall(msg)
    finally:
        try:
            s.close()
        except Exception:
            pass


def run_predator(shared_env, energies_to_env, events_to_env, ctrl_q):
    pid = os.getpid()
    _join_env_socket("predator", config.ENV_HOST, config.ENV_PORT, pid)

    my_energy = config.PREDATOR_INITIAL_ENERGY
    active = False

    hunt_tries_left = 3
    repro_tries_left = 3

    while my_energy > 0 and shared_env.running.value:
        time.sleep(config.TICK_DURATION)

        # control messages: die / hunt_result
        try:
            while True:
                msg = ctrl_q.get_nowait()
                if msg[0] == "die":
                    energies_to_env.put(("dead", "predator", pid))
                    return
                elif msg[0] == "hunt_result":
                    if bool(msg[1]):
                        my_energy += config.PREDATOR_EAT_GAIN
        except Exception:
            pass

        # decay
        my_energy -= config.PREDATOR_ENERGY_DECAY

        # active/passive with hysteresis
        if my_energy < config.H_ENERGY:
            active = True
        elif my_energy > config.H_ENERGY * 1.5:
            active = False

        # Hunt: up to 3 attempts
        if active and hunt_tries_left > 0:
            hunt_tries_left -= 1
            if random.random() < config.PRED_HUNT_PROB:
                events_to_env.put(("hunt", pid))

        # Reproduction: up to 3 attempts
        if my_energy > config.R_ENERGY and repro_tries_left > 0:
            repro_tries_left -= 1
            if random.random() < config.PRED_REPRO_PROB:
                events_to_env.put(("spawn_predator", 1))
                my_energy -= config.PRED_REPRO_COST

        energies_to_env.put(("predator", pid, float(my_energy), bool(active)))

    energies_to_env.put(("dead", "predator", pid))
