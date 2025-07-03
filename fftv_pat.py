#!/usr/bin/env python3
"""
RaspiGPT: Injecting terminal chaos + framebuffer bars + lyric bombs.
Refactored to use engine.py - You wanted LIFE? Here's your electric circus.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import subprocess
import os
import random
import colorsys
import shutil
from common.engine import AudioEngine

# === Initialize Engine ===
engine = AudioEngine()
engine.initialize(
    interface_type="focusrite2i4",
    processor_type="default",
    debug=False
)

# === Configuration ===
WIDTH, HEIGHT = 480, 360
FB_PATH = "/dev/fb0"
NUM_BARS = 64
BAR_WIDTH = WIDTH // NUM_BARS

# === State ===
state = {
    "prev_fft": np.zeros(NUM_BARS),
    "prev_silent": True,
    "explosion_timer": 0,
    "lyric_timer": 0,
    "current_lyric": "",
    "current_explosion": "",
    "lyric_color": (255, 255, 255),
    "lyric_x": 10,
    "lyric_y": HEIGHT - 20
}

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

# === Main Loop Function ===
def main_loop(data):
    """Main visualization loop that receives processed audio data from engine"""
    
    # Get processed audio data from engine
    samples = data["samples"]
    is_silent = data["is_silent"]
    engine_fft = data["fft"]  # This is already processed by the engine
    
    # Detect transitions
    just_became_loud = state["prev_silent"] and not is_silent
    state["prev_silent"] = is_silent


    # === Framebuffer render ===
    img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Animated hue shift
    import time
    hue_offset = (time.time() % 10) / 10.0
    for i in range(NUM_BARS):
        bar_height = int(engine_fft[i] * HEIGHT)
        x = i * BAR_WIDTH
        hue = (i / NUM_BARS + hue_offset) % 1.0
        brightness = min(1.0, engine_fft[i] * 1.2)
        color = hsv_to_rgb(hue, 1.0, brightness)
        draw.rectangle((x, HEIGHT - bar_height, x + BAR_WIDTH - 1, HEIGHT), fill=color)

    # === Explosion and Lyric triggers ===
    if just_became_loud:
        state["explosion_timer"] = 10
        state["lyric_timer"] = 60
        state["current_lyric"] = random.choice(lyrics)
        state["current_explosion"] = random.choice(explosions)
        
        try:
            tw, th = draw.textsize(state["current_lyric"], font=FONT)
        except AttributeError:
            # For newer PIL versions
            bbox = draw.textbbox((0, 0), state["current_lyric"], font=FONT)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        
        max_x = max(10, WIDTH - tw - 10)
        state["lyric_x"] = random.randint(10, max_x)
        state["lyric_y"] = random.randint(10, HEIGHT - th - 20)
        state["lyric_color"] = hsv_to_rgb(random.random(), 1, 1)

    if state["explosion_timer"] > 0:
        draw.multiline_text((WIDTH // 8, HEIGHT // 3), state["current_explosion"],
                            fill=(255, 255, 255), font=FONT, spacing=2, align="center")
        state["explosion_timer"] -= 1

    if state["lyric_timer"] > 0:
        draw.text((state["lyric_x"], state["lyric_y"]), state["current_lyric"], 
                 fill=state["lyric_color"], font=FONT)
        state["lyric_timer"] -= 1

    # Write to framebuffer
    buf = rgb888_to_rgb565(img)
    with open(FB_PATH, "rb+") as f:
        for row in range(HEIGHT):
            offset = ((y_offset + row) * FB_WIDTH + x_offset) * 2
            f.seek(offset)
            start = row * WIDTH * 2
            end = start + WIDTH * 2
            f.write(buf[start:end])

    # === Terminal chaos (stdout) ===
    total_energy = data["total_energy"]  # Use engine's normalized energy
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

# === Run Engine ===
if __name__ == "__main__":
    print("[fftv_pat] Starting electric circus with engine...")
    try:
        engine.run(main_loop)
    except KeyboardInterrupt:
        print("\nVisualizer terminated.")
