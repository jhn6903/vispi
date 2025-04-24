import subprocess
import numpy as np
import pyaudio
import time
import random
import shutil
import os
from scipy.ndimage import median_filter

# === Terminal
def get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))

cols, rows = get_terminal_size()
canvas = [[" " for _ in range(cols)] for _ in range(rows)]
age = [[0 for _ in range(cols)] for _ in range(rows)]
max_age = 20

chars = list("░▒▓█@#%&$+=~:;,. ")  # glitchy decay set
colors = [f"\033[9{c}m" for c in range(1, 7)]
RESET = "\033[0m"

# === Load Lyrics
with open("/home/vispi/visualizers/out_there.txt") as f:
    lines = [line.strip() for line in f if line.strip()]
line_index = 0

# === Audio
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

# === Draw functions

def draw_waveform(samples):
    try:
        fb = open("/dev/fb0", "rb+")
        fb_width, fb_height = get_fb_geometry()
        fb_center_y = fb_height // 2

        # Boosted downsampling
        step = max(1, len(samples) // fb_width)
        wave = samples[::step][:fb_width]
        # Amplify the waveform visually
        norm = np.interp(wave, (-15000, 15000), (fb_center_y - 40, fb_center_y + 40)).astype(int)

        for x in range(len(norm)):
            y = norm[x]
            if 0 <= y < fb_height:
                offset = (y * fb_width + x) * 2
                fb.seek(offset)
                # Randomize color slightly (glitchy white)
                white_pixel = random.choice([b'\xff\xff', b'\xf8\xf8', b'\xfc\xfc'])
                fb.write(white_pixel)

                # Optional trailing line (above or below for glow/fade feel)
                if random.random() < 0.2:
                    trail_y = y + random.choice([-1, 1])
                    if 0 <= trail_y < fb_height:
                        offset_trail = (trail_y * fb_width + x) * 2
                        fb.seek(offset_trail)
                        fb.write(b'\x88\x88')  # Dim white

                if np.max(np.abs(samples)) > 5000:
                    for _ in range(20):
                        rand_x = random.randint(0, fb_width - 1)
                        rand_y = random.randint(0, fb_height - 1)
                        fb.seek((rand_y * fb_width + rand_x) * 2)
                        fb.write(random.choice([b'\xff\x00', b'\x00\xff', b'\x1f\xff']))  # Red, Blue, Magenta

        fb.close()
    except Exception as e:
        pass  # Silent failure

def get_fb_geometry():
    try:
        out = subprocess.check_output("fbset -s", shell=True).decode()
        for line in out.splitlines():
            if "geometry" in line:
                parts = line.split()
                return int(parts[1]), int(parts[2])
    except:
        return (320, 240)  # Default fallback

def draw_line(text, x, y, color):
    for i, char in enumerate(text):
        if 0 <= x + i < cols and 0 <= y < rows:
            canvas[y][x + i] = f"{color}{char}{RESET}"
            age[y][x + i] = max_age

def decay_canvas():
    for y in range(rows):
        for x in range(cols):
            if age[y][x] > 0:
                age[y][x] -= 1
                if age[y][x] == 0:
                    canvas[y][x] = " "
                elif random.random() < 0.02:
                    canvas[y][x] = random.choice(chars)

def render():
    print("\033[2J\033[H", end="")
    for y in range(rows - 1):
        line = ""
        for x in range(cols):
            cell = canvas[y][x]
            line += cell
        print(line)
    print(RESET, end="")

# === Main Loop
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

        # === Paint with sound
        if energy > 0.15 and random.random() < energy:
            line = lines[line_index % len(lines)]
            line_index += 1

            # Position based on energy profile
            length = min(len(line), cols - 2)
            x = random.randint(0, cols - length)
            y = random.randint(0, rows - 2)

            color_chance = random.random()
            if color_chance < 0.9:
                color = "\033[97m"  # Mostly white
            else:
                color = random.choice(colors)

            draw_line(line[:length], x, y, color)

        # === Glitch injection
        if energy > 0.3 and random.random() < 0.05:
            for _ in range(3):
                gx = random.randint(0, cols - 1)
                gy = random.randint(0, rows - 2)
                canvas[gy][gx] = random.choice(chars)
                age[gy][gx] = random.randint(3, max_age)

        decay_canvas()
        render()
        draw_waveform(samples)
        time.sleep(1 / 30)

except KeyboardInterrupt:
    print("\033[0m\n[lyric_canvas] Terminated.")
    stream.stop_stream()
    stream.close()
    p.terminate()
