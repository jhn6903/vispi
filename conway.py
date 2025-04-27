import numpy as np
import pyaudio
import random
import time
import sys
import shutil
from scipy.ndimage import median_filter

cell_chars = ['█', '▓', '▒', '░']

# === AUDIO CONFIG ===
CHUNK = 1024
RATE = 48000
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = None

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

def get_kick_val(fft):
    """
    Extracts the kick energy from the FFT.
    """
    return int(np.mean(fft[:8]) * 100)

mantra = "Let the Making it Happen Happen"

# === AUDIO SETUP ===
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    dev_info = p.get_device_info_by_index(i)
    if 'BlackHole' in dev_info['name']:
        INPUT_INDEX = i
        break
if INPUT_INDEX is None:
    raise RuntimeError("BlackHole device not found!")
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=INPUT_INDEX,
                frames_per_buffer=CHUNK)

prev_fft = np.zeros(64)
SMOOTHING = 0.5

# === MAIN LOOP ===
try:
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]
        is_silent = np.max(np.abs(samples)) < 100

        if is_silent:
            print("\033[2J\033[H", end="")
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

        # TODO: integrate the game of life

except KeyboardInterrupt:
    print(RESET)
    print("\nVisualizer stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
