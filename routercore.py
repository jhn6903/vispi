import numpy as np
import pyaudio
import time
import random
import os
import shutil
import colorsys
from scipy.ndimage import median_filter
from PIL import Image, ImageDraw

# === Audio config ===
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = 1
NUM_BARS = 64
NOISE_GATE = 100

# === Terminal / Framebuffer ===
WIDTH, HEIGHT = 480, 360
FB_PATH = "/dev/fb0"

def get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))

cols, rows = get_terminal_size()

# === Framebuffer helpers ===
def get_fb_geometry():
    try:
        out = os.popen("fbset -s").read()
        for line in out.splitlines():
            if "geometry" in line:
                parts = line.split()
                return int(parts[1]), int(parts[2])
    except:
        pass
    return WIDTH, HEIGHT

def rgb888_to_rgb565(rgb_img):
    arr = np.array(rgb_img)
    r = (arr[:, :, 0] >> 3).astype(np.uint16)
    g = (arr[:, :, 1] >> 2).astype(np.uint16)
    b = (arr[:, :, 2] >> 3).astype(np.uint16)
    return ((r << 11) | (g << 5) | b).flatten().astype(np.uint16).tobytes()

def hsv_to_rgb(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)

FB_WIDTH, FB_HEIGHT = get_fb_geometry()
x_offset = (FB_WIDTH - WIDTH) // 2
y_offset = (FB_HEIGHT - HEIGHT) // 2

# === Load text pool ===
with open("/home/vispi/visualizers/out_there.txt") as f:
    extra_words = [line.strip() for line in f if line.strip()]
glitch_chars = list("!@#$%&*()_-+=<>?;:^")

# === Audio stream ===
p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=INPUT_INDEX,
                frames_per_buffer=CHUNK)

prev_fft = np.zeros(NUM_BARS)

# === Begin chaos ===
try:
    while True:
        # --- Read audio ---
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]
        is_silent = np.max(np.abs(samples)) < NOISE_GATE

        # --- FFT ---
        if is_silent:
            fft = np.zeros(NUM_BARS)
        else:
            full_fft = np.abs(np.fft.fft(samples))[:CHUNK // 2]
            focus = full_fft[:int(NUM_BARS * 2/3)]
            fft = np.interp(np.linspace(0, len(focus), NUM_BARS), np.arange(len(focus)), focus)
            fft = fft / (np.percentile(fft, 98) + 1e-6)
            fft = np.clip(fft * 1.5, 0, 1)
            fft = np.where(fft < 0.05, fft * 0.1, fft)
            fft[fft < 0.08] = 0
            fft = np.sqrt(fft)
            fft = median_filter(fft, size=1)
            fft = 0.3 * prev_fft + 0.7 * fft
            prev_fft = fft.copy()

        energy = np.mean(fft)

        # --- ASCII terminal chaos ---
        print("\033[2J\033[H", end="")  # Clear screen

        for _ in range(random.randint(10, 20)):
            ip = ".".join(str(random.randint(0, 255)) for _ in range(4))
            port = random.randint(1000, 9999)
            glitch = ''.join(random.choice(glitch_chars) for _ in range(random.randint(3, 7)))
            word = random.choice(extra_words) if random.random() < 0.5 else ""
            line = f"[+] Detected {ip}:{port} {word} [{glitch}]"
            col = random.randint(0, max(0, cols - len(line)))
            row = random.randint(1, rows - 2)
            print(f"\033[{row};{col}H\033[9{random.randint(1,6)}m{line}\033[0m")

        # --- Visual corruption to framebuffer ---
        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        for _ in range(int(energy * 300)):
            x = random.randint(0, WIDTH - 1)
            y = random.randint(0, HEIGHT - 1)
            hue = (time.time() * 0.1 + x * 0.01) % 1.0
            color = hsv_to_rgb(hue, 1, random.uniform(0.5, 1))
            draw.point((x, y), fill=color)

        # Occasional colored stripe, like interference
        if random.random() < energy * 0.6:
            y = random.randint(0, HEIGHT - 1)
            color = hsv_to_rgb(random.random(), 1, 1)
            draw.line((0, y, WIDTH, y), fill=color)

        # Write to framebuffer
        buf = rgb888_to_rgb565(img)
        with open(FB_PATH, "rb+") as f:
            for row in range(HEIGHT):
                offset = ((y_offset + row) * FB_WIDTH + x_offset) * 2
                f.seek(offset)
                start = row * WIDTH * 2
                end = start + WIDTH * 2
                f.write(buf[start:end])

        time.sleep(1 / 30)

except KeyboardInterrupt:
    print("\033[0m\nVisualizer stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
