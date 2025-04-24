import pyaudio
import numpy as np
import time
import os

# Constants
CHUNK = 1024  # Number of audio samples per frame
RATE = 44100  # Sampling rate
FORMAT = pyaudio.paInt16  # 16-bit audio
CHANNELS = 1  # Mono input

# Init PyAudio
p = pyaudio.PyAudio()

# Open audio stream
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK
)

try:
    print("Vispi VU Meter – Live Input")
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)
        peak = np.abs(samples).max()
        bar = '#' * int(peak / 500)  # Scale this for your input level
        print("\033[1;1H\033[J", end="")  # ANSI escape: clear from cursor down
        print(f"[{bar:<80}] {peak}", end="\r", flush=True)
        time.sleep(0.05)

except KeyboardInterrupt:
    pass

finally:
    stream.stop_stream()
    stream.close()
    p.terminate()
    print("\nStopped.")
