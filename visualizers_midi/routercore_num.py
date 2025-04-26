#!/usr/bin/env python3
"""
routercore_chaos.py

Interactive terminal + framebuffer audio visualizer for Raspberry Pi 4b.
Use numpad keys (1–9) to spawn effects or adjust parameters:

 1: ↑ glitch text intensity
 2: ↓ glitch text intensity
 3: ↑ pixel noise multiplier
 4: ↓ pixel noise multiplier
 5: Toggle colored stripes
 6: Spawn IP‑flood ASCII burst
 7: Randomize color‑shift speed
 8: Toggle framebuffer freeze
 9: Spawn ASCII explosion

Ctrl+C to exit.
"""
import numpy as np
import pyaudio
import time
import random
import os
import shutil
import colorsys
from scipy.ndimage import median_filter
from PIL import Image, ImageDraw
import sys
import termios
import fcntl
import tty

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

# === Load text + glitch chars ===
with open("/home/vispi2/visualizers/out_there.txt") as f:
    extra_words = [line.strip() for line in f if line.strip()]
glitch_chars = list("!@#$%&*()_-+=<>?;:^")

# === Interactive state ===
glitch_text_intensity = 1.0
pixel_noise_multiplier = 1.0
stripe_enabled = True
color_shift_speed = 0.1
freeze_frame = False

# === Terminal input setup (non‑blocking, raw) ===
fd = sys.stdin.fileno()
old_term = termios.tcgetattr(fd)
tty.setcbreak(fd)
old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)

def print_status(name, value):
    # Show current parameter up top
    sys.stdout.write(f"\033[H\033[2K[STATUS] {name}: {value}\033[0m\n")
    sys.stdout.flush()

def spawn_ip_flood():
    for _ in range(30):
        ip = ".".join(str(random.randint(0,255)) for _ in range(4))
        port = random.randint(1000,9999)
        glitch = ''.join(random.choice(glitch_chars) for _ in range(random.randint(3,6)))
        line = f"[FLOOD] {ip}:{port} [{glitch}]"
        c = random.randint(0, max(0, cols - len(line)))
        r = random.randint(1, rows - 2)
        sys.stdout.write(f"\033[{r};{c}H\033[1;31m{line}\033[0m")
    sys.stdout.flush()

def spawn_explosion():
    for _ in range(10):
        pat = random.choice(["BOOM","KABOOM","BLAST","POW","!!!"])
        line = f"[{pat}]"
        c = random.randint(0, max(0, cols - len(line)))
        r = random.randint(1, rows - 2)
        sys.stdout.write(f"\033[{r};{c}H\033[1;33m{line}\033[0m")
    sys.stdout.flush()

def handle_key(ch):
    global glitch_text_intensity, pixel_noise_multiplier
    global stripe_enabled, color_shift_speed, freeze_frame

    if ch == '1':
        glitch_text_intensity = min(glitch_text_intensity + 0.5, 10)
        print_status("Glitch intensity", glitch_text_intensity)
    elif ch == '2':
        glitch_text_intensity = max(glitch_text_intensity - 0.5, 0)
        print_status("Glitch intensity", glitch_text_intensity)
    elif ch == '3':
        pixel_noise_multiplier = min(pixel_noise_multiplier + 0.2, 5)
        print_status("Pixel noise ×", pixel_noise_multiplier)
    elif ch == '4':
        pixel_noise_multiplier = max(pixel_noise_multiplier - 0.2, 0.1)
        print_status("Pixel noise ×", pixel_noise_multiplier)
    elif ch == '5':
        stripe_enabled = not stripe_enabled
        print_status("Stripes enabled", stripe_enabled)
    elif ch == '6':
        spawn_ip_flood()
    elif ch == '7':
        color_shift_speed = random.uniform(0.05, 0.5)
        print_status("Color speed", f"{color_shift_speed:.2f}")
    elif ch == '8':
        freeze_frame = not freeze_frame
        print_status("Freeze frame", freeze_frame)
    elif ch == '9':
        spawn_explosion()

# === Setup audio stream ===
p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=INPUT_INDEX,
                frames_per_buffer=CHUNK)

prev_fft = np.zeros(NUM_BARS)

try:
    while True:
        # — Keyboard input —
        try:
            ch = sys.stdin.read(1)
        except (OSError, IOError):
            ch = None
        if ch in '123456789':
            handle_key(ch)

        # — Read audio & FFT —
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]
        is_silent = np.max(np.abs(samples)) < NOISE_GATE

        if is_silent:
            fft = np.zeros(NUM_BARS)
        else:
            full_fft = np.abs(np.fft.fft(samples))[:CHUNK//2]
            focus = full_fft[:int(NUM_BARS*2/3)]
            fft = np.interp(np.linspace(0,len(focus),NUM_BARS),
                            np.arange(len(focus)), focus)
            fft /= (np.percentile(fft,98)+1e-6)
            fft = np.clip(fft*1.5, 0,1)
            fft = np.where(fft<0.05, fft*0.1, fft)
            fft[fft<0.08] = 0
            fft = np.sqrt(fft)
            fft = median_filter(fft, size=1)
            fft = 0.3*prev_fft + 0.7*fft
            prev_fft = fft.copy()

        energy = np.mean(fft)

        # — ASCII terminal chaos —
        sys.stdout.write("\033[2J\033[H")  # clear
        count = int(random.randint(10,20) * glitch_text_intensity)
        for _ in range(count):
            ip = ".".join(str(random.randint(0,255)) for _ in range(4))
            port = random.randint(1000,9999)
            glitch = ''.join(random.choice(glitch_chars)
                             for _ in range(random.randint(3,7)))
            word = random.choice(extra_words) if random.random()<0.5 else ""
            line = f"[+] Detected {ip}:{port} {word} [{glitch}]"
            c = random.randint(0, max(0, cols - len(line)))
            r = random.randint(1, rows - 2)
            color = random.randint(1,6)
            sys.stdout.write(f"\033[{r};{c}H\033[9{color}m{line}\033[0m")
        sys.stdout.flush()

        # — Visual corruption to framebuffer —
        img = Image.new("RGB", (WIDTH, HEIGHT), (0,0,0))
        draw = ImageDraw.Draw(img)

        for _ in range(int(energy * 300 * pixel_noise_multiplier)):
            x = random.randint(0, WIDTH-1)
            y = random.randint(0, HEIGHT-1)
            hue = (time.time()*color_shift_speed + x*0.01) % 1.0
            col = hsv_to_rgb(hue, 1, random.uniform(0.5,1))
            draw.point((x,y), fill=col)

        if stripe_enabled and random.random() < energy*0.6:
            y = random.randint(0, HEIGHT-1)
            col = hsv_to_rgb(random.random(),1,1)
            draw.line((0,y,WIDTH,y), fill=col)

        if not freeze_frame:
            buf = rgb888_to_rgb565(img)
            with open(FB_PATH, "rb+") as fb:
                for row in range(HEIGHT):
                    off = ((y_offset+row)*FB_WIDTH + x_offset)*2
                    fb.seek(off)
                    start = row*WIDTH*2
                    fb.write(buf[start:start+WIDTH*2])

        time.sleep(1/30)

except KeyboardInterrupt:
    pass

finally:
    # restore terminal + audio
    termios.tcsetattr(fd, termios.TCSAFLUSH, old_term)
    fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)
    print("\033[0m\nVisualizer stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
