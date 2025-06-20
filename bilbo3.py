import numpy as np
import pyaudio
import random
import time
import sys
import shutil
from scipy.ndimage import median_filter
from common import engine

# === INITIALIZE ENGINE ===
engine_data = engine.initialize(
    interface_type="focusrite2i4",
    processor_type="default",
)
cols = engine_data["cols"]
rows = engine_data["rows"]

# === CONSTANTS ===
wave_chars = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
RESET = "\033[0m"
colors = [
    "\033[91m", "\033[92m", "\033[93m",
    "\033[94m", "\033[95m", "\033[96m"
]
decay_chars = list(".*:,'`> &")

# === EXPLOSIONS ===
explosions = [
    [r"   .   ", r"  . .  ", r"   .   "],
    [r" \ o / ", r"-  O  -", r" / o \ "],
    [r"  ***  ", r" ***** ", r"  ***  "]
]
# === PROJECT PAT SPRITE ===
pat_sprite = [
    r"   _____   ",
    r"  /     \  ",
    r" | () () | ",
    r"  \  ^  /  ",
    r"   |||||   ",
    r"   |||||   ",
]
# === LYRICS ===
with open("out_there.txt", "r") as f:
    all_lines = [line.strip() for line in f if line.strip()]

# === STATE DICTIONARY ===
state = {
    "line_index": random.randrange(len(all_lines)),
    "lyric_state": {
        "text": "",
        "color": "",
        "x": 0,
        "y": rows // 2,
        "timer": 0,
        "fade_frames": [],
    },
    "pat_timer": 0,
    "pat_pos": (0, 0),
    "explosion_active": False,
    "explosion_frame": 0,
    "explosion_delay": 0,
    "explosion_pos": (0, 0),
    "explosion_color": random.choice(colors),
    "explosion_cooldown": 0,
}

# === MAIN LOOP ===
def main_loop(data):
    is_silent = data["is_silent"]
    fft = data["fft"]
    low_energy = data["low_energy"]
    high_energy = data["high_energy"]
    total_energy = data["total_energy"]
    snare_val = data["snare_val"]
    hat_val = data["hat_val"]
    samples = data["samples"]

    if is_silent:
        print("\033[2J\033[H", end="")
        state["lyric_state"]["timer"] = 0
        state["lyric_state"]["fade_frames"].clear()
        state["pat_timer"] = 0
        state["explosion_active"] = False
        state["explosion_cooldown"] = 0
        sys.stdout.flush()
        time.sleep(1 / 30)
        return

    print("\033[2J\033[H", end="")

    # === CHAOS CHARACTERS ===
    if high_energy > 0.15:
        density = int(high_energy * 120)
        for _ in range(density):
            y = random.randint(1, rows - 2)
            if abs(y - state["lyric_state"]["y"]) < 2:
                continue
            x = random.randint(0, cols - 1)
            char = random.choice("~!@#$%^&*()_+=-▌▐▒░█▓▄▀▁▂▃▅▆")
            color = random.choice(colors)
            print(f"\033[{y};{x}H{color}{char}{RESET}")

    # === EXPLOSIONS ===
    if not state["explosion_active"] and state["explosion_cooldown"] <= 0:
        if low_energy > 0.45 and total_energy > 0.4 and random.random() < 0.2:
            state["explosion_active"] = True
            state["explosion_frame"] = 0
            state["explosion_delay"] = 3
            state["explosion_color"] = random.choice(colors)
            state["explosion_pos"] = (
                random.randint(5, max(5, cols - 10)),
                random.randint(2, max(2, rows - 5))
            )
            state["explosion_cooldown"] = 10

    if state["explosion_active"]:
        if state["explosion_frame"] < len(explosions):
            frame = explosions[state["explosion_frame"]]
            x, y = state["explosion_pos"]
            for i, line in enumerate(frame):
                if 0 <= y + i < rows:
                    print(f"\033[{y+i};{x}H{state['explosion_color']}{line}{RESET}")
            state["explosion_delay"] -= 1
            if state["explosion_delay"] <= 0:
                state["explosion_frame"] += 1
                state["explosion_delay"] = 3
        else:
            state["explosion_active"] = False

    if state["explosion_cooldown"] > 0:
        state["explosion_cooldown"] -= 1

    # === PROJECT PAT ===
    if state["pat_timer"] == 0 and total_energy > 0.5 and random.random() < 0.03:
        state["pat_pos"] = (random.randint(3, cols - 15), random.randint(3, rows - 8))
        state["pat_timer"] = 10

    if state["pat_timer"] > 0:
        px, py = state["pat_pos"]
        for i, line in enumerate(pat_sprite):
            if 0 <= py + i < rows:
                print(f"\033[{py+i};{px}H\033[95m{line}{RESET}")
        state["pat_timer"] -= 1

    # === LYRICS ===
    if state["lyric_state"]["timer"] == 0 and total_energy > 0.25:
        line = all_lines[state["line_index"] % len(all_lines)]
        state["line_index"] += 1
        base_x = max(0, (cols - len(line)) // 2)
        x = base_x + random.choice([-1, 0, 1])
        x = max(0, min(cols - len(line), x))

        state["lyric_state"].update({
            "text": line,
            "color": random.choice(colors),
            "x": x,
            "y": rows // 2,
            "timer": int(15 + total_energy * 50),
            "fade_frames": []
        })

    if state["lyric_state"]["timer"] > 0:
        print(f"\033[{state['lyric_state']['y']};{state['lyric_state']['x']}H{state['lyric_state']['color']}{state['lyric_state']['text']}{RESET}")
        state["lyric_state"]["timer"] -= 1

        if state["lyric_state"]["timer"] == 0:
            # Begin fade-out
            state["lyric_state"]["fade_frames"] = list(state["lyric_state"]["text"])

    elif state["lyric_state"]["fade_frames"]:
        for i in range(len(state["lyric_state"]["fade_frames"])):
            if state["lyric_state"]["fade_frames"][i] != " ":
                state["lyric_state"]["fade_frames"][i] = random.choice(decay_chars)
        fade_line = ''.join(state["lyric_state"]["fade_frames"])
        print(f"\033[{state['lyric_state']['y']};{state['lyric_state']['x']}H{state['lyric_state']['color']}{fade_line}{RESET}")
        if all(c == " " for c in fade_line):
            state["lyric_state"]["fade_frames"].clear()

    # === HUD BAR CHART UNDER LYRICS ===
    hud_bands = 8
    band_vals = np.mean(fft.reshape(hud_bands, -1), axis=1)
    hud_chars = [' ', '▁', '▂', '▃', '▄', '▅', '▆', '█']
    hud_height = len(hud_chars) - 1

    hud_y = state["lyric_state"]["y"] + 3
    hud_x = max((cols - hud_bands) // 2, 0)

    for i, val in enumerate(band_vals):
        level = min(int(val * hud_height * 1.5), hud_height)
        char = hud_chars[level]
        print(f"\033[{hud_y};{hud_x + i}H\033[96m{char}{RESET}")

    # === ENERGY NUMBER CENTERED TOO ===
    
    # Compute "kick" energy as the mean of the lowest 8 FFT bands, scaled to 0–100%
    energy_value = int(np.mean(fft[:8]) * 100)
    energy_label = f"Kick: {energy_value:3d}%"
    # Center the label horizontally
    kick_x = max((cols - len(energy_label)) // 2, 0)
    # Place it just below the HUD bar chart
    kick_y = hud_y + 1
    print(f"\033[{kick_y};{kick_x}H\033[94m{energy_label}{RESET}")

    # Hat line
    hat_val_pct = int(hat_val * 100)
    hat_label = f"Hat:  {hat_val_pct:3d}%"
    print(f"\033[{hud_y+2};{kick_x}H\033[93m{hat_label}{RESET}")

    # Snare line
    snare_val_pct = int(snare_val * 100)
    snare_label = f"Snare:{snare_val_pct:3d}%"
    print(f"\033[{hud_y+3};{kick_x}H\033[95m{snare_label}{RESET}")

    # === ASCII WAVEFORM ===
    wave_y = rows - 2
    wave = samples[::len(samples)//cols][:cols]
    norm_wave = np.interp(wave, (-30000, 30000), (0, 7)).astype(int)
    for x, idx in enumerate(norm_wave):
        char = wave_chars[idx]
        print(f"\033[{wave_y};{x}H\033[92m{char}{RESET}")

engine.run(engine_data, main_loop)