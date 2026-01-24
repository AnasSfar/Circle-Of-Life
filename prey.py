import os
import time
import random
import socket
import config


def _join_env_socket(kind: str, host: str, port: int, pid: int):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect((host, port))
        s.sendall(f"{kind} {pid}\n".encode("utf-8"))
    finally:
        try:
            s.close()
        except Exception:
            pass


def run_prey(shared_env, energies_to_env, events_to_env, ctrl_q):
    pid = os.getpid()
    _join_env_socket("prey", config.ENV_HOST, config.ENV_PORT, pid)

    my_energy = float(config.PREY_INITIAL_ENERGY)
    active = False

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
                    my_energy += granted * float(getattr(config, "PREY_GRASS_GAIN_PER_UNIT", 1))
        except Exception:
            pass

        # decay
        my_energy -= float(config.PREY_ENERGY_DECAY)

        # active/passive with hysteresis
        if my_energy < config.H_ENERGY:
            active = True
        elif my_energy > config.H_ENERGY * 1.5:
            active = False

        # Eat: every tick if active (probabilistic)
        if active and random.random() < config.PREY_EAT_PROB:
            requested = random.randint(
                int(config.PREY_MIN_EAT),
                max(int(config.PREY_MIN_EAT), int(config.R_ENERGY * config.PREY_MAX_EAT_FACTOR))
            )
            events_to_env.put(("eat_grass", pid, requested))

        # Reproduction: every tick if enough energy (probabilistic)
        if my_energy > config.R_ENERGY and random.random() < config.PREY_REPRO_PROB:
            events_to_env.put(("spawn_prey", 1))
            my_energy -= float(getattr(config, "PREY_REPRO_COST", 15))

        energies_to_env.put(("prey", pid, float(my_energy), bool(active)))

    energies_to_env.put(("dead", "prey", pid))