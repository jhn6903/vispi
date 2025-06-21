#!/usr/bin/env python3
"""
Lyric Canvas Visualizer - Refactored to use engine.py
"""

import subprocess
import numpy as np
import time
import random
import shutil
import os
from common import engine
import mmap

# === Initialize Engine ===
engine_data = engine.initialize(
    interface_type="focusrite2i4",
    processor_type="default", 
    debug=True
)

cols = engine_data["cols"]
rows = engine_data["rows"]

# === State ===
canvas = [[" " for _ in range(cols)] for _ in range(rows)]
age = [[0 for _ in range(cols)] for _ in range(rows)]
max_age = 20

chars = list("░▒▓█@#%&$+=~:;,. ")  # glitchy decay set
colors = [f"\033[9{c}m" for c in range(1, 7)]
RESET = "\033[0m"

# === Load Lyrics ===
with open("./out_there.txt") as f:
    lines = [line.strip() for line in f if line.strip()]

state = {
    "line_index": 0
}

# === Draw functions ===
def draw_waveform(samples):
    try:
        if not hasattr(draw_waveform, 'fb_mmap'):
            fb_width, fb_height = get_fb_geometry()
            fb_size = fb_width * fb_height * 2  # 2 bytes per pixel
            
            fb_file = open("/dev/fb0", "rb+")
            draw_waveform.fb_mmap = mmap.mmap(fb_file.fileno(), fb_size)
            draw_waveform.fb_width = fb_width
            draw_waveform.fb_height = fb_height
        
        fb_mmap = draw_waveform.fb_mmap
        fb_width = draw_waveform.fb_width
        fb_height = draw_waveform.fb_height
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
                fb_mmap[offset:offset+2] = b'\xff\xff'  # Direct memory write

                # Optional trailing line (above or below for glow/fade feel)
                if random.random() < 0.2:
                    trail_y = y + random.choice([-1, 1])
                    if 0 <= trail_y < fb_height:
                        offset_trail = (trail_y * fb_width + x) * 2
                        fb_mmap[offset_trail:offset_trail+2] = b'\x88\x88'  # Dim white

                if np.max(np.abs(samples)) > 5000:
                    for _ in range(20):
                        rand_x = random.randint(0, fb_width - 1)
                        rand_y = random.randint(0, fb_height - 1)
                        fb_mmap[rand_y * fb_width + rand_x:rand_y * fb_width + rand_x + 2] = random.choice([b'\xff\x00', b'\x00\xff', b'\x1f\xff']).tobytes()  # Red, Blue, Magenta
        
        # Memory mapped writes are usually immediate
        
    except Exception as e:
        pass

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

# === Main Loop Function ===
def main_loop(data):
    """Main visualization loop that receives processed audio data from engine"""
    
    if data["is_silent"]:
        # Still render canvas during silence to show decay
        decay_canvas()
        render()
        return

    # Get processed audio data from engine
    samples = data["samples"]
    energy = data["total_energy"]  # This is already normalized 0-1 by the engine
    
    # === Paint with sound ===
    # Adjusted threshold since engine normalizes energy to 0-1
    if energy > 0.15 and random.random() < energy:
        line = lines[state["line_index"] % len(lines)]
        state["line_index"] += 1

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

    # === Glitch injection ===
    # Adjusted threshold for normalized energy
    if energy > 0.3 and random.random() < 0.05:
        for _ in range(3):
            gx = random.randint(0, cols - 1)
            gy = random.randint(0, rows - 2)
            canvas[gy][gx] = random.choice(chars)
            age[gy][gx] = random.randint(3, max_age)

    # Update display
    decay_canvas()
    render()
    draw_waveform(samples)

# === Run Engine ===
print("[lyric_canvas] Starting with engine...")
try:
    engine.run(engine_data, main_loop)
except KeyboardInterrupt:
    print("\033[0m\n[lyric_canvas] Terminated.")
