#!/usr/bin/env python3
"""
voidcore_vis_v2.py

Enhanced terminal audio visualizer with interactive numpad controls:

 1: Increase spawn density multiplier
 2: Decrease spawn density multiplier
 3: Increase fade duration (slower decay)
 4: Decrease fade duration (faster decay)
 5: Toggle rainbow flicker
 6: Trigger instant text event
 7: Randomize character palette
 8: Adjust text scroll speed
 9: Toggle inverted brightness mode
 0: Show this HELP overlay

Ctrl+C to quit.
"""
import os
import numpy as np
import pyaudio
import time
import random
import shutil
import sys
import termios
import fcntl
import tty
from scipy.ndimage import median_filter

# === Terminal Geometry ===
def get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))
cols, rows = get_terminal_size()
rows -= 1  # leave room

# === Load word list & char palettes ===
with open("/home/vispi2/visualizers/out_there.txt") as f:
    words = [w.strip() for w in f if w.strip()]

# Two palettes: block gradients and ASCII chaos
palettes = [
    list("▁▂▃▄▅▆▇█▒░▓#@$%&|=~:. "),
    list("abcdefghijklmnopqrstuvwxyz0123456789<>?!*")
]
palette = palettes[0]

# === Audio setup ===
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = 1

p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=INPUT_INDEX,
                frames_per_buffer=CHUNK)

prev_fft = np.zeros(64)

# === Simulation state ===
spawn_mult = 1.0
fade_dur = 6        # base age frames
rainbow = True
text_scroll_speed = 1.0
invert = False
char_palette = 0

# Text event
TEXT_DUR = 20
TEXT_COOLDOWN = 80
text_timer = 0
text_cool = 0
text_lines = []

# Grid buffers
grid = [[" "]*cols for _ in range(rows)]
age  = [[0]*cols for _ in range(rows)]

# === Terminal input setup ===
fd = sys.stdin.fileno()
old_term = termios.tcgetattr(fd)
tty.setcbreak(fd)
old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)

def restore_terminal():
    termios.tcsetattr(fd, termios.TCSAFLUSH, old_term)
    fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)

def draw_help():
    box_w = min(50, cols-4)
    box_h = 12
    x0 = (cols - box_w)//2
    y0 = (rows - box_h)//2
    lines = [
        "voidcore_vis_v2.py HELP",
        "",
        "1: ↑ density   2: ↓ density",
        "3: ↑ fade time 4: ↓ fade time",
        "5: Toggle rainbow flicker",
        "6: Instant text event",
        "7: Randomize palette",
        "8: Adjust scroll speed",
        "9: Toggle invert mode",
        "0: Show HELP",
        "",
        "Press any key to continue..."
    ]
    sys.stdout.write("\033[2J")
    for i, ln in enumerate(lines):
        y = y0 + i
        x = x0 + (box_w - len(ln))//2
        sys.stdout.write(f"\033[{y};{x}H\033[1;37m{ln}\033[0m")
    sys.stdout.flush()

# === Key handling ===
def handle_key(ch):
    global spawn_mult, fade_dur, rainbow
    global text_timer, text_cool, palettes, palette
    global text_scroll_speed, invert, char_palette

    if ch == '1':
        spawn_mult = min(spawn_mult + 0.2, 5.0)
    elif ch == '2':
        spawn_mult = max(spawn_mult - 0.2, 0.2)
    elif ch == '3':
        fade_dur = min(fade_dur + 2, 20)
    elif ch == '4':
        fade_dur = max(fade_dur - 2, 2)
    elif ch == '5':
        rainbow = not rainbow
    elif ch == '6':
        trigger_text_event()
    elif ch == '7':
        char_palette = 1 - char_palette
        palette[:] = palettes[char_palette]
    elif ch == '8':
        text_scroll_speed = round(random.uniform(0.5, 2.0), 2)
    elif ch == '9':
        invert = not invert
    elif ch == '0':
        draw_help()
        # wait for next key to exit help
        while True:
            try:
                k = sys.stdin.read(1)
            except IOError:
                k = None
            if k:
                break

def trigger_text_event():
    global text_timer, text_cool, text_lines
    if text_cool == 0:
        text_lines = random.sample(words, k=min(8, len(words)))
        text_timer = TEXT_DUR
        text_cool = TEXT_COOLDOWN

# === Main loop ===
try:
    while True:
        # — read key —
        try:
            ch = sys.stdin.read(1)
        except IOError:
            ch = None
        if ch:
            handle_key(ch)

        # — audio FFT —
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]
        if np.max(np.abs(samples)) < 80:
            fft = np.zeros(64)
        else:
            full = np.abs(np.fft.fft(samples))[:CHUNK//2]
            focus = full[:64]
            fft = np.interp(np.linspace(0,len(focus),64),
                            np.arange(len(focus)), focus)
            fft /= (np.percentile(fft,98)+1e-6)
            fft = np.clip(np.sqrt(fft), 0,1)
            fft = median_filter(fft, size=1)
            fft = 0.3*prev_fft + 0.7*fft
            prev_fft = fft.copy()

        energy = np.mean(fft)
        density = int(energy*200*spawn_mult)

        # — maybe auto trigger text event —
        if energy>0.6 and random.random()<0.03 and text_cool==0:
            trigger_text_event()

        # — fade grid —
        for y in range(rows):
            for x in range(cols):
                if age[y][x]>0:
                    age[y][x] -=1
                    if age[y][x]==0:
                        grid[y][x] = " "

        # — spawn new chars —
        for _ in range(density):
            x = random.randrange(cols)
            y = random.randrange(rows)
            if random.random()<0.1:
                c = random.choice(words)
            else:
                idx = int(energy * (len(palette)-1))
                c = palette[random.randint(0, idx)]
            grid[y][x] = str(c)[0]
            age[y][x] = random.randint(1, fade_dur)

        # — render —
        sys.stdout.write("\033[2J\033[H")
        for y in range(rows):
            line = []
            for x in range(cols):
                if age[y][x]>0:
                    ch = grid[y][x]
                    if rainbow and random.random()<0.02:
                        color = f"\033[9{random.randint(1,6)}m"
                    else:
                        color = "\033[97m" if not invert else "\033[90m"
                    line.append(f"{color}{ch}\033[0m")
                else:
                    line.append(" ")
            sys.stdout.write("".join(line) + "\n")
        sys.stdout.flush()

        # — draw text event overlay —
        if text_timer>0:
            start = rows - int((text_timer/TEXT_DUR)*rows*text_scroll_speed)
            for i, txt in enumerate(text_lines):
                y = start + i
                if 0 <= y < rows:
                    pad = max(0, (cols - len(txt))//2)
                    sys.stdout.write(f"\033[{y};{pad}H\033[1;37m{txt[:cols]}\033[0m")
            text_timer -= 1
        if text_cool>0:
            text_cool -= 1

        time.sleep(1/30)

except KeyboardInterrupt:
    pass

finally:
    restore_terminal()
    stream.stop_stream()
    stream.close()
    p.terminate()
    print("\033[0m\n[voidcore_vis_v2] Exited.")
