# env.py

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

    def alarm_handler(signum, frame):
        # SIGALRM -> trigger SIGUSR1 (spec demo: drought notified by a signal)
        os.kill(os.getpid(), DROUGHT_SIGNAL)

    # =======================
    # RESET / SPAWN
    # =======================

    def _terminate_process(p: multiprocessing.Process):
        try:
            p.terminate()
        except Exception:
            pass
        try:
            p.join(timeout=0.5)
        except Exception:
            pass

    def reset_to_initial():
        # ask all animals to die
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

        # terminate everything (fast)
        for p in list(prey_procs.values()) + list(pred_procs.values()):
            _terminate_process(p)

        prey_procs.clear()
        pred_procs.clear()
        prey_ctrl.clear()
        pred_ctrl.clear()
        prey_energy.clear()
        pred_energy.clear()
        prey_active.clear()
        reserved_preys.clear()

        shared_env.set_initial(grass=int(config.INITIAL_GRASS), drought=False)
        _log(log_to_display, "🔄 Reset environment (0 prey, 0 predator)")

    def spawn_prey(n: int, origin: str = "UI"):
        n = int(n)
        if n <= 0:
            return

        with shared_env.lock:
            can_add = max(0, int(config.MAX_PREYS) - int(shared_env.preys.value))
            n = min(n, can_add)
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

        _log(log_to_display, f"🐇 +{n} prey")

    def spawn_predator(n: int, origin: str = "UI"):
        n = int(n)
        if n <= 0:
            return

        with shared_env.lock:
            can_add = max(0, int(config.MAX_PREDATORS) - int(shared_env.predators.value))
            n = min(n, can_add)
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

        _log(log_to_display, f"🦁 +{n} predator")

    def kill_one_active_prey():
        # rule: only active preys can be predated
        for pid, active in list(prey_active.items()):
            if not active:
                continue
            if pid in reserved_preys:
                continue
            if pid not in prey_ctrl:
                continue

            reserved_preys.add(pid)
            prey_active[pid] = False
            try:
                prey_ctrl[pid].put(("die",))
                return pid
            except Exception:
                reserved_preys.discard(pid)
                return None

        return None

    # =======================
    # SOCKET JOIN (SPEC)
    # =======================

    def accept_clients():
        # NOTE: thread must be daemon so it won't block shutdown
        while shared_env.running.value:
            try:
                c, _ = server_socket.accept()
                try:
                    # optional handshake content; not strictly required for your current design
                    _ = c.recv(64)
                except Exception:
                    pass
                try:
                    c.close()
                except Exception:
                    pass
            except Exception:
                break

    # =======================
    # MAIN LOOP
    # =======================

    try:
        # Register POSIX signal handlers (Linux/WSL)
        signal.signal(DROUGHT_SIGNAL, drought_signal_handler)
        signal.signal(signal.SIGALRM, alarm_handler)

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((config.ENV_HOST, config.ENV_PORT))
        server_socket.listen(10)

        threading.Thread(target=accept_clients, daemon=True).start()

        reset_to_initial()
        tick = 0

        while shared_env.running.value:
            with shared_env.lock:
                shared_env.tick.value = tick

            # ---- UI commands ----
            while not display_to_env.empty():
                cmd = display_to_env.get_nowait()

                if cmd.cmd == "quit":
                    with shared_env.lock:
                        shared_env.running.value = False

                elif cmd.cmd == "reset":
                    reset_to_initial()

                elif cmd.cmd == "trigger_drought":
                    os.kill(os.getpid(), DROUGHT_SIGNAL)

                elif cmd.cmd == "add_prey":
                    spawn_prey(int(cmd.args.get("value", 1)), origin="UI")

                elif cmd.cmd == "add_predator":
                    spawn_predator(int(cmd.args.get("value", 1)), origin="UI")

                elif cmd.cmd == "set_grass":
                    val = int(float(cmd.args.get("value", 0)))
                    with shared_env.lock:
                        shared_env.grass.value = max(0, min(val, int(config.MAX_GRASS)))
                    _log(log_to_display, f"🌿 Grass set to {int(shared_env.grass.value)}")

            # ---- Telemetry ----
            while not energies_to_env.empty():
                msg = energies_to_env.get_nowait()

                if msg[0] == "prey":
                    _, pid, e, a = msg
                    prey_energy[pid] = float(e)
                    prey_active[pid] = bool(a)

                elif msg[0] == "predator":
                    _, pid, e, _a = msg
                    pred_energy[pid] = float(e)

                elif msg[0] == "dead":
                    _, kind, pid = msg

                    if kind == "prey":
                        reserved_preys.discard(pid)
                        prey_energy.pop(pid, None)
                        prey_active.pop(pid, None)
                        prey_ctrl.pop(pid, None)
                        prey_procs.pop(pid, None)
                        with shared_env.lock:
                            shared_env.preys.value = max(0, int(shared_env.preys.value) - 1)
                        _log(log_to_display, f"☠️ Prey {pid} dead")

                    elif kind == "predator":
                        pred_energy.pop(pid, None)
                        pred_ctrl.pop(pid, None)
                        pred_procs.pop(pid, None)
                        with shared_env.lock:
                            shared_env.predators.value = max(0, int(shared_env.predators.value) - 1)
                        _log(log_to_display, f"☠️ Predator {pid} dead")

            # ---- Actions ----
            while not events_to_env.empty():
                ev = events_to_env.get_nowait()

                if ev[0] == "eat_grass":
                    _, pid, req = ev
                    req = max(0, int(req))
                    with shared_env.lock:
                        granted = min(req, int(shared_env.grass.value))
                        shared_env.grass.value -= granted

                    if pid in prey_ctrl:
                        try:
                            prey_ctrl[pid].put(("grass_grant", granted))
                        except Exception:
                            pass

                    if granted > 0:
                        _log(log_to_display, f"🐇 Prey {pid} eats {granted} grass")
                    else:
                        _log(log_to_display, f"🐇 Prey {pid} wants grass but none left")

                elif ev[0] == "hunt":
                    _, pred_pid = ev
                    killed = kill_one_active_prey()
                    success = killed is not None

                    if pred_pid in pred_ctrl:
                        try:
                            pred_ctrl[pred_pid].put(("hunt_result", success))
                        except Exception:
                            pass

                    if success:
                        _log(log_to_display, f"🦁 Predator {pred_pid} eats prey {killed}")
                    else:
                        _log(log_to_display, f"🦁 Predator {pred_pid} hunts but fails (no active prey)")

                elif ev[0] == "spawn_prey":
                    _, n = ev
                    n = int(n)
                    if n > 0:
                        spawn_prey(n, origin="reproduction")
                        _log(log_to_display, f"🐇 Reproduction: +{n} prey")

                elif ev[0] == "spawn_predator":
                    _, n = ev
                    n = int(n)
                    if n > 0:
                        spawn_predator(n, origin="reproduction")
                        _log(log_to_display, f"🦁 Reproduction: +{n} predator")

            # ---- Grass growth ----
            with shared_env.lock:
                if not shared_env.drought.value:
                    shared_env.grass.value += int(config.GRASS_GROWTH_PER_TICK)
                else:
                    shared_env.grass.value += int(config.GRASS_GROWTH_PER_TICK * config.DROUGHT_GRASS_FACTOR)

                if shared_env.grass.value > int(config.MAX_GRASS):
                    shared_env.grass.value = int(config.MAX_GRASS)
                if shared_env.grass.value < 0:
                    shared_env.grass.value = 0

                predators_n = int(shared_env.predators.value)
                preys_n = int(shared_env.preys.value)
                grass_n = int(shared_env.grass.value)
                drought_b = bool(shared_env.drought.value)

            snapshot = Snapshot(
                tick=tick,
                predators=predators_n,
                preys=preys_n,
                grass=grass_n,
                drought=drought_b,
                prey_energy_stats=_energy_stats(list(prey_energy.values())),
                predator_energy_stats=_energy_stats(list(pred_energy.values())),
                prey_probs=(config.PREY_EAT_PROB, config.PREY_REPRO_PROB),
                pred_probs=(config.PRED_HUNT_PROB, config.PRED_REPRO_PROB),
            )
            env_to_display.put(snapshot)

            tick += 1
            time.sleep(config.TICK_DURATION)

    finally:
        try:
            with shared_env.lock:
                shared_env.running.value = False
        except Exception:
            pass

        try:
            if server_socket:
                server_socket.close()
        except Exception:
            pass

        _log(log_to_display, "🛑 ENV stopped")
