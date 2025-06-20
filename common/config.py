import shutil
import pyaudio

# === Audio Configuration ===
CHUNK = 2048
RATE = 48000
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = 1  # Default to index 1, can be changed
OUTPUT_INDEX = 1  # Default to index 0 for output

# === Terminal Configuration ===
def get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))

# === FFT Processing ===
SMOOTHING = 0.5
FFT_SIZE = 64

# === Animation Settings ===
FPS = 30
FRAME_DELAY = 1/30

# === Energy Thresholds ===
SILENCE_THRESHOLD = 100
LOW_ENERGY_THRESHOLD = 0.15
HIGH_ENERGY_THRESHOLD = 0.2
EXPLOSION_THRESHOLD = 0.4
PAT_THRESHOLD = 0.5

# === Load Lyrics
def load_lyrics():
    with open("./out_there.txt") as f:
        lines = [line.strip() for line in f if line.strip()]
    line_index = 0
    return lines, line_index