import numpy as np
import pyaudio
from PIL import Image, ImageDraw
import time
from scipy.ndimage import median_filter
import subprocess

import colorsys

def hsv_to_rgb(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return int(r * 255), int(g * 255), int(b * 255)

# Constants
WIDTH, HEIGHT = 320, 240
FB_PATH = "/dev/fb0"
TARGET_FPS = 30
NUM_BARS = 64
BAR_WIDTH = WIDTH // NUM_BARS

CHUNK = 1024
RATE = 44100
CHANNELS = 2
input_device_index = 1
FORMAT = pyaudio.paInt16

NOISE_GATE_THRESHOLD = 0.05
HARD_FLOOR = 0.1
SMOOTHING_FACTOR = 0.5
prev_fft = np.zeros(NUM_BARS)

# PyAudio setup
p = pyaudio.PyAudio()
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    input_device_index=input_device_index,  # Behringer device index
    frames_per_buffer=CHUNK
)

# Framebuffer conversion
def rgb888_to_rgb565(rgb_img):
    arr = np.array(rgb_img)
    r = (arr[:, :, 0] >> 3).astype(np.uint16)
    g = (arr[:, :, 1] >> 2).astype(np.uint16)
    b = (arr[:, :, 2] >> 3).astype(np.uint16)
    rgb565 = (r << 11) | (g << 5) | b
    return rgb565.flatten().astype(np.uint16).tobytes()

# Detect framebuffer size
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

# Clear framebuffer
with open(FB_PATH, "wb") as f:
    f.write(b'\x00' * (FB_WIDTH * FB_HEIGHT * 2))

# Main loop
try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]  # Left channel only

        # Silence detection — skip everything if signal is quiet
        if np.max(np.abs(samples)) < 100:
            fft = np.zeros(NUM_BARS)
        else:
            # FFT
            full_fft = np.abs(np.fft.fft(samples))[:CHUNK // 2]
            focus_bins = full_fft[:int(NUM_BARS * 2/3)]
            fft = np.interp(np.linspace(0, len(focus_bins), NUM_BARS), np.arange(len(focus_bins)), focus_bins)

            # Normalize using percentile to reduce domination by single bins
            norm = np.percentile(fft, 98) + 1e-6
            fft = fft / norm
            fft = np.clip(fft, 0, 1)

            # Boost quiet signals slightly
            fft *= 1.5
            fft = np.clip(fft, 0, 1)

            # Gate and floor
            fft = np.where(fft < NOISE_GATE_THRESHOLD, fft * 0.2, fft)
            fft[fft < HARD_FLOOR] = 0

            # Compress dynamic range (makes bass less overpowering)
            fft = np.sqrt(fft)

            # Median filter to clean noise spikes
            fft = median_filter(fft, size=1)

            # Selective smoothing (skip kick bins)
            for i in range(NUM_BARS):
                if i > 4:
                    fft[i] = SMOOTHING_FACTOR * prev_fft[i] + (1 - SMOOTHING_FACTOR) * fft[i]
            prev_fft = fft.copy()

            # Spread low-end across neighboring bins for visual "roundness"
            fft[1] = (fft[0] + fft[1] + fft[2]) / 3
            fft[2] = (fft[1] + fft[2] + fft[3]) / 3
            fft[3] = (fft[2] + fft[3] + fft[4]) / 3

            # Kick compression for dynamic breathing
            kick_energy = np.mean(fft[:4])
            squash_factor = 1 - np.clip(kick_energy * 0.3, 0, 0.15)
            for i in range(8, NUM_BARS):
                fft[i] *= squash_factor

        # Optional debug output
        # print(np.round(fft[:10], 2))

        # Draw bars
        img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        for i in range(NUM_BARS):
            bar_height = int(fft[i] * HEIGHT)
            x = i * BAR_WIDTH

            hue = i / NUM_BARS  # spectrum left to right
            brightness = fft[i]  # louder = brighter
            color = hsv_to_rgb(hue, 1.0, brightness)

            draw.rectangle((x, HEIGHT - bar_height, x + BAR_WIDTH - 1, HEIGHT), fill=color)


        # Write to framebuffer
        buf = rgb888_to_rgb565(img)
        with open(FB_PATH, "rb+") as f:
            for row in range(HEIGHT):
                offset = ((y_offset + row) * FB_WIDTH + x_offset) * 2
                f.seek(offset)
                start = row * WIDTH * 2
                end = start + WIDTH * 2
                f.write(buf[start:end])

        # ASCII terminal bars (optional debug overlay)
        ascii_bar = ''.join(['█' if val > 0.7 else
                     '▓' if val > 0.5 else
                     '▒' if val > 0.3 else
                     '░' if val > 0.1 else
                     ' ' for val in fft])
        print(ascii_bar)

        time.sleep(1 / TARGET_FPS)

except KeyboardInterrupt:
    stream.stop_stream()
    stream.close()
    p.terminate()
    print("\nVisualizer stopped.")
