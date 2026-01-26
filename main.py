# main.py
# Starts:
#  - env process
#  - display (web) process
# Predators/Preys are processes (individuals). They join env via socket handshake.

import multiprocessing
import time

import config
from shared_env import SharedEnv
from env import run_env
from web_display import run_web_display
from ipc import create_shared_state, create_queues



def main():
    multiprocessing.set_start_method("spawn", force=True)

    shared_env = SharedEnv()

    env_to_display = multiprocessing.Queue()
    display_to_env = multiprocessing.Queue()
    log_to_display = multiprocessing.Queue()

    energies_to_env = multiprocessing.Queue()
    events_to_env = multiprocessing.Queue()

    # ENV
    env_p = multiprocessing.Process(
        target=run_env,
        args=(shared_env, env_to_display, display_to_env, energies_to_env, events_to_env, log_to_display),
        daemon=False,
    )
    env_p.start()

    # DISPLAY (web)
    disp_p = multiprocessing.Process(
        target=run_web_display,
        args=(env_to_display, display_to_env, log_to_display, "127.0.0.1", 8000),
        daemon=False,
    )
    disp_p.start()

    print("Open: http://127.0.0.1:8000")

    try:
        while env_p.is_alive() and disp_p.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            with shared_env.lock:
                shared_env.running.value = False
        except Exception:
            pass
        try:
            env_p.join(timeout=2)
        except Exception:
            pass
        try:
            disp_p.join(timeout=2)
        except Exception:
            pass


if __name__ == "__main__":
    main()
