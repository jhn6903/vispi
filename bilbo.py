import numpy as np
import pyaudio
import random
import time
import sys
import shutil
from scipy.ndimage import median_filter

wave_chars = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']

# === AUDIO CONFIG ===
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = 1

# === TERMINAL CONFIG ===
def get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))

cols, rows = get_terminal_size()
RESET = "\033[0m"

# === COLORS ===
colors = [
    "\033[91m", "\033[92m", "\033[93m",
    "\033[94m", "\033[95m", "\033[96m"
]

# === ASCII DECAY CHARACTERS ===
decay_chars = list(".*:,'`> &")

# === Snare & Hat Helpers ===
def get_snare_val(fft, bin_index=20):
    """
    Extracts the snare energy from the FFT.
    """
    return fft[bin_index]

def get_hat_val(fft, bin_index=-1):
    """
    Extracts the hi-hat energy from the FFT.
    """
    return fft[bin_index]

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

line_index = random.randrange(len(all_lines))
lyric_state = {
    "text": "",
    "color": "",
    "x": 0,
    "y": rows // 2,
    "timer": 0,
    "fade_frames": [],
}


# === AUDIO SETUP ===
p = pyaudio.PyAudio()
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=INPUT_INDEX,
                frames_per_buffer=CHUNK)

prev_fft = np.zeros(64)
SMOOTHING = 0.5
pat_timer = 0
pat_pos = (0, 0)

explosion_active = False
explosion_frame = 0
explosion_delay = 0
explosion_pos = (0, 0)
explosion_color = random.choice(colors)
explosion_cooldown = 0

# === MAIN LOOP ===
try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]
        is_silent = np.max(np.abs(samples)) < 100

        if is_silent:
            print("\033[2J\033[H", end="")
            lyric_state["timer"] = 0
            lyric_state["fade_frames"].clear()
            pat_timer = 0
            explosion_active = False
            explosion_cooldown = 0
            sys.stdout.flush()
            time.sleep(1 / 30)
            continue

        fft = np.abs(np.fft.fft(samples))[:64]
        fft = median_filter(fft, size=3)
        fft = fft / (np.max(fft) + 1e-6)
        fft = SMOOTHING * prev_fft + (1 - SMOOTHING) * fft
        prev_fft = fft.copy()

        low_energy = np.mean(fft[:8])
        high_energy = np.mean(fft[32:])
        total_energy = np.mean(fft)
        snare_val = get_snare_val(fft)
        hat_val   = get_hat_val(fft)

        print("\033[2J\033[H", end="")

        # === CHAOS CHARACTERS ===
        if high_energy > 0.15:
            density = int(high_energy * 120)
            for _ in range(density):
                y = random.randint(1, rows - 2)
                if abs(y - lyric_state["y"]) < 2:  # avoid printing *on* the lyric
                    continue
                x = random.randint(0, cols - 1)
                char = random.choice("~!@#$%^&*()_+=-▌▐▒░█▓▄▀▁▂▃▅▆")
                color = random.choice(colors)
                print(f"\033[{y};{x}H{color}{char}{RESET}")


        # === EXPLOSIONS ===
        if not explosion_active and explosion_cooldown <= 0:
            if low_energy > 0.45 and total_energy > 0.4 and random.random() < 0.2:
                explosion_active = True
                explosion_frame = 0
                explosion_delay = 3
                explosion_color = random.choice(colors)
                explosion_pos = (
                    random.randint(5, max(5, cols - 10)),
                    random.randint(2, max(2, rows - 5))
                )
                explosion_cooldown = 10

        if explosion_active:
            if explosion_frame < len(explosions):
                frame = explosions[explosion_frame]
                x, y = explosion_pos
                for i, line in enumerate(frame):
                    if 0 <= y + i < rows:
                        print(f"\033[{y+i};{x}H{explosion_color}{line}{RESET}")
                explosion_delay -= 1
                if explosion_delay <= 0:
                    explosion_frame += 1
                    explosion_delay = 3
            else:
                explosion_active = False

        if explosion_cooldown > 0:
            explosion_cooldown -= 1


            # === BACKGROUND NOISE FLICKER ===
            if total_energy < 0.25:
                for _ in range(10):
                    x = random.randint(0, cols - 1)
                    y = random.randint(1, rows - 2)
                    flicker = random.choice([".", "`", "'", " "])
                    print(f"\033[{y};{x}H\033[90m{flicker}{RESET}")


        # === PROJECT PAT ===
        if pat_timer == 0 and total_energy > 0.5 and random.random() < 0.03:
            pat_pos = (random.randint(3, cols - 15), random.randint(3, rows - 8))
            pat_timer = 10

        if pat_timer > 0:
            px, py = pat_pos
            for i, line in enumerate(pat_sprite):
                if 0 <= py + i < rows:
                    print(f"\033[{py+i};{px}H\033[95m{line}{RESET}")
            pat_timer -= 1

        # === LYRICS ===
        if lyric_state["timer"] == 0 and total_energy > 0.25:
            line = all_lines[line_index % len(all_lines)]
            line_index += 1
            base_x = max(0, (cols - len(line)) // 2)
            x = base_x + random.choice([-1, 0, 1])
            x = max(0, min(cols - len(line), x))

            lyric_state.update({
                "text": line,
                "color": random.choice(colors),
                "x": x,
                "y": rows // 2,
                "timer": int(15 + total_energy * 50),
                "fade_frames": []
            })

        if lyric_state["timer"] > 0:
            print(f"\033[{lyric_state['y']};{lyric_state['x']}H{lyric_state['color']}{lyric_state['text']}{RESET}")
            lyric_state["timer"] -= 1

            if lyric_state["timer"] == 0:
                # Begin fade-out
                lyric_state["fade_frames"] = list(lyric_state["text"])

        elif lyric_state["fade_frames"]:
            for i in range(len(lyric_state["fade_frames"])):
                if lyric_state["fade_frames"][i] != " ":
                    lyric_state["fade_frames"][i] = random.choice(decay_chars)
            fade_line = ''.join(lyric_state["fade_frames"])
            print(f"\033[{lyric_state['y']};{lyric_state['x']}H{lyric_state['color']}{fade_line}{RESET}")
            if all(c == " " for c in fade_line):
                lyric_state["fade_frames"].clear()

        # === HUD BAR CHART UNDER LYRICS ===
        hud_bands = 8
        band_vals = np.mean(fft.reshape(hud_bands, -1), axis=1)
        hud_chars = [' ', '▁', '▂', '▃', '▄', '▅', '▆', '█']
        hud_height = len(hud_chars) - 1

        hud_y = lyric_state["y"] + 3
        hud_x = max((cols - hud_bands) // 2, 0)

        for i, val in enumerate(band_vals):
            level = min(int(val * hud_height * 1.5), hud_height)
            char = hud_chars[level]
            print(f"\033[{hud_y};{hud_x + i}H\033[96m{char}{RESET}")

        # === ENERGY NUMBER CENTERED TOO ===
        
        # Compute “kick” energy as the mean of the lowest 8 FFT bands, scaled to 0–100%
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

        sys.stdout.flush()
        time.sleep(1 / 30)

        # === ASCII WAVEFORM ===
        wave_y = rows - 2
        wave = samples[::len(samples)//cols][:cols]
        norm_wave = np.interp(wave, (-30000, 30000), (0, 7)).astype(int)
        for x, idx in enumerate(norm_wave):
            char = wave_chars[idx]
            print(f"\033[{wave_y};{x}H\033[92m{char}{RESET}")


except KeyboardInterrupt:
    print(RESET)
    print("\nVisualizer stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
