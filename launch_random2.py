#!/usr/bin/env python3
'''
Launcher that runs visualizer scripts from ~/visualizers in random mode,
switching at intervals, with manual override via left/right arrows.
After MANUAL_TIMEOUT seconds without manual keypress, returns to random mode.
Press 'q' to quit.
'''
import os
import sys
import subprocess
import time
import random
import signal
import termios
import tty
import select

# Config
VISUALIZER_DIR = os.path.expanduser('~/visualizers')
SWITCH_INTERVAL = 12  # seconds between random mode checks
SWITCH_CHANCE = 0.65  # chance to switch at each interval
MANUAL_TIMEOUT = 60   # seconds to wait before reverting to random mode
LOGFILE = '/tmp/vis_launcher.log'

# Logging
def log(msg):
    timestamp = time.strftime('[%Y-%m-%d %H:%M:%S]')
    with open(LOGFILE, 'a') as f:
        f.write(f'{timestamp} {msg}\n')
    print(f'{timestamp} {msg}', flush=True)

# Read a single keypress (including arrows)
def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch1 = sys.stdin.read(1)
        if ch1 == '\x1b':
            ch2 = sys.stdin.read(1)
            if ch2 == '[':
                ch3 = sys.stdin.read(1)
                return ch1 + ch2 + ch3
            return ch1 + ch2
        return ch1
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

# Launch and track process
current_proc = None
def launch(script):
    global current_proc
    # Terminate previous
    if current_proc and current_proc.poll() is None:
        try:
            os.killpg(os.getpgid(current_proc.pid), signal.SIGTERM)
        except Exception:
            pass
    script_path = os.path.join(VISUALIZER_DIR, script)
    log(f'Launching: {script}')
    proc = subprocess.Popen(['python3', script_path], preexec_fn=os.setsid)
    current_proc = proc
    return proc

# Cleanup on exit
def cleanup(signum=None, frame=None):
    log('Exiting launcher')
    if current_proc and current_proc.poll() is None:
        try:
            os.killpg(os.getpgid(current_proc.pid), signal.SIGTERM)
        except Exception:
            pass
    sys.exit(0)

signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

# Load scripts
if not os.path.isdir(VISUALIZER_DIR):
    print(f'Directory not found: {VISUALIZER_DIR}')
    sys.exit(1)

scripts = sorted([f for f in os.listdir(VISUALIZER_DIR) if f.endswith('.py')])
if not scripts:
    print(f'No .py scripts in {VISUALIZER_DIR}')
    sys.exit(1)

# State
mode = 'random'
last_interaction = time.time()
next_switch = time.time() + SWITCH_INTERVAL
current_idx = random.randrange(len(scripts))
launch(scripts[current_idx])
log('Entering random mode')
print('Use ◄ ► to switch manually; q to quit.')

# Main loop
while True:
    now = time.time()
    if mode == 'random':
        timeout = max(0, next_switch - now)
    else:
        timeout = max(0, (last_interaction + MANUAL_TIMEOUT) - now)

    rlist, _, _ = select.select([sys.stdin], [], [], timeout)
    if rlist:
        key = get_key()
        if key == '\x1b[C':  # right arrow
            current_idx = (current_idx + 1) % len(scripts)
            launch(scripts[current_idx])
            mode = 'manual'
            last_interaction = time.time()
            log('Switched manually to next')
        elif key == '\x1b[D':  # left arrow
            current_idx = (current_idx - 1) % len(scripts)
            launch(scripts[current_idx])
            mode = 'manual'
            last_interaction = time.time()
            log('Switched manually to previous')
        elif key in ('q', 'Q', '\x03'):  # q or Ctrl-C
            cleanup()
    else:
        # Timeout
        now = time.time()
        if mode == 'random' and now >= next_switch:
            if random.random() < SWITCH_CHANCE:
                # pick a different random index
                choices = [i for i in range(len(scripts)) if i != current_idx]
                current_idx = random.choice(choices)
                launch(scripts[current_idx])
                log('Randomly switched')
            else:
                log('Holding current script')
            next_switch = now + SWITCH_INTERVAL
        elif mode == 'manual' and (now - last_interaction) >= MANUAL_TIMEOUT:
            log('No interaction for 60s; returning to random mode')
            mode = 'random'
            next_switch = time.time() + SWITCH_INTERVAL
