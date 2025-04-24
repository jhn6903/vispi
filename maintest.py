#!/usr/bin/env python3
"""
pi-visualizer/main.py

High‑intensity, low‑lag terminal + framebuffer audio visualizer.
Features:
- Vertical bars composed of whole words or glitch symbols
- Ultra‑sensitive spectral scaling for transients
- Dynamic color mapping per bar (green→yellow→red→magenta→cyan)
- Background noise flicker for analog chaos
- Peak dB history on right
- Frameless, single‑buffer rendering for minimal lag
"""
import sys, time, random, subprocess, shutil, os
import numpy as np
import pyaudio
from scipy.ndimage import median_filter
from PIL import Image, ImageDraw
import colorsys

# === Config ===
CHUNK, RATE = 1024, 44100
CHANNELS, FORMAT = 2, pyaudio.paInt16
INPUT_INDEX = 1
NUM_BARS = 64
SMOOTHING = 0.4           # lower smoothing = more reactive
SENSITIVITY = 3.0        # amplify spectral levels
FPS = 30
DELAY = 1.0 / FPS
MAX_INT16 = 32768.0

# Framebuffer image size & path
WIDTH, HEIGHT = 480, 360
FB_PATH = '/dev/fb0'

# Terminal geometry
GEO = shutil.get_terminal_size(fallback=(80, 24))
ROWS, COLS = GEO.lines, GEO.columns
MAX_H = ROWS - 1
HIST_SZ = MAX_H

# Load word pool
lyric_file = os.path.expanduser('~/visualizers/out_there.txt')
if not os.path.exists(lyric_file): lyric_file = 'out_there.txt'
LYRICS = []
with open(lyric_file) as f:
    for line in f:
        LYRICS += [w for w in line.strip().split() if w]
if not LYRICS: LYRICS = ['NOISE','BASS','BEAT','GLITCH']
GLITCH = list("~*!#@$%&+=:;?")
POOL = LYRICS + GLITCH

# === Audio ===
class AudioEngine:
    def __init__(self):
        pa = pyaudio.PyAudio()
        self.stream = pa.open(format=FORMAT, channels=CHANNELS,
                              rate=RATE, input=True,
                              input_device_index=INPUT_INDEX,
                              frames_per_buffer=CHUNK)
    def read(self):
        data = self.stream.read(CHUNK, exception_on_overflow=False)
        return np.frombuffer(data, np.int16)[::CHANNELS]

# === Spectrum ===
def compute_spectrum(samples, prev):
    fft = np.abs(np.fft.rfft(samples))
    focus = fft[:len(fft)*2//3]
    bars = np.interp(np.linspace(0, len(focus), NUM_BARS),
                     np.arange(len(focus)), focus)
    bars *= SENSITIVITY
    p98 = np.percentile(bars, 97) + 1e-6
    norm = np.clip(bars / p98, 0, 1)
    comp = norm ** 0.5
    filt = median_filter(comp, 1)
    return SMOOTHING * prev + (1 - SMOOTHING) * filt

# === Terminal Renderer ===
class TerminalRenderer:
    def __init__(self):
        self.peak_hist = []
    def render(self, spec, peak_db):
        # update peak history
        self.peak_hist.insert(0, f"{peak_db:5.1f}dB")
        if len(self.peak_hist) > HIST_SZ:
            self.peak_hist.pop()
        # clear once per frame
        print("\033[2J\033[H", end='')
        # draw bars
        for i, v in enumerate(spec):
            h = int(v * MAX_H)
            x = i + 1
            # background flicker for analog chaos
            if random.random() < v * 0.2:
                print(f"\033[{MAX_H//2};{x}H\033[90m·\033[0m", end='')
            for y in range(MAX_H):
                row = MAX_H - y
                if y < h:
                    word = random.choice(POOL)
                    # color mapping: green→yellow→red→magenta→cyan
                    cidx = min(int(v * 5), 4)
                    color_codes = [32, 33, 31, 35, 36]
                    color = color_codes[cidx]
                    print(f"\033[{row};{x}H\033[{color}m{word}\033[0m", end='')
                else:
                    print(f"\033[{row};{x}H ", end='')
        # draw peak history on right
        px = NUM_BARS + 3
        for idx, t in enumerate(self.peak_hist):
            print(f"\033[{idx+1};{px}H{t}", end='')
        # reset cursor
        print(f"\033[{ROWS};1H", end='')
        sys.stdout.flush()

# === Framebuffer Renderer ===
class FramebufferRenderer:
    def __init__(self):
        out = subprocess.getoutput('fbset -s')
        self.fb_w, self.fb_h = WIDTH, HEIGHT
        for l in out.splitlines():
            if 'geometry' in l:
                parts = l.split()
                self.fb_w, self.fb_h = int(parts[1]), int(parts[2])
        self.x_off = (self.fb_w - WIDTH) // 2
        self.y_off = (self.fb_h - HEIGHT) // 2
    def render(self, spec):
        img = Image.new('RGB', (WIDTH, HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        hueoff = (time.time() % 5) / 5
        bw = WIDTH / NUM_BARS
        for i, v in enumerate(spec):
            h = int(v * HEIGHT)
            hue = (i / NUM_BARS + hueoff) % 1.0
            col = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, 1.0, v))
            x0 = i * bw
            x1 = x0 + bw - 1
            draw.rectangle((x0, HEIGHT - h, x1, HEIGHT), fill=col)
        buf = self._to565(img)
        with open(FB_PATH, 'rb+') as fb:
            for r in range(HEIGHT):
                off = ((self.y_off + r) * self.fb_w + self.x_off) * 2
                fb.seek(off)
                fb.write(buf[r*WIDTH*2:(r+1)*WIDTH*2])
    def _to565(self, img):
        arr = np.array(img)
        r = (arr[:, :, 0] >> 3).astype(np.uint16)
        g = (arr[:, :, 1] >> 2).astype(np.uint16)
        b = (arr[:, :, 2] >> 3).astype(np.uint16)
        fb = (r << 11) | (g << 5) | b
        return fb.flatten().astype(np.uint16).tobytes()

# === Main ===
def main():
    audio = AudioEngine()
    term = TerminalRenderer()
    fb = FramebufferRenderer()
    prev = np.zeros(NUM_BARS)
    use_fb = '--fb' in sys.argv
    try:
        while True:
            samples = audio.read()
            peak = np.max(np.abs(samples)) / MAX_INT16
            peak_db = 20 * np.log10(peak + 1e-6)
            spec = compute_spectrum(samples, prev)
            prev = spec
            if use_fb:
                fb.render(spec)
            else:
                term.render(spec, peak_db)
            time.sleep(DELAY)
    except KeyboardInterrupt:
        print("\nExiting")

if __name__ == '__main__':
    main()
