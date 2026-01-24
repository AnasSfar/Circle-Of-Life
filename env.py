# env.py — UNIX-LIKE FINAL VERSION
# Requires: Linux / WSL / VM (POSIX signals)

import os
import time
import socket
import threading
import multiprocessing
import random
import signal

import config
from ipc import Snapshot
from prey import run_prey
from predator import run_predator


def _energy_stats(values):
    if not values:
        return (0.0, 0.0, 0.0)
    return (float(min(values)), float(sum(values) / len(values)), float(max(values)))


def _log(log_to_display, msg: str):
    try:
        ts = time.strftime("%H:%M:%S")
        log_to_display.put_nowait(f"[{ts}] {msg}")
    except Exception:
        pass


def run_env(shared_env, env_to_display, display_to_env,
            energies_to_env, events_to_env, log_to_display):

    server_socket = None

    prey_procs = {}
    pred_procs = {}
    prey_ctrl = {}
    pred_ctrl = {}

    prey_energy = {}
    pred_energy = {}
    prey_active = {}
    reserved_preys = set()

    # =======================
    # DROUGHT = POSIX SIGNALS
    # =======================

    DROUGHT_SIGNAL = signal.SIGUSR1

    def drought_signal_handler(signum, frame):
        """ONLY place where drought state changes"""
        with shared_env.lock:
            shared_env.drought.value = not bool(shared_env.drought.value)
            now = bool(shared_env.drought.value)
            if now:
                shared_env.grass.value //= 2
        _log(log_to_display, f"🌵 Drought toggled by SIGNAL (drought={now})")

    def schedule_next_drought():
        if not config.ENABLE_DROUGHT_TIMER:
            return

        with shared_env.lock:
            is_drought = bool(shared_env.drought.value)

        if is_drought:
            dt = random.randint(config.DROUGHT_MIN_SECONDS,
                                config.DROUGHT_MAX_SECONDS)
        else:
            dt = random.randint(config.NORMAL_MIN_SECONDS,
                                config.NORMAL_MAX_SECONDS)

        signal.setitimer(signal.ITIMER_REAL, float(dt))
        _log(log_to_display, f"[DROUGHT] next signal in {dt}s")

    def alarm_handler(signum, frame):
        os.kill(os.getpid(), DROUGHT_SIGNAL)
        schedule_next_drought()

    # =======================
    # RESET / SPAWN
    # =======================

    def reset_to_initial():
        for q in list(prey_ctrl.values()):
            try:
                q.put(("die",))
            except Exception:
                pass
        for q in list(pred_ctrl.values()):
            try:
                q.put(("die",))
            except Exception:
                pass

        for p in list(prey_procs.values()) + list(pred_procs.values()):
            try:
                p.terminate()
            except Exception:
                pass

        prey_procs.clear()
        pred_procs.clear()
        prey_ctrl.clear()
        pred_ctrl.clear()
        prey_energy.clear()
        pred_energy.clear()
        prey_active.clear()
        reserved_preys.clear()

        shared_env.set_initial(grass=int(config.INITIAL_GRASS), drought=False)
        _log(log_to_display, "🔄 Reset environment")

        schedule_next_drought()

    def spawn_prey(n):
        with shared_env.lock:
            n = min(n, config.MAX_PREYS - shared_env.preys.value)
            if n <= 0:
                return
            shared_env.preys.value += n

        for _ in range(n):
            q = multiprocessing.Queue()
            p = multiprocessing.Process(
                target=run_prey,
                args=(shared_env, energies_to_env, events_to_env, q)
            )
            p.start()
            prey_procs[p.pid] = p
            prey_ctrl[p.pid] = q

    def spawn_predator(n):
        with shared_env.lock:
            n = min(n, config.MAX_PREDATORS - shared_env.predators.value)
            if n <= 0:
                return
            shared_env.predators.value += n

        for _ in range(n):
            q = multiprocessing.Queue()
            p = multiprocessing.Process(
                target=run_predator,
                args=(shared_env, energies_to_env, events_to_env, q)
            )
            p.start()
            pred_procs[p.pid] = p
            pred_ctrl[p.pid] = q

    def kill_one_active_prey():
        for pid, active in prey_active.items():
            if active and pid not in reserved_preys and pid in prey_ctrl:
                reserved_preys.add(pid)
                prey_active[pid] = False
                prey_ctrl[pid].put(("die",))
                return pid
        return None

    # =======================
    # SOCKET JOIN (SPEC)
    # =======================

    def accept_clients():
        while shared_env.running.value:
            try:
                c, _ = server_socket.accept()
                c.close()
            except Exception:
                break

    # =======================
    # MAIN LOOP
    # =======================

    try:
        # Register POSIX signal handlers
        signal.signal(DROUGHT_SIGNAL, drought_signal_handler)
        signal.signal(signal.SIGALRM, alarm_handler)

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((config.ENV_HOST, config.ENV_PORT))
        server_socket.listen(10)
        threading.Thread(target=accept_clients, daemon=False).start()

        reset_to_initial()
        tick = 0

        while shared_env.running.value:
            with shared_env.lock:
                shared_env.tick.value = tick

            # ---- UI commands ----
            while not display_to_env.empty():
                cmd = display_to_env.get_nowait()

                if cmd.cmd == "quit":
                    shared_env.running.value = False

                elif cmd.cmd == "reset":
                    reset_to_initial()

                elif cmd.cmd == "trigger_drought":
                    os.kill(os.getpid(), DROUGHT_SIGNAL)

                elif cmd.cmd == "add_prey":
                    spawn_prey(int(cmd.args.get("value", 1)))

                elif cmd.cmd == "add_predator":
                    spawn_predator(int(cmd.args.get("value", 1)))

            # ---- Telemetry ----
            while not energies_to_env.empty():
                msg = energies_to_env.get_nowait()
                if msg[0] == "prey":
                    _, pid, e, a = msg
                    prey_energy[pid] = e
                    prey_active[pid] = a
                elif msg[0] == "predator":
                    _, pid, e, _ = msg
                    pred_energy[pid] = e
                elif msg[0] == "dead":
                    _, kind, pid = msg
                    if kind == "prey":
                        reserved_preys.discard(pid)
                        prey_energy.pop(pid, None)
                        prey_active.pop(pid, None)
                        prey_ctrl.pop(pid, None)
                        prey_procs.pop(pid, None)
                        with shared_env.lock:
                            shared_env.preys.value -= 1
                    elif kind == "predator":
                        pred_energy.pop(pid, None)
                        pred_ctrl.pop(pid, None)
                        pred_procs.pop(pid, None)
                        with shared_env.lock:
                            shared_env.predators.value -= 1

            # ---- Actions ----
            while not events_to_env.empty():
                ev = events_to_env.get_nowait()
                if ev[0] == "eat_grass":
                    _, pid, req = ev
                    with shared_env.lock:
                        g = min(req, shared_env.grass.value)
                        shared_env.grass.value -= g
                    prey_ctrl[pid].put(("grass_grant", g))
                elif ev[0] == "hunt":
                    _, pid = ev
                    success = kill_one_active_prey() is not None
                    pred_ctrl[pid].put(("hunt_result", success))

            # ---- Grass growth ----
            with shared_env.lock:
                if not shared_env.drought.value:
                    shared_env.grass.value += config.GRASS_GROWTH_PER_TICK
                else:
                    shared_env.grass.value += int(
                        config.GRASS_GROWTH_PER_TICK * config.DROUGHT_GRASS_FACTOR
                    )
                shared_env.grass.value = min(shared_env.grass.value, config.MAX_GRASS)

            snapshot = Snapshot(
                tick=tick,
                predators=shared_env.predators.value,
                preys=shared_env.preys.value,
                grass=shared_env.grass.value,
                drought=shared_env.drought.value,
                prey_energy_stats=_energy_stats(list(prey_energy.values())),
                predator_energy_stats=_energy_stats(list(pred_energy.values())),
                prey_probs=(config.PREY_EAT_PROB, config.PREY_REPRO_PROB),
                pred_probs=(config.PRED_HUNT_PROB, config.PRED_REPRO_PROB),
            )
            env_to_display.put(snapshot)

            tick += 1
            time.sleep(config.TICK_DURATION)

    finally:
        shared_env.running.value = False
        if server_socket:
            server_socket.close()
        _log(log_to_display, "🛑 ENV stopped")
