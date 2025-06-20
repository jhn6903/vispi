import shutil
import pyaudio

# === Audio Configuration ===
interface_configs = {
    "default": {
        "chunk_size": 2048,
        "sample_rate": 48000,
        "format": pyaudio.paInt16,
        "channels": 2,
        "input_index": 1,
        "output_index": 1,
    },
    "focusrite2i4": {
        "chunk_size": 2048,
        "sample_rate": 48000,
        "format": pyaudio.paInt16,
        "channels": 2,
        "input_index": 1,
        "output_index": 1,
    }
}

# === FFT Processing ===
SMOOTHING = 0.5
FFT_SIZE = 64
