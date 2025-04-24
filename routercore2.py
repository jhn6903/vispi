import numpy as np
import pyaudio
import time
import random
import shutil
import os
from scipy.ndimage import median_filter

# === Terminal ===
def get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))

cols, rows = get_terminal_size()
grid = [[" " for _ in range(cols)] for _ in range(rows)]
age = [[0 for _ in range(cols)] for _ in range(rows)]

chars = list("▁▂▃▄▅▆▇█▒░▓#@$%&|=~:. ")  # fade effect from dense to empty
colors = [f"\033[9{c}m" for c in range(1, 7)]
RESET = "\033[0m"

# === Text Inject ===
with open("/home/vispi/visualizers/out_there.txt") as f:
    words = [w.strip() for w in f if w.strip()]

def pick_char(energy):
    if random.random() < 0.05:
        return random.choice(words)
    if energy > 0.6:
        return random.choice(chars[:8])
    elif energy > 0.3:
        return random.choice(chars[4:12])
    else:
        return random.choice(chars[10:])

# === Audio ===
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = 1

p = pyaudio.PyAudio()
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    input_device_index=INPUT_INDEX,
    frames_per_buffer=CHUNK
)

prev_fft = np.zeros(64)

# === Text Event State ===
text_event_timer = 0
text_event_lines = []
TEXT_EVENT_DURATION = 20  # frames
TEXT_EVENT_COOLDOWN = 100
text_event_cooldown = 0

# === Main Loop ===
try:
    while True:
        # Audio
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]
        if np.max(np.abs(samples)) < 100:
            fft = np.zeros(64)
        else:
            full_fft = np.abs(np.fft.fft(samples))[:CHUNK // 2]
            focus = full_fft[:64]
            fft = np.interp(np.linspace(0, len(focus), 64), np.arange(len(focus)), focus)
            fft = fft / (np.percentile(fft, 98) + 1e-6)
            fft = np.clip(np.sqrt(fft), 0, 1)
            fft = median_filter(fft, size=1)
            fft = 0.3 * prev_fft + 0.7 * fft
            prev_fft = fft.copy()

        energy = np.mean(fft)
        density = int(energy * 300)

        # === Possibly trigger a text event ===
        if energy > 0.5 and random.random() < 0.05 and text_event_timer == 0 and text_event_cooldown == 0:
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
        print("\033[2J\033[H", end="")

        for y in range(rows - 1):
            line = ""
            for x in range(cols):
                fade_level = age[y][x]
                if fade_level > 0:
                    color = "\033[97m"  # mostly white
                    if random.random() < 0.02:
                        color = random.choice(colors)
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

        time.sleep(1 / 30)

except KeyboardInterrupt:
    print("\033[0m\n[voidcore] Terminated.")
    stream.stop_stream()
    stream.close()
    p.terminate()
