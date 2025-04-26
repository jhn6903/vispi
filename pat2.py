import numpy as np
import pyaudio
import random
import time
import sys
import shutil
import os
from scipy.ndimage import median_filter

# === AUDIO CONFIG ===
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = 1  # Behringer

# === TERMINAL SETUP ===
def get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))

cols, rows = get_terminal_size()

# === COLOR SETUP ===
colors = [
    "\033[91m", "\033[92m", "\033[93m",
    "\033[94m", "\033[95m", "\033[96m"
]
RESET = "\033[0m"

# === PROJECT PAT EASTER EGG ===
pat_sprite = [
    r"   _____   ",
    r"  /     \  ",
    r" | () () | ",
    r"  \  ^  /  ",
    r"   |||||   ",
    r"   |||||   ",
]

# === EXPLOSIONS (multiple styles) ===
explosions = [
    [  # radial
        r"   .   ",
        r"  . .  ",
        r"   .   "
    ],
    [
        r"   o   ",
        r"  o o  ",
        r"   o   "
    ],
    [
        r" \ o / ",
        r"-  O  -",
        r" / o \ "
    ],
    [
        r" \ | / ",
        r"-- * --",
        r" / | \ "
    ],
    [
        r"  ***  ",
        r" ***** ",
        r"  ***  "
    ],
    [
        r"   *   ",
        r"  .*.  ",
        r"   *   "
    ],
    [  # glitch style
        r" ░▓▒░▒▓ ",
        r" ▒█▌█▒ ",
        r" ▓▒░▓▒ ",
    ]
]

glitch_chars = ['~', '*', '#', '@', '%', '=', '+', '^', '&', '▓', '▒', '░', '▐', '▌']

# === LOAD LYRICS ===
with open("out_there.txt", "r") as f:
    full_lyrics = [line.strip() for line in f if line.strip()]
all_words = " ".join(full_lyrics).split()
word_index = 0

# === AUDIO SETUP ===
p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=INPUT_INDEX,
                frames_per_buffer=CHUNK)

prev_fft = np.zeros(64)
SMOOTHING = 0.5

# === WORD DROP STATE ===
class WordDrop:
    def __init__(self, text, x, y, color, scroll_dir=None):
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.jitter = 0
        self.scroll_dir = scroll_dir

active_words = []

# === EXPLOSION STATE ===
explosion_active = False
explosion_frame = 0
explosion_delay = 0
explosion_pos = (0, 0)
explosion_color = random.choice(colors)

# === PAT GHOST ===
pat_timer = 0
pat_pos = (0, 0)

# === MAIN LOOP ===
try:
    while True:
        # AUDIO INPUT
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]
        is_silent = np.max(np.abs(samples)) < 100

        if is_silent:
            print("\033[2J\033[H", end="")
            active_words.clear()
            explosion_active = False
            pat_timer = 0
            sys.stdout.flush()
            time.sleep(1 / 30)
            continue

        # FFT ANALYSIS
        fft = np.abs(np.fft.fft(samples))[:64]
        fft = median_filter(fft, size=3)
        fft = fft / (np.max(fft) + 1e-6)
        fft = SMOOTHING * prev_fft + (1 - SMOOTHING) * fft
        prev_fft = fft.copy()
        low_energy = np.mean(fft[:8])
        high_energy = np.mean(fft[32:])
        total_energy = np.mean(fft)

        # SCREEN CLEAR
        print("\033[2J\033[H", end="")

        # SPAWN WORDS
        word_density = int(total_energy * 15) + 2
        for _ in range(word_density):
            word = all_words[word_index % len(all_words)]
            word_index += 1
            x = random.randint(0, max(0, cols - len(word)))
            y = random.randint(1, rows - 2)
            color = random.choice(colors)
            scroll_dir = random.choice([None, "left", "right"]) if total_energy > 0.3 else None
            wd = WordDrop(word, x, y, color, scroll_dir)
            wd.jitter = int(fft[random.randint(0, 8)] * 2)
            active_words.append(wd)

        # MOVE & DRAW WORDS
        for wd in active_words[-200:]:
            if wd.scroll_dir == "left":
                wd.x -= 1
            elif wd.scroll_dir == "right":
                wd.x += 1
            wd.x = max(0, min(cols - len(wd.text), wd.x))
            jitter_x = wd.x + random.randint(-wd.jitter, wd.jitter)
            jitter_y = wd.y + random.randint(-wd.jitter, wd.jitter)
            jitter_x = max(0, min(cols - len(wd.text), jitter_x))
            jitter_y = max(1, min(rows - 2, jitter_y))
            print(f"\033[{jitter_y};{jitter_x}H{wd.color}{wd.text}{RESET}")

        # EXPLOSIONS
        if not explosion_active and low_energy > 0.4 and random.random() < total_energy:
            explosion_active = True
            explosion_frame = 0
            explosion_delay = 3
            explosion_color = random.choice(colors)
            explosion_pos = (
                random.randint(5, max(5, cols - 10)),
                random.randint(2, max(2, rows - 5))
            )

        if explosion_active:
            if explosion_frame < len(explosions):
                frame = explosions[explosion_frame]
                x, y = explosion_pos
                for i, line in enumerate(frame):
                    if 0 <= y + i < rows:
                        print(f"\033[{y+i};{x}H{explosion_color}{line}{RESET}")
                explosion_delay -= 1
                if explosion_delay <= 0:
                    explosion_frame += 1
                    explosion_delay = 3
            else:
                explosion_active = False

        # GLITCH PARTICLES
        if high_energy > 0.2:
            for _ in range(int(high_energy * 25)):
                gx = random.randint(0, cols - 1)
                gy = random.randint(1, rows - 1)
                char = random.choice(glitch_chars)
                color = random.choice(colors)
                print(f"\033[{gy};{gx}H{color}{char}{RESET}")

        # COLOR PULSE STRIPES
        if low_energy > 0.6:
            bg_color = random.choice(colors)
            for y in range(1, rows - 1, 3):
                line = bg_color + " " * cols + RESET
                print(f"\033[{y};0H{line}")

        # PROJECT PAT GHOST (rare)
        if pat_timer == 0 and total_energy > 0.5 and random.random() < 0.03:
            pat_pos = (random.randint(3, cols - 15), random.randint(3, rows - 8))
            pat_timer = 10

        if pat_timer > 0:
            px, py = pat_pos
            for i, line in enumerate(pat_sprite):
                if 0 <= py + i < rows:
                    print(f"\033[{py+i};{px}H\033[95m{line}{RESET}")
            pat_timer -= 1

        sys.stdout.flush()
        time.sleep(1 / 30)

except KeyboardInterrupt:
    print(RESET)
    print("\nVisualizer stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
