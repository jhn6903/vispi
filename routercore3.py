import numpy as np
import pyaudio
import time
import random
import shutil
from scipy.ndimage import median_filter

# === Audio Config ===
CHUNK = 1024
RATE = 44100
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = 1
NUM_BARS = 64
NOISE_GATE = 100

# === Terminal Config ===
def get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))

cols, rows = get_terminal_size()
log_lines = []
glitch_chars = list("~!@#$%^&*()_+=-▌▐▒░█▓▄▀▁▂▃▅▆")

# === Text Content ===
with open("/home/vispi/visualizers/out_there.txt") as f:
    word_bank = [line.strip() for line in f if line.strip()]

# === Audio Stream ===
p = pyaudio.PyAudio()
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    input_device_index=INPUT_INDEX,
    frames_per_buffer=CHUNK
)

prev_fft = np.zeros(NUM_BARS)

# === Main Loop ===
try:
    while True:
        # === Audio Capture ===
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]
        is_silent = np.max(np.abs(samples)) < NOISE_GATE

        # === FFT Analysis ===
        if is_silent:
            fft = np.zeros(NUM_BARS)
        else:
            full_fft = np.abs(np.fft.fft(samples))[:CHUNK // 2]
            focus = full_fft[:int(NUM_BARS * 2/3)]
            fft = np.interp(np.linspace(0, len(focus), NUM_BARS), np.arange(len(focus)), focus)
            fft = fft / (np.percentile(fft, 98) + 1e-6)
            fft = np.clip(fft * 1.5, 0, 1)
            fft = np.where(fft < 0.05, fft * 0.1, fft)
            fft[fft < 0.08] = 0
            fft = np.sqrt(fft)
            fft = median_filter(fft, size=1)
            fft = 0.3 * prev_fft + 0.7 * fft
            prev_fft = fft.copy()

        energy = np.mean(fft)
        max_lines = rows - 2

        # === Terminal Log Line Generation ===
        if energy > 0.06 or len(log_lines) < max_lines:
            ip = ".".join(str(random.randint(0, 255)) for _ in range(4))
            port = random.randint(1000, 9999)
            word = random.choice(word_bank) if random.random() < 0.4 else ""
            glitch = ''.join(random.choice(glitch_chars) for _ in range(random.randint(2, 5)))
            log_line = f"[+] {ip}:{port} / {word} [{glitch}]"
            log_lines.append(log_line)

        if len(log_lines) > max_lines:
            log_lines = log_lines[-max_lines:]

        # === Clear and Print to Terminal ===
        print("\033[2J\033[H", end="")  # Clear screen
        for i, line in enumerate(log_lines):
            if random.random() < energy * 0.3:
                # Glitch out a line
                glitched = ''.join(
                    c if random.random() > energy * 0.3 else random.choice(glitch_chars)
                    for c in line
                )
            else:
                glitched = line

            # Occasionally throw color
            if random.random() < 0.05:
                color = f"\033[9{random.randint(1, 6)}m"
            else:
                color = "\033[97m"  # white

            print(f"\033[{i + 1};0H{color}{glitched}\033[0m")

        # === ASCII Waveform Strip (Bottom Row) ===
        wave = samples[::len(samples) // cols][:cols]
        norm_wave = np.interp(wave, (-30000, 30000), (0, 7)).astype(int)
        wave_chars = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']
        print(f"\033[{rows - 1};0H", end="")
        for idx in norm_wave:
            print(f"\033[97m{wave_chars[idx]}\033[0m", end="")

        time.sleep(1 / 30)

except KeyboardInterrupt:
    print("\033[0m\nVisualizer stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
