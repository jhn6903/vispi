import numpy as np
import pyaudio
import time
import random
import shutil
import os
import curses
import threading
import sys
import json
import select
import termios
import tty
from scipy.ndimage import median_filter, gaussian_filter1d
from vis_config import config

# === Status monitoring ===
STATUS_FILE = "/tmp/routercore2_status.json"

def update_status(status_dict):
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(status_dict, f)
    except Exception as e:
        print(f"Error updating status: {e}", file=sys.stderr)

# === Terminal ===
def get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))

# Check if we're running via SSH
SSH_SESSION = 'SSH_CLIENT' in os.environ

# If running via SSH, redirect output to a log file
if SSH_SESSION:
    LOG_FILE = "/tmp/routercore2.log"
    sys.stdout = open(LOG_FILE, 'w', buffering=1)  # Line buffering
    sys.stderr = sys.stdout

cols, rows = get_terminal_size()
grid = [[" " for _ in range(cols)] for _ in range(rows)]
age = [[0 for _ in range(cols)] for _ in range(rows)]

# More varied character set for different energy levels
chars_high = list("█▇▆▅▄▃▂▁")  # High energy (solid blocks)
chars_med = list("◢◣◤◥■□▣▤▥▦▧▨▩")  # Medium energy (geometric shapes)
chars_low = list(".:·˙°⋅⊙⊚○◌◍◎●")  # Low energy (dots and circles)

# Enhanced color palette
colors = [
    "\033[38;5;{}m".format(c) for c in [
        51,   # Cyan
        45,   # Light blue
        39,   # Blue
        33,   # Deep blue
        198,  # Pink
        199,  # Light magenta
        171,  # Purple
        213,  # Light pink
        226,  # Yellow
        154,  # Light green
        148,  # Green
        184,  # Light yellow
        208,  # Orange
    ]
]

RESET = "\033[0m"

# === Text Inject ===
with open("/home/vispi2/visualizers/out_there.txt") as f:
    words = [w.strip() for w in f if w.strip()]

def pick_char(energy):
    if random.random() < 0.05 * config.settings['intensity']:
        return random.choice(words)
    
    # More nuanced character selection based on energy
    if energy > 0.7:
        return random.choice(chars_high)
    elif energy > 0.4:
        return random.choice(chars_med)
    else:
        return random.choice(chars_low)

class MenuThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.running = True
        
    def run(self):
        if SSH_SESSION:
            # Don't run menu in SSH session
            while self.running:
                time.sleep(0.1)
            return
            
        def menu_loop(stdscr):
            curses.start_color()
            curses.use_default_colors()
            selected_item = 0
            
            while self.running:
                if config.paused:
                    menu = config.draw_menu(stdscr)
                    key = menu.getch()
                    
                    if key == 27:  # ESC
                        config.paused = False
                        config.save_settings()
                    else:
                        selected_item = config.handle_menu_input(key, selected_item)
                else:
                    time.sleep(0.1)
        
        try:
            curses.wrapper(menu_loop)
        except Exception as e:
            print(f"Menu error: {e}", file=sys.stderr)

# === Audio Setup ===
def find_input_device():
    p = pyaudio.PyAudio()
    try:
        default_input = p.get_default_input_device_info()
        status = {"default_device": default_input['name']}
        update_status(status)
        
        # Try to find a device with input channels
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            if dev['maxInputChannels'] > 0:
                status["selected_device"] = f"{dev['name']} (index {i})"
                update_status(status)
                return i
        
        # Fall back to default input device
        return default_input['index']
    except Exception as e:
        status = {"error": f"Error finding input device: {e}"}
        update_status(status)
        raise

# === Audio ===
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = find_input_device()

try:
    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=INPUT_INDEX,
        frames_per_buffer=CHUNK
    )
except Exception as e:
    print(f"Error opening audio stream: {e}")
    print("Available audio devices:")
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        print(f"  Device {i}: {dev['name']} (in: {dev['maxInputChannels']}, out: {dev['maxOutputChannels']})")
    sys.exit(1)

prev_fft = np.zeros(64)

# === Text Event State ===
text_event_timer = 0
text_event_lines = []
TEXT_EVENT_DURATION = 20  # frames
TEXT_EVENT_COOLDOWN = 100
text_event_cooldown = 0

# === Main Loop ===
try:
    # Clear status file
    if os.path.exists(STATUS_FILE):
        os.remove(STATUS_FILE)
    
    update_status({"state": "starting"})
    
    menu_thread = MenuThread()
    menu_thread.start()
    
    # Set up raw mode for terminal
    if not SSH_SESSION:
        old_settings = termios.tcgetattr(sys.stdin)
        tty.setraw(sys.stdin.fileno(), termios.TCSANOW)
    
    update_status({"state": "running", "mode": "SSH" if SSH_SESSION else "local"})
    
    while True:
        try:
            # Check for pause toggle (only in local session) using non-blocking select
            if not SSH_SESSION:
                rlist, _, _ = select.select([sys.stdin], [], [], 0)
                if rlist:
                    char = sys.stdin.read(1)
                if char == 'p':
                    config.paused = not config.paused
                    print(f"Visualizer {'paused' if config.paused else 'resumed'}")
            
            if config.paused and not SSH_SESSION:
                time.sleep(0.1)
                continue
            
            # Audio processing
            data = stream.read(CHUNK, exception_on_overflow=False)
            samples = np.frombuffer(data, dtype=np.int16)[::2]
            if np.max(np.abs(samples)) < config.settings['noise_gate']:
                fft = np.zeros(64)
            else:
                full_fft = np.abs(np.fft.fft(samples))[:CHUNK // 2]
                # Enhanced FFT processing for cleaner waveforms
                focus = full_fft[:128]  # Increased frequency resolution
                fft = np.interp(np.linspace(0, len(focus), 64), np.arange(len(focus)), focus)
                fft = fft / (np.percentile(fft, 95) + 1e-6)  # Adjusted normalization
                fft = np.clip(np.power(fft, 0.7) * config.settings['sensitivity'], 0, 1)  # Softer curve
                fft = gaussian_filter1d(fft, sigma=1.2)  # Gaussian smoothing for more natural transitions
                fft = median_filter(fft, size=3)  # Remove spurious peaks
                fft = config.settings['smoothing'] * prev_fft + (1 - config.settings['smoothing']) * fft
                prev_fft = fft.copy()

            energy = np.mean(fft)
            density = int(energy * 300 * config.settings['intensity'])

            # === Possibly trigger a text event ===
            if energy > 0.5 and random.random() < 0.05 * config.settings['intensity'] and text_event_timer == 0 and text_event_cooldown == 0:
                text_event_lines = random.sample(words, k=min(10, len(words)))
                text_event_timer = TEXT_EVENT_DURATION
                text_event_cooldown = TEXT_EVENT_COOLDOWN

            # === Fade existing grid ===
            for y in range(rows):
                for x in range(cols):
                    if age[y][x] > 0:
                        age[y][x] -= 1
                        if age[y][x] == 0:
                            grid[y][x] = " "

            # === Spawn new elements ===
            for _ in range(density):
                x = random.randint(0, cols - 1)
                y = random.randint(0, rows - 2)
                val = pick_char(energy)
                grid[y][x] = val
                age[y][x] = random.randint(4, 12)

            # === Draw ===
            if not SSH_SESSION:
                print("\033[2J\033[H", end="")

            for y in range(rows - 1):
                line = ""
                for x in range(cols):
                    fade_level = age[y][x]
                    if fade_level > 0:
                        # More sophisticated color selection based on position and energy
                        color_index = (x + y + int(time.time() * 5)) % len(colors)
                        if random.random() < 0.3:  # Increased color variation
                            color = colors[color_index]
                        else:
                            color = "\033[97m"  # White
                        symbol = str(grid[y][x])[0]
                        line += f"{color}{symbol}{RESET}"
                    else:
                        line += " "
                print(line)

            # === Draw scrolling text event ===
            if text_event_timer > 0:
                start_line = rows - int((text_event_timer / TEXT_EVENT_DURATION) * rows)
                for i, txt in enumerate(text_event_lines):
                    y = start_line + i
                    if 0 <= y < rows - 1:
                        padding = (cols - len(txt)) // 2
                        print(f"\033[{y};{max(0, padding)}H\033[97m{txt[:cols]}\033[0m")
                text_event_timer -= 1
            elif text_event_cooldown > 0:
                text_event_cooldown -= 1

            # Update status periodically
            if random.random() < 0.1:  # Update roughly every 10 frames
                status = {
                    "state": "running",
                    "mode": "SSH" if SSH_SESSION else "local",
                    "paused": config.paused,
                    "energy": float(energy),
                    "settings": config.settings
                }
                update_status(status)

            if SSH_SESSION:
                sys.stdout.flush()
            time.sleep(1 / 30)

        except Exception as e:
            update_status({"state": "error", "error": str(e)})
            raise

except KeyboardInterrupt:
    update_status({"state": "terminated", "reason": "keyboard interrupt"})
except Exception as e:
    update_status({"state": "error", "error": str(e)})
finally:
    # Restore terminal settings
    if not SSH_SESSION:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    menu_thread.running = False
    menu_thread.join()
    stream.stop_stream()
    stream.close()
    p.terminate()
    if SSH_SESSION:
        sys.stdout.close()
