#!/usr/bin/env python3
"""
bilbo.py

Terminal audio visualizer with FFT, chaos, explosions, PAT sprite,
lyrics, HUD bars, MIDI color cycle, and interactive numpad controls:
1: Next lyric
2: Random lyric color
3: Cycle sensitivity
4: Toggle chaos
0: Toggle help overlay
"""
import numpy as np
import pyaudio
import random
import time
import sys
import shutil
import termios
import tty
import select
from scipy.ndimage import median_filter
import mido

# === TERMINAL CONFIG ===
def get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))
cols, rows = get_terminal_size()
RESET = "\033[0m"

# Enter raw mode for key input
fd = sys.stdin.fileno()
old_settings = termios.tcgetattr(fd)
tty.setcbreak(fd)

# === AUDIO CONFIG ===
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = 1

# === COLORS ===
colors = [
    "\033[91m", "\033[92m", "\033[93m",
    "\033[94m", "\033[95m", "\033[96m"
]
color_idx = 0  # for MIDI cycling

# === ASCII DECAY & WAVEFORM ===
decay_chars = list(".*:,'` ")
wave_chars = ['▁','▂','▃','▄','▅','▆','▇','█']

# === EXPLOSIONS ===
explosions = [
    ["   .   ", "  . .  ", "   .   "],
    [" \ o / ", "-  O  -", " / o \ "],
    ["  ***  ", " ***** ", "  ***  "]
]

# === PAT SPRITE ===
pat_sprite = [
    "   _____   ",
    "  /     \  ",
    " | () () | ",
    "  \  ^  /  ",
    "   |||||   ",
    "   |||||   "
]

# === LYRICS ===
with open("out_there.txt", "r") as f:
    all_lines = [ln.strip() for ln in f if ln.strip()]
line_index = 0
lyric_state = {
    "text": "", "color": "", "x": 0,
    "y": rows // 2, "timer": 0, "fade_frames": []
}

# === SENSITIVITY ===
sensitivity_levels = [3.0, 5.0, 8.0]
sens_idx = 1

# === CHAOS & HELP ===
chaos_enabled = True
help_lines = [
    "Numpad:",
    "1: Next lyric",
    "2: Random lyric color",
    "3: Cycle sensitivity",
    "4: Toggle chaos",
    "0: Toggle help"
]
help_mode = False

# === MIDI SETUP ===
ports = mido.get_input_names()
if len(ports) < 2:
    print("Need 2+ MIDI ports, found:", ports)
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    sys.exit(1)
midi_in = mido.open_input(ports[1])
MIDI_NOTE, MIDI_CH = 87, 1

# === AUDIO INIT ===
p = pyaudio.PyAudio()
stream = p.open(format=FORMAT, channels=CHANNELS,
                rate=RATE, input=True,
                input_device_index=INPUT_INDEX,
                frames_per_buffer=CHUNK)

prev_fft = np.zeros(64)
SMOOTHING = 0.5
pat_timer = 0
expl_active = False
expl_frame = expl_delay = expl_cd = 0
expl_pos = (0, 0)

try:
    while True:
                # --- Numpad input ---
        help_pressed = False
        if select.select([sys.stdin], [], [], 0)[0]:
            ch = sys.stdin.read(1)
            if ch == '1':
                lyric_state['timer'] = 0
            elif ch == '2':
                r, g, b = [random.randint(0, 255) for _ in range(3)]
                lyric_state['color'] = f"[38;2;{r};{g};{b}m"
            elif ch == '3':
                sens_idx = (sens_idx + 1) % len(sensitivity_levels)
            elif ch == '4':
                chaos_enabled = not chaos_enabled
            elif ch == '0':
                help_pressed = True
        # Help view only while '0' held
        help_mode = help_pressed

        # Show help overlay
        if help_mode:
            print("\033[2J\033[H", end='')
            start = (rows - len(help_lines)) // 2
            for i, hl in enumerate(help_lines):
                x = (cols - len(hl)) // 2
                print(f"\033[{start+i};{x}H{hl}")
            sys.stdout.flush()
            time.sleep(0.1)
            continue

        # === Read audio & compute FFT ===
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::CHANNELS]
        fft = np.abs(np.fft.fft(samples))[:64]
        fft = median_filter(fft, size=3)
        fft /= (np.max(fft) + 1e-6)
        sens = sensitivity_levels[sens_idx]
        fft = SMOOTHING * prev_fft + (1 - SMOOTHING) * (fft * sens)
        prev_fft = fft.copy()

        # Energy metrics
        bass_val = np.max(fft[:8])
        snare_val = fft[20]
        hat_val = fft[-1]
        total_energy = np.mean(fft)

        # MIDI: cycle color
        for msg in midi_in.iter_pending():
            if msg.type == 'note_on' and msg.channel == MIDI_CH and msg.note == MIDI_NOTE:
                color_idx = (color_idx + 1) % len(colors)

        # Clear screen
        print("\033[2J\033[H", end='')

        # === Chaos characters ===
        if chaos_enabled and total_energy > 0.1:
            for _ in range(int(total_energy * 150)):
                y = random.randint(1, rows-2)
                if abs(y - lyric_state['y']) < 2: continue
                x = random.randint(0, cols-1)
                c = random.choice("~!@#$%^&*()_+=-▌▐▒░█▓▄▀▁▂▃▅▆")
                col = random.choice(colors)
                print(f"\033[{y};{x}H{col}{c}{RESET}")

        # === Explosions ===
        if not expl_active and expl_cd <= 0 and bass_val > 1.0 and total_energy > 0.5 and random.random() < 0.1:
            expl_active = True
            expl_frame = 0
            expl_delay = 3
            expl_cd = 10
            expl_pos = (random.randint(5, cols-10), random.randint(2, rows-5))
        if expl_active:
            x0, y0 = expl_pos
            if expl_frame < len(explosions):
                for i, frame in enumerate(explosions[expl_frame]):
                    print(f"\033[{y0+i};{x0}H{colors[color_idx]}{frame}{RESET}")
                expl_delay -= 1
                if expl_delay <= 0:
                    expl_frame += 1
                    expl_delay = 3
            else:
                expl_active = False
        expl_cd = max(0, expl_cd - 1)

        # === PAT sprite ===
        if pat_timer == 0 and total_energy > 0.5 and random.random() < 0.03:
            pat_pos = (random.randint(3, cols-15), random.randint(3, rows-8))
            pat_timer = 10
        if pat_timer > 0:
            px, py = pat_pos
            for i, line in enumerate(pat_sprite):
                print(f"\033[{py+i};{px}H{colors[color_idx]}{line}{RESET}")
            pat_timer -= 1

        # === Lyrics ===
        if lyric_state['timer'] == 0 and total_energy > 0.25:
            ln = all_lines[line_index % len(all_lines)]
            line_index += 1
            bx = max((cols - len(ln)) // 2, 0)
            x0 = bx + random.choice([-1, 0, 1])
            x0 = max(0, min(cols - len(ln), x0))
            lyric_state.update({
                'text': ln,
                'color': colors[color_idx],
                'x': x0,
                'y': rows // 2,
                'timer': int(15 + total_energy * 50),
                'fade_frames': []
            })
        if lyric_state['timer'] > 0:
            print(f"\033[{lyric_state['y']};{lyric_state['x']}H{lyric_state['color']}{lyric_state['text']}{RESET}")
            lyric_state['timer'] -= 1
            if lyric_state['timer'] == 0:
                lyric_state['fade_frames'] = list(lyric_state['text'])
        elif lyric_state['fade_frames']:
            ff = lyric_state['fade_frames']
            for i, ch in enumerate(ff):
                if ch != ' ': ff[i] = random.choice(decay_chars)
            fl = ''.join(ff)
            print(f"\033[{lyric_state['y']};{lyric_state['x']}H{lyric_state['color']}{fl}{RESET}")
            if all(c==' ' for c in fl): lyric_state['fade_frames'].clear()

        # === HUD Bars ===
        by = lyric_state['y'] + 3
        bx = (cols - 8) // 2
        for i, val in enumerate(np.mean(fft.reshape(8, -1), axis=1)):
            lvl = min(int(val * 7 * 1.5), 7)
            print(f"\033[{by};{bx+i}H\033[96m{wave_chars[lvl]}{RESET}")
        print(f"\033[{by+1};{bx+1}H\033[94mKick:{int(bass_val*100):3d}%{RESET}")
        print(f"\033[{by+2};{bx+1}H\033[97mSnare:{int(snare_val*100):3d}%{RESET}")
        print(f"\033[{by+3};{bx+1}H\033[93mHat:  {int(hat_val*100):3d}%{RESET}")

        # === Bottom Bars & Waveform ===
        print(f"\033[{rows-3};1H\033[92m{'█'*int(bass_val*cols):{cols}}{RESET}")
        print(f"\033[{rows-2};1H\033[97m{'█'*int(snare_val*cols):{cols}}{RESET}")
        print(f"\033[{rows-1};1H\033[93m{'█'*int(hat_val*cols):{cols}}{RESET}")
        wy = rows - 5
        wave = np.interp(samples[::max(1, len(samples)//cols)], (-30000,30000), (0,7)).astype(int)
        for x, idx in enumerate(wave):
            print(f"\033[{wy};{x}H\033[92m{wave_chars[idx]}{RESET}")

        sys.stdout.flush()
        time.sleep(1/30)

except KeyboardInterrupt:
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    print(RESET + "\nVisualizer stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
