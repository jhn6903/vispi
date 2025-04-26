import subprocess
import numpy as np
import pyaudio
import time
import random
import os
import colorsys
import curses
from scipy.ndimage import median_filter
from PIL import Image, ImageDraw, ImageFont

# Constants
WIDTH, HEIGHT = 80, 24  # Adjust for terminal size (ASCII-based)
FB_PATH = "/dev/fb0"
TARGET_FPS = 30
NUM_BARS = 40
BAR_WIDTH = WIDTH // NUM_BARS
CHUNK = 1024
RATE = 44100
CHANNELS = 2
INPUT_INDEX = 1
FORMAT = pyaudio.paInt16
NOISE_GATE_THRESHOLD = 0.05
HARD_FLOOR = 0.1
SMOOTHING_FACTOR = 0.15
prev_fft = np.zeros(NUM_BARS)
prev_silent = True
current_lyric = ""
explosion_timer = 0
lyric_timer = 0

# ASCII art for glitchy effect
ascii_art = '''
                       __________________________
               __..--/".'                        '.
       __..--""      | |                          |
      /              | |                          |
     /               | |    ___________________   |
    ;                | |   :__________________/:  |
    |                | |   |                 '.|  |
    |                | |   |                  ||  |
    |                | |   |                  ||  |
    |                | |   |                  ||  |
    |                | |   |                  ||  |
    |                | |   |                  ||  |
    |                | |   |______......-----"\|  |
    |                | |   |_______......-----"   |
    |                | |                          |
    |                | |                          |
    |                | |                  ____----|
    |                | |_____.....----|#######|---|
    |                | |______.....----""""       |
    |                | |                          |
    |. ..            | |   ,                      |
    |... ....        | |  (c ----- """           .'
    |..... ......  |\|_|    ____......------"""|"
    |. .... .......| |""""""                   |
    '... ..... ....| |                         |
      "-._ .....  .| |                         |
          "-._.....| |             ___...---"""'
              "-._.| | ___...---"""
                  """""
'''

# Setup for PyAudio
p = pyaudio.PyAudio()
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    input_device_index=INPUT_INDEX,
    frames_per_buffer=CHUNK
)

# Convert RGB888 to RGB565 for framebuffer
def rgb888_to_rgb565(rgb_img):
    arr = np.array(rgb_img)
    r = (arr[:, :, 0] >> 3).astype(np.uint16)
    g = (arr[:, :, 1] >> 2).astype(np.uint16)
    b = (arr[:, :, 2] >> 3).astype(np.uint16)
    rgb565 = (r << 11) | (g << 5) | b
    return rgb565.flatten().astype(np.uint16).tobytes()

# Detect framebuffer geometry
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

FB_WIDTH, FB_HEIGHT = get_fb_geometry()
x_offset = (FB_WIDTH - WIDTH) // 2
y_offset = (FB_HEIGHT - HEIGHT) // 2

# Convert HSV to RGB for colors
def hsv_to_rgb(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)

# Clear framebuffer
with open(FB_PATH, "wb") as f:
    f.write(b'\x00' * (FB_WIDTH * FB_HEIGHT * 2))

# Terminal visualizer function
def visualizer_main(stdscr):
    curses.curs_set(0)
    stdscr.nodelay(1)
    stdscr.timeout(100)  # Non-blocking delay for refreshing screen

    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]

        is_silent = np.max(np.abs(samples)) < 100
        just_became_loud = prev_silent and not is_silent
        prev_silent = is_silent

        if is_silent:
            fft = np.zeros(NUM_BARS)
        else:
            full_fft = np.abs(np.fft.fft(samples))[:CHUNK // 2]
            focus_bins = full_fft[:int(NUM_BARS * 2/3)]
            fft = np.interp(np.linspace(0, len(focus_bins), NUM_BARS), np.arange(len(focus_bins)), focus_bins)

            # Normalize FFT values
            norm = np.percentile(fft, 98) + 1e-6
            fft = fft / norm
            fft = np.clip(fft * 1.5, 0, 1)
            fft = np.where(fft < NOISE_GATE_THRESHOLD, fft * 0.2, fft)
            fft[fft < HARD_FLOOR] = 0
            fft = np.sqrt(fft)
            fft = median_filter(fft, size=1)

            # Smoothing for visual "roundness"
            for i in range(NUM_BARS):
                if i > 4:
                    fft[i] = SMOOTHING_FACTOR * prev_fft[i] + (1 - SMOOTHING_FACTOR) * fft[i]
            prev_fft = fft.copy()

        # Terminal-based glitchy visualizer
        stdscr.clear()
        stdscr.addstr(0, 0, ascii_art, curses.color_pair(random.randint(1, 8)))

        for i in range(NUM_BARS):
            bar_height = int(fft[i] * HEIGHT)
            hue = i / NUM_BARS  # Color spectrum left to right
            brightness = fft[i]  # Louder = brighter
            color = hsv_to_rgb(hue, 1.0, brightness)
            stdscr.addstr(bar_height, i * BAR_WIDTH, '█', curses.color_pair(random.randint(1, 8)))

        # Explosion logic for chaotic effect
        if just_became_loud:
            stdscr.addstr(random.randint(1, HEIGHT-3), random.randint(0, WIDTH-10), "BOOM!", curses.color_pair(random.randint(1, 8)))

        # Refresh screen and add glitchy randomness
        stdscr.refresh()
        time.sleep(1 / TARGET_FPS)

if __name__ == "__main__":
    curses.wrapper(visualizer_main)
