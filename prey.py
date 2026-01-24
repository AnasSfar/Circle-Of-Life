# prey.py
# Prey process: reads shared env (grass/drought/tick) but does not write it.
# It requests resources via events_to_env and receives grants via ctrl_q.

import os
import random
import time
import socket
import config


def _join_env_socket(kind: str, host: str, port: int, pid: int):
    """
    Join handshake required by the spec:
    env listens on socket, predator/prey connect and register.
    """
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


def run_prey(shared_env, energies_to_env, events_to_env, ctrl_q):
    pid = os.getpid()
    _join_env_socket("prey", config.ENV_HOST, config.ENV_PORT, pid)

    my_energy = config.PREY_INITIAL_ENERGY
    active = False

    eat_tries_left = 3
    repro_tries_left = 3

    while my_energy > 0 and shared_env.running.value:
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
                    my_energy += granted  # 1 grass = 1 energy
        except Exception:
            pass

        # decay
        my_energy -= config.PREY_ENERGY_DECAY

        # active/passive with hysteresis
        if my_energy < config.H_ENERGY:
            active = True
        elif my_energy > config.H_ENERGY * 1.5:
            active = False

        # Eat: up to 3 attempts
        if active and eat_tries_left > 0:
            eat_tries_left -= 1
            requested = random.randint(
                config.PREY_MIN_EAT,
                max(config.PREY_MIN_EAT, int(config.R_ENERGY * config.PREY_MAX_EAT_FACTOR))
            )
            if random.random() < config.PREY_EAT_PROB:
                events_to_env.put(("eat_grass", pid, requested))

        # Reproduction: up to 3 attempts
        if my_energy > config.R_ENERGY and repro_tries_left > 0:
            repro_tries_left -= 1
            if random.random() < config.PREY_REPRO_PROB:
                events_to_env.put(("spawn_prey", 1))
                my_energy -= config.PREY_REPRO_COST

        energies_to_env.put(("prey", pid, float(my_energy), bool(active)))

    energies_to_env.put(("dead", "prey", pid))
