#!/usr/bin/env python3
import subprocess
import time
import random
import os
import signal
import sys
from common.config import supported_visualizers

# Interval settings (in seconds)
MIN_INTERVAL = 5
MAX_INTERVAL = 60

# === Launcher ===
def launch(script_name):
    path = os.path.join(SCRIPT_DIR, script_name)
    log(f"Launching: {script_name}")
    # Launch in its own process group
    proc = subprocess.Popen([sys.executable, path], preexec_fn=os.setsid)
    return proc

# === Main Controller ===
def main():
    random.seed()
    current_proc = None
    current_script = None
    try:
        while True:
            next_script = random.choice(VISUALIZERS)
            if next_script != current_script:
                if current_proc:
                    log(f"Stopping: {current_script}")
                    os.killpg(os.getpgid(current_proc.pid), signal.SIGTERM)
                current_proc = launch(next_script)
                current_script = next_script
            else:
                log(f"Keeping current: {current_script}")
            sleep_time = random.uniform(MIN_INTERVAL, MAX_INTERVAL)
            log(f"Next switch in {sleep_time:.1f}s")
            time.sleep(sleep_time)
    except KeyboardInterrupt:
        log("Interrupted by user, shutting down.")
        if current_proc:
            os.killpg(os.getpgid(current_proc.pid), signal.SIGTERM)
    except Exception as e:
        log(f"Error occurred: {e}")
        if current_proc:
            os.killpg(os.getpgid(current_proc.pid), signal.SIGTERM)

if __name__ == '__main__':
    log("Visualizer controller started")
    if not VISUALIZERS:
        log("No visualizer scripts found in folder.")
        sys.exit(1)
    main()
