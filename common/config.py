import shutil
import pyaudio
import numpy as np

supported_visualizers = ["fftv_pat", "routercore4", "conway", "bilbo3", "debug_energy"]
possible_chunk_sizes = [1024, 2048, 4096, 8192, 16384]

# === Audio Configuration ===
interface_configs = {
    "default": {
        "chunk_size": 2048,
        "sample_rate": 48000,
        "format": pyaudio.paInt16,
        "np_format": np.int16,
        "channels": 2,
        "input_index": 1,
        "output_index": 1,
    },
    "focusrite2i4": {
        "chunk_size": 2048,
        "sample_rate": 48000,
        "format": pyaudio.paInt16,
        "np_format": np.int16,
        "channels": 2,
        "input_index": 1,
        "output_index": 1,
    },
}

# === FFT Processing ===
SMOOTHING = 0.5
FFT_SIZE = 64

# === random loop settings ===
min_frames = 23 * 1
max_frames = 23 * 2
