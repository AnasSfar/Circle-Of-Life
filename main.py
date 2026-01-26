# main.py

import multiprocessing
import time

import config
from shared_env import SharedEnv
from env import run_env
from web_display import run_web_display

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
        name="ENV",
    )
    try:
        env_p.start()
    except Exception as e:
        print("ENV failed to start:", repr(e))
        raise

    # DISPLAY (web)
    disp_p = multiprocessing.Process(
        target=run_web_display,
        args=(env_to_display, display_to_env, log_to_display, "127.0.0.1", config.WEB_PORT),
        daemon=False,
        name="DISPLAY",
    )
    try:
        disp_p.start()
        time.sleep(0.3)
        print("AFTER START:")
        print("  ENV    alive:", env_p.is_alive(), "exitcode:", env_p.exitcode)
        print("  DISPLAY alive:", disp_p.is_alive(), "exitcode:", disp_p.exitcode)

    except Exception as e:
        print("DISPLAY failed to start:", repr(e))
        # stop env if display cannot start
        try:
            with shared_env.lock:
                shared_env.running.value = False
        except Exception:
            pass
        raise

    print(f"Open: http://127.0.0.1:{config.WEB_PORT}")

    try:
        while True:
            time.sleep(0.5)
            if not env_p.is_alive():
                print(f"ENV died (exitcode={env_p.exitcode})")
                break
            if not disp_p.is_alive():
                print(f"DISPLAY died (exitcode={disp_p.exitcode})")
                break
    except KeyboardInterrupt:
        pass
    finally:
        try:
            with shared_env.lock:
                shared_env.running.value = False
        except Exception:
            pass

        try:
            if getattr(env_p, "_popen", None) is not None:
                env_p.join(timeout=2)
        except Exception:
            pass

        try:
            if getattr(disp_p, "_popen", None) is not None:
                disp_p.join(timeout=2)
        except Exception:
            pass


if __name__ == "__main__":
    main()
