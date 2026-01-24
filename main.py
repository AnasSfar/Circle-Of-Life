# main.py

import multiprocessing
from ipc import create_shared_state, create_queues
from env import run_env
from web_display import run_web_display


def main():
    manager, shared_state = create_shared_state()
    env_to_display, display_to_env, energies_to_env, events_to_env, log_to_display = create_queues()

    env_proc = multiprocessing.Process(
        target=run_env,
        args=(shared_state, env_to_display, display_to_env, energies_to_env, events_to_env, log_to_display),
    )
    env_proc.start()

    web_proc = multiprocessing.Process(
        target=run_web_display,
        args=(shared_state, env_to_display, display_to_env, log_to_display, "127.0.0.1", 8000),
    )
    web_proc.start()

    try:
        env_proc.join()
        web_proc.join()
    except KeyboardInterrupt:
        shared_state["running"] = False
        env_proc.join(timeout=2)
        web_proc.join(timeout=2)

    print("Simulation terminée.")


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn", force=True)
    main()
