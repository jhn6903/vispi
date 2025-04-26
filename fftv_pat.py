# RaspiGPT: Injecting terminal chaos + framebuffer bars + lyric bombs.
# You wanted LIFE? Here's your electric circus.

import numpy as np
import pyaudio
from PIL import Image, ImageDraw, ImageFont
import time
import subprocess
import os
import random
import colorsys
import shutil
from scipy.ndimage import median_filter

WIDTH, HEIGHT = 480, 360
FB_PATH = "/dev/fb0"
TARGET_FPS = 30
NUM_BARS = 64
BAR_WIDTH = WIDTH // NUM_BARS
CHUNK = 1024
RATE = 44100
CHANNELS = 2
INPUT_INDEX = 1
FORMAT = pyaudio.paInt16

NOISE_GATE = 100
prev_fft = np.zeros(NUM_BARS)
prev_silent = True
explosion_timer = 0
lyric_timer = 0
current_lyric = ""
current_explosion = ""
lyric_color = (255, 255, 255)
lyric_x, lyric_y = 10, HEIGHT - 20

# === Terminal chaos stuff ===
def term_size():
    return shutil.get_terminal_size(fallback=(80, 24))

cols, rows = term_size()
term_symbols = list("~!@#$%^&*()_+=-▌▐▒░█▓▄▀▁▂▃▅▆")

# === Load font ===
try:
    FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 14)
except:
    FONT = ImageFont.load_default()

# === Lyrics ===
with open("out_there.txt", "r") as f:
    lyrics = [line.strip() for line in f if line.strip()]

# === Explosions ===
explosions = [
    r""" * @@@ * \|/ ZZZAP /|\ * @@@ * """,
    r"""[B00M]  \\ ^_^ //  === ||| === """,
    r"""!! KRAKK !! <O> /|\ <O> !!""",
    r"""[#######] ~BLAST~ `=======`""",
    r"""...STATIC...///|||\\\...ZZZ..."""
]

# === Framebuffer setup ===
def get_fb_geometry():
    try:
        output = subprocess.check_output("fbset -s", shell=True).decode()
        for line in output.splitlines():
            if "geometry" in line:
                parts = line.split()
                return int(parts[1]), int(parts[2])
    except:
        return WIDTH, HEIGHT
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

# === Audio ===
p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=INPUT_INDEX,
                frames_per_buffer=CHUNK)

# === Clear framebuffer
# with open(FB_PATH, "wb") as f:
#     f.write(b'\x00' * (FB_WIDTH * FB_HEIGHT * 2))

# === Main loop ===
try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]
        is_silent = np.max(np.abs(samples)) < NOISE_GATE
        just_became_loud = prev_silent and not is_silent
        prev_silent = is_silent

        if is_silent:
            fft = np.zeros(NUM_BARS)
        else:
            full_fft = np.abs(np.fft.fft(samples))[:CHUNK // 2]
            focus_bins = full_fft[:int(NUM_BARS * 2/3)]
            fft = np.interp(np.linspace(0, len(focus_bins), NUM_BARS), np.arange(len(focus_bins)), focus_bins)
            fft = fft / (np.percentile(fft, 98) + 1e-6)
            fft = np.clip(fft * 1.5, 0, 1)
            fft = np.where(fft < 0.05, fft * 0.2, fft)
            fft[fft < 0.1] = 0
            fft = np.sqrt(fft)
            fft = median_filter(fft, size=1)

            for i in range(NUM_BARS):
                if i > 4:
                    fft[i] = 0.3 * prev_fft[i] + 0.7 * fft[i]
            prev_fft = fft.copy()

        # === Framebuffer render ===
        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        hue_offset = (time.time() % 10) / 10.0
        for i in range(NUM_BARS):
            bar_height = int(fft[i] * HEIGHT)
            x = i * BAR_WIDTH
            hue = (i / NUM_BARS + hue_offset) % 1.0
            brightness = min(1.0, fft[i] * 1.2)
            color = hsv_to_rgb(hue, 1.0, brightness)
            draw.rectangle((x, HEIGHT - bar_height, x + BAR_WIDTH - 1, HEIGHT), fill=color)

        # === Explosion and Lyric triggers ===
        if just_became_loud:
            explosion_timer = 10
            lyric_timer = 60
            current_lyric = random.choice(lyrics)
            current_explosion = random.choice(explosions)
            tw, th = draw.textsize(current_lyric, font=FONT)
            max_x = max(10, WIDTH - tw - 10)
            lyric_x = random.randint(10, max_x)
            lyric_y = random.randint(10, HEIGHT - th - 20)
            lyric_color = hsv_to_rgb(random.random(), 1, 1)

        if explosion_timer > 0:
            draw.multiline_text((WIDTH // 8, HEIGHT // 3), current_explosion,
                                fill=(255, 255, 255), font=FONT, spacing=2, align="center")
            explosion_timer -= 1

        if lyric_timer > 0:
            draw.text((lyric_x, lyric_y), current_lyric, fill=lyric_color, font=FONT)
            lyric_timer -= 1

        buf = rgb888_to_rgb565(img)
        with open(FB_PATH, "rb+") as f:
            for row in range(HEIGHT):
                offset = ((y_offset + row) * FB_WIDTH + x_offset) * 2
                f.seek(offset)
                start = row * WIDTH * 2
                end = start + WIDTH * 2
                f.write(buf[start:end])

        # === Terminal chaos (stdout) ===
        total_energy = np.mean(fft)
        if total_energy > 0.15:
            for _ in range(int(total_energy * 100)):
                x = random.randint(0, cols - 1)
                y = random.randint(1, rows - 3)
                char = random.choice(term_symbols)
                color = f"\033[9{random.randint(1, 7)}m"
                print(f"\033[{y};{x}H{color}{char}\033[0m", end='')

        # === ASCII waveform ===
        wave = samples[::len(samples) // cols][:cols]
        norm_wave = np.interp(wave, (-30000, 30000), (0, 7)).astype(int)
        wave_chars = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
        print("\033[%d;0H" % (rows - 2), end='')
        for idx in norm_wave:
            print(f"\033[92m{wave_chars[idx]}\033[0m", end='')
        print("\033[0m")

        time.sleep(1 / TARGET_FPS)

except KeyboardInterrupt:
    stream.stop_stream()
    stream.close()
    p.terminate()
    print("\nVisualizer terminated.")
