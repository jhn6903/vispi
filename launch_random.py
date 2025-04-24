import subprocess
import time
import random
import os
import signal
import sys

# === Init Log ===
LOGFILE = "/tmp/vis_log.txt"
def log(msg):
    timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
    with open(LOGFILE, "a") as f:
        f.write(f"{timestamp} {msg}\n")
    print(f"{timestamp} {msg}", flush=True)

log("Launch script started")

# === Config ===
VISUALIZER_DIR = "/home/vispi/visualizers"
VISUALIZERS = [
    "bilbo.py",
    "pat2.py",
    "fftv_pat.py",
    "routercore.py",
    "routercore2.py",
    "routercore3.py",
    "routercore4.py"
]
SWITCH_INTERVAL = 12
SWITCH_CHANCE = 0.65

# === Detect if visualizer is terminal-based ===
def is_terminal_visualizer(script):
    return any(term in script for term in [
        "fftv_pat"
    ])

# === Launch visualizer ===
def launch(script):
    path = os.path.join(VISUALIZER_DIR, script)
    log(f"Launching visualizer: {script}")

    try:
        if is_terminal_visualizer(script):
            return subprocess.Popen(
                ["python3", path],
                stdout=open("/dev/tty1", "w"),
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
        else:
            return subprocess.Popen(
                ["python3", path],
                preexec_fn=os.setsid
            )
    except Exception as e:
        log(f"Error launching {script}: {e}")
        return None

# === Controller Loop ===
try:
    current_script = random.choice(VISUALIZERS)
    current_proc = launch(current_script)

    while True:
        time.sleep(SWITCH_INTERVAL)

        if current_proc and current_proc.poll() is not None:
            log(f"Visualizer {current_script} exited unexpectedly.")
            current_script = random.choice(VISUALIZERS)
            current_proc = launch(current_script)
            continue

        if random.random() < SWITCH_CHANCE:
            log(f"Switching visualizer...")

            if current_proc:
                os.killpg(os.getpgid(current_proc.pid), signal.SIGTERM)

            next_script = random.choice([v for v in VISUALIZERS if v != current_script])
            current_proc = launch(next_script)
            current_script = next_script
        else:
            log(f"Holding current visualizer: {current_script}")

except KeyboardInterrupt:
    log("Visualizer controller interrupted by keyboard.")
    if current_proc:
        os.killpg(os.getpgid(current_proc.pid), signal.SIGTERM)

except Exception as e:
    log(f"Unhandled error: {e}")
    if current_proc:
        os.killpg(os.getpgid(current_proc.pid), signal.SIGTERM)

