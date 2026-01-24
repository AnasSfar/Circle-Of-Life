# env.py
# Env process:
#  - keeps populations & climate in shared memory (SharedEnv)
#  - listens on a socket for predator/prey join
#  - display communicates via message queue (display_to_env)
#  - drought is notified via a signal (best effort: SIGALRM/SIGUSR1 on Unix)

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


def run_env(shared_env, env_to_display, display_to_env, energies_to_env, events_to_env, log_to_display):
    server_socket = None

    prey_procs = {}
    pred_procs = {}
    prey_ctrl = {}
    pred_ctrl = {}

    prey_energy = {}
    pred_energy = {}
    prey_active = {}

    reserved_preys = set()  # prevents double-eat while waiting "dead"

    # ---------- drought via signals (Unix best-effort) ----------
    def _toggle_drought(reason: str = "signal"):
        with shared_env.lock:
            shared_env.drought.value = not bool(shared_env.drought.value)
            now_drought = bool(shared_env.drought.value)
            if now_drought:
                shared_env.grass.value = int(shared_env.grass.value // 2)
        _log(log_to_display, f"[DROUGHT] toggle -> {now_drought} ({reason})")

    def _sigusr_handler(signum, frame):
        _toggle_drought(reason=f"signal {signum}")

    def _sigalrm_handler(signum, frame):
        _toggle_drought(reason="SIGALRM timer")

    def _schedule_next_timer():
        if not config.DROUGHT_AUTO:
            return
        # schedule next toggle; alternate durations depending on current drought
        with shared_env.lock:
            is_drought = bool(shared_env.drought.value)
        if is_drought:
            dt = random.randint(config.DROUGHT_MIN_SECONDS, config.DROUGHT_MAX_SECONDS)
        else:
            dt = random.randint(config.NORMAL_MIN_SECONDS, config.NORMAL_MAX_SECONDS)

        # prefer signal-based timer if available
        if hasattr(signal, "setitimer") and hasattr(signal, "ITIMER_REAL"):
            try:
                signal.setitimer(signal.ITIMER_REAL, float(dt))
                _log(log_to_display, f"[DROUGHT] next toggle in {dt}s (signal timer)")
                return
            except Exception:
                pass

        # fallback: thread triggers os.kill with SIGUSR1 (Unix)
        def _thread_kill():
            try:
                sig = getattr(signal, "SIGUSR1", None)
                if sig is None:
                    return
                os.kill(os.getpid(), sig)
            except Exception:
                pass

        threading.Timer(float(dt), _thread_kill).start()
        _log(log_to_display, f"[DROUGHT] next toggle in {dt}s (thread+signal)")

    # ---------- reset / spawn ----------
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

        # join/terminate
        for p in list(prey_procs.values()) + list(pred_procs.values()):
            try:
                p.join(timeout=1)
            except Exception:
                pass
            if p.is_alive():
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
        _log(log_to_display, "Reset: initial state (0 prey, 0 predator)")
        _schedule_next_timer()

    def spawn_prey(n: int, origin: str = "UI"):
        if n <= 0:
            return
        with shared_env.lock:
            can_add = max(0, config.MAX_PREYS - int(shared_env.preys.value))
            n = min(int(n), can_add)
        if n <= 0:
            _log(log_to_display, f"Add prey refused: MAX_PREYS={config.MAX_PREYS}")
            return

        for _ in range(n):
            ctrl_q = multiprocessing.Queue()
            p = multiprocessing.Process(target=run_prey, args=(shared_env, energies_to_env, events_to_env, ctrl_q))
            p.start()
            prey_procs[p.pid] = p
            prey_ctrl[p.pid] = ctrl_q
            with shared_env.lock:
                shared_env.preys.value += 1

        _log(log_to_display, f"Add: +{n} prey ({origin})")

    def spawn_predator(n: int, origin: str = "UI"):
        if n <= 0:
            return
        with shared_env.lock:
            can_add = max(0, config.MAX_PREDATORS - int(shared_env.predators.value))
            n = min(int(n), can_add)
        if n <= 0:
            _log(log_to_display, f"Add predator refused: MAX_PREDATORS={config.MAX_PREDATORS}")
            return

        for _ in range(n):
            ctrl_q = multiprocessing.Queue()
            p = multiprocessing.Process(target=run_predator, args=(shared_env, energies_to_env, events_to_env, ctrl_q))
            p.start()
            pred_procs[p.pid] = p
            pred_ctrl[p.pid] = ctrl_q
            with shared_env.lock:
                shared_env.predators.value += 1

        _log(log_to_display, f"Add: +{n} predator ({origin})")

    def kill_one_active_prey():
        # rule: only active preys can be predated
        for prey_pid, active in list(prey_active.items()):
            if not active:
                continue
            if prey_pid in reserved_preys:
                continue
            if prey_pid not in prey_ctrl:
                continue

            # reserve immediately (prevents double kill before "dead" arrives)
            reserved_preys.add(prey_pid)
            prey_active[prey_pid] = False
            try:
                prey_ctrl[prey_pid].put(("die",))
                return prey_pid
            except Exception:
                reserved_preys.discard(prey_pid)
                return None
        return None

    # ---------- socket join server ----------
    def accept_clients():
        while shared_env.running.value:
            try:
                c, _ = server_socket.accept()
                try:
                    data = c.recv(64).decode("utf-8", errors="ignore").strip()
                except Exception:
                    data = ""
                finally:
                    try:
                        c.close()
                    except Exception:
                        pass

                # Expected: "prey <pid>" or "predator <pid>" (pid not trusted, just for spec demo)
                if data:
                    _log(log_to_display, f"[SOCKET] join: {data}")
            except Exception:
                break

    # ---------- main loop ----------
    try:
        # signals
        try:
            if hasattr(signal, "SIGUSR1"):
                signal.signal(signal.SIGUSR1, _sigusr_handler)
            if hasattr(signal, "SIGALRM"):
                signal.signal(signal.SIGALRM, _sigalrm_handler)
        except Exception:
            pass

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((config.ENV_HOST, config.ENV_PORT))
        server_socket.listen(10)
        threading.Thread(target=accept_clients, daemon=True).start()

        reset_to_initial()

        tick = 0
        while shared_env.running.value:
            # tick in shared memory
            with shared_env.lock:
                shared_env.tick.value = tick

            # ----- UI commands (display->env message queue) -----
            while not display_to_env.empty():
                cmd = display_to_env.get_nowait()
                c = cmd.cmd
                args = cmd.args or {}

                if c == "quit":
                    with shared_env.lock:
                        shared_env.running.value = False
                    break

                if c == "reset":
                    reset_to_initial()

                elif c == "drought_toggle":
                    _toggle_drought(reason="UI")
                    _schedule_next_timer()

                elif c == "drought_on":
                    with shared_env.lock:
                        if not shared_env.drought.value:
                            shared_env.drought.value = True
                            shared_env.grass.value = int(shared_env.grass.value // 2)
                    _log(log_to_display, "Drought ON (UI)")
                    _schedule_next_timer()

                elif c == "drought_off":
                    with shared_env.lock:
                        if shared_env.drought.value:
                            shared_env.drought.value = False
                    _log(log_to_display, "Drought OFF (UI)")
                    _schedule_next_timer()

                elif c == "add_prey":
                    spawn_prey(int(args.get("value", 1)), origin="UI")

                elif c == "add_predator":
                    spawn_predator(int(args.get("value", 1)), origin="UI")

                elif c == "set_grass":
                    val = int(float(args.get("value", 0)))
                    with shared_env.lock:
                        shared_env.grass.value = max(0, min(val, int(config.MAX_GRASS)))
                    _log(log_to_display, f"Grass set to {int(shared_env.grass.value)}")

            # ----- Telemetry from animals -----
            while not energies_to_env.empty():
                msg = energies_to_env.get_nowait()

                if msg[0] == "prey":
                    _, pid, energy, active = msg
                    prey_energy[pid] = float(energy)
                    prey_active[pid] = bool(active)

                elif msg[0] == "predator":
                    _, pid, energy, active = msg
                    pred_energy[pid] = float(energy)

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
                        _log(log_to_display, f"Prey {pid} dead")

                    elif kind == "predator":
                        pred_energy.pop(pid, None)
                        pred_ctrl.pop(pid, None)
                        pred_procs.pop(pid, None)
                        with shared_env.lock:
                            shared_env.predators.value = max(0, int(shared_env.predators.value) - 1)
                        _log(log_to_display, f"Predator {pid} dead")

            # ----- Actions requested by animals -----
            while not events_to_env.empty():
                ev = events_to_env.get_nowait()
                et = ev[0]

                if et == "eat_grass":
                    _, pid, requested = ev
                    requested = max(0, int(requested))
                    with shared_env.lock:
                        granted = min(requested, int(shared_env.grass.value))
                        shared_env.grass.value -= granted

                    if pid in prey_ctrl:
                        try:
                            prey_ctrl[pid].put(("grass_grant", granted))
                        except Exception:
                            pass

                elif et == "hunt":
                    _, pred_pid = ev
                    killed_pid = kill_one_active_prey()
                    success = killed_pid is not None

                    if pred_pid in pred_ctrl:
                        try:
                            pred_ctrl[pred_pid].put(("hunt_result", success))
                        except Exception:
                            pass

                elif et == "spawn_prey":
                    _, n = ev
                    spawn_prey(int(n), origin="reproduction")

                elif et == "spawn_predator":
                    _, n = ev
                    spawn_predator(int(n), origin="reproduction")

            # ----- grass growth (env writes shared memory under lock) -----
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

            # ----- snapshot to display -----
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
            if server_socket:
                server_socket.close()
        except Exception:
            pass

        with shared_env.lock:
            shared_env.running.value = False

        _log(log_to_display, "ENV stopped")
