# env.py

import time
import socket
import threading
import multiprocessing
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


def run_env(shared_state, env_to_display, display_to_env, energies_to_env, events_to_env, log_to_display):
    tick = 0
    server_socket = None

    prey_procs = {}
    pred_procs = {}
    prey_ctrl = {}
    pred_ctrl = {}

    prey_energy = {}
    pred_energy = {}
    prey_active = {}

    def reset_to_initial():
        nonlocal tick
        tick = 0
        shared_state["tick"] = 0
        shared_state["grass"] = float(config.INITIAL_GRASS)
        shared_state["drought"] = False

        _log(log_to_display, "🔄 Reset: retour à l'état initial (0 proie, 0 prédateur)")

        # ask all animals to die
        for q in prey_ctrl.values():
            try:
                q.put(("die",))
            except Exception:
                pass
        for q in pred_ctrl.values():
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

        shared_state["preys"] = 0
        shared_state["predators"] = 0

    def spawn_prey(n: int, origin: str = "UI"):
        if n <= 0:
            return
        can_add = max(0, config.MAX_PREYS - int(shared_state["preys"]))
        n = min(int(n), can_add)
        if n <= 0:
            _log(log_to_display, f"🐇 Ajout proies refusé: limite MAX_PREYS={config.MAX_PREYS}")
            return

        for _ in range(n):
            ctrl_q = multiprocessing.Queue()
            p = multiprocessing.Process(target=run_prey, args=(energies_to_env, events_to_env, ctrl_q))
            p.start()
            prey_procs[p.pid] = p
            prey_ctrl[p.pid] = ctrl_q
            shared_state["preys"] += 1

        _log(log_to_display, f"🐇 Ajout: +{n} proie(s) ({origin})")

    def spawn_predator(n: int, origin: str = "UI"):
        if n <= 0:
            return
        can_add = max(0, config.MAX_PREDATORS - int(shared_state["predators"]))
        n = min(int(n), can_add)
        if n <= 0:
            _log(log_to_display, f"🦁 Ajout prédateurs refusé: limite MAX_PREDATORS={config.MAX_PREDATORS}")
            return

        for _ in range(n):
            ctrl_q = multiprocessing.Queue()
            p = multiprocessing.Process(target=run_predator, args=(energies_to_env, events_to_env, ctrl_q))
            p.start()
            pred_procs[p.pid] = p
            pred_ctrl[p.pid] = ctrl_q
            shared_state["predators"] += 1

        _log(log_to_display, f"🦁 Ajout: +{n} prédateur(s) ({origin})")

    def kill_one_active_prey():
        # kill one active prey (rule: only active preys can be predated)
        for pid, active in list(prey_active.items()):
            if active and pid in prey_ctrl:
                try:
                    prey_ctrl[pid].put(("die",))
                    return pid
                except Exception:
                    return None
        return None

    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((config.ENV_HOST, config.ENV_PORT))
        server_socket.listen(10)

        def accept_clients():
            while shared_state["running"]:
                try:
                    c, _ = server_socket.accept()
                    c.close()
                except Exception:
                    break

        threading.Thread(target=accept_clients, daemon=True).start()

        reset_to_initial()

        while shared_state["running"]:
            shared_state["tick"] = tick

            # ====== COMMANDES UI ======
            while not display_to_env.empty():
                cmd = display_to_env.get_nowait()
                c = cmd.cmd
                args = cmd.args or {}

                if c in ("reset", "quit"):
                    reset_to_initial()

                elif c == "drought_on":
                    if not shared_state["drought"]:
                        shared_state["drought"] = True
                        shared_state["grass"] = shared_state["grass"] / 2.0
                        _log(log_to_display, "🌵 Sécheresse activée: herbe divisée par 2")

                elif c == "drought_off":
                    if shared_state["drought"]:
                        shared_state["drought"] = False
                        _log(log_to_display, "🌱 Sécheresse désactivée: retour normal")

                elif c == "add_prey":
                    spawn_prey(int(args.get("value", 1)), origin="UI")

                elif c == "add_predator":
                    spawn_predator(int(args.get("value", 1)), origin="UI")

                elif c == "set_grass":
                    val = float(args.get("value", shared_state["grass"]))
                    shared_state["grass"] = max(0.0, min(val, float(config.MAX_GRASS)))
                    _log(log_to_display, f"🌿 Herbe fixée à {int(shared_state['grass'])}")

                elif c == "add_grass":
                    delta = float(args.get("value", 0))
                    shared_state["grass"] = max(0.0, min(shared_state["grass"] + delta, float(config.MAX_GRASS)))
                    _log(log_to_display, f"🌿 Herbe ajoutée: +{int(delta)} (total {int(shared_state['grass'])})")

            # ====== TÉLÉMÉTRIE ======
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
                        prey_energy.pop(pid, None)
                        prey_active.pop(pid, None)
                        prey_ctrl.pop(pid, None)
                        prey_procs.pop(pid, None)
                        shared_state["preys"] = max(0, int(shared_state["preys"]) - 1)
                        _log(log_to_display, f"☠️ Proie {pid} morte")

                    elif kind == "predator":
                        pred_energy.pop(pid, None)
                        pred_ctrl.pop(pid, None)
                        pred_procs.pop(pid, None)
                        shared_state["predators"] = max(0, int(shared_state["predators"]) - 1)
                        _log(log_to_display, f"☠️ Prédateur {pid} mort")

            # ====== ACTIONS (décisions réelles ici) ======
            while not events_to_env.empty():
                ev = events_to_env.get_nowait()
                et = ev[0]

                if et == "eat_grass":
                    _, pid, requested = ev
                    requested = max(0, int(requested))
                    granted = min(requested, int(shared_state["grass"]))
                    shared_state["grass"] -= granted

                    if pid in prey_ctrl:
                        try:
                            prey_ctrl[pid].put(("grass_grant", granted))
                        except Exception:
                            pass

                    if granted > 0:
                        _log(log_to_display, f"🐇 Proie {pid} mange {granted} herbe(s)")
                    else:
                        _log(log_to_display, f"🐇 Proie {pid} veut manger mais il n'y a plus d'herbe")

                elif et == "hunt":
                    _, pid = ev
                    killed_pid = kill_one_active_prey()
                    success = killed_pid is not None

                    if pid in pred_ctrl:
                        try:
                            pred_ctrl[pid].put(("hunt_result", success))
                        except Exception:
                            pass

                    if success:
                        _log(log_to_display, f"🦁 Prédateur {pid} mange une proie (pid {killed_pid})")
                    else:
                        _log(log_to_display, f"🦁 Prédateur {pid} chasse mais échoue (pas de proie active)")

                elif et == "spawn_prey":
                    _, n = ev
                    spawn_prey(int(n), origin="reproduction")
                    _log(log_to_display, f"🐇 Reproduction: +{int(n)} proie(s)")

                elif et == "spawn_predator":
                    _, n = ev
                    spawn_predator(int(n), origin="reproduction")
                    _log(log_to_display, f"🦁 Reproduction: +{int(n)} prédateur(s)")

            # ====== CROISSANCE DE L’HERBE ======
            if not shared_state["drought"]:
                shared_state["grass"] += config.GRASS_GROWTH_PER_TICK
            else:
                shared_state["grass"] += config.GRASS_GROWTH_PER_TICK * config.DROUGHT_GRASS_FACTOR

            shared_state["grass"] = min(shared_state["grass"], float(config.MAX_GRASS))
            shared_state["grass"] = max(shared_state["grass"], 0.0)

            # ====== SNAPSHOT ======
            snapshot = Snapshot(
                tick=tick,
                predators=int(shared_state["predators"]),
                preys=int(shared_state["preys"]),
                grass=int(shared_state["grass"]),
                drought=bool(shared_state["drought"]),
                prey_energy_stats=_energy_stats(list(prey_energy.values())),
                predator_energy_stats=_energy_stats(list(pred_energy.values())),
            )
            env_to_display.put(snapshot)

            tick += 1
            time.sleep(config.TICK_DURATION)

    finally:
        if server_socket:
            try:
                server_socket.close()
            except Exception:
                pass
        shared_state["running"] = False
        _log(log_to_display, "🛑 ENV arrêté")
        print("ENV arrêté")
