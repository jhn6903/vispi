import shutil
import pyaudio
import numpy as np
import time
from scipy.ndimage import median_filter
import sys
from .config import interface_configs, FFT_SIZE, SMOOTHING

def _get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))

def _setup_audio(interface_type: str = "default"):
    p = pyaudio.PyAudio()
    config = interface_configs[interface_type]
    stream = p.open(format=config["format"],
                    channels=config["channels"],
                    rate=config["sample_rate"],
                    input=True,
                    input_device_index=config["input_index"],
                    frames_per_buffer=config["chunk_size"]
                    )
    return stream, p, config

def _get_processor(processor_type: str = "default"):
    if processor_type == "default":
        return _default_process_audio
    else:
        raise ValueError(f"Processor {processor_type} not found")

def _default_process_audio(stream, config, prev_fft):
    SMOOTHING = 0.5

    data = stream.read(config["chunk_size"], exception_on_overflow=False)
    samples = np.frombuffer(data, dtype=np.int16)[::2]
    is_silent = np.max(np.abs(samples)) < 100

    fft = np.abs(np.fft.fft(samples))[:64]
    fft = median_filter(fft, size=3)
    fft = fft / (np.max(fft) + 1e-6)
    fft = SMOOTHING * prev_fft + (1 - SMOOTHING) * fft

    output = {
        "is_silent": is_silent,
        "samples": samples,
        "fft": fft,
        "prev_fft": fft.copy(),
        "low_energy": np.mean(fft[:8]),
        "high_energy": np.mean(fft[32:]),
        "total_energy": np.mean(fft),
        "kick_energy": fft[8],
        "snare_energy": fft[20],
        "hat_energy": fft[-1],
    }

    return output

def initialize(interface_type: str = "default", processor_type: str = "default"):
    cols, rows = _get_terminal_size()
    stream, p, config = _setup_audio(interface_type)
    processor = _get_processor(processor_type)
    
    return {
        "cols": cols,
        "rows": rows,
        "stream": stream,
        "p": p,
        "config": config,
        "processor": processor,
        "prev_fft": np.zeros(64)
    }

def run(engine_data, loop_func, fps=30):
    stream = engine_data["stream"]
    p = engine_data["p"]
    config = engine_data["config"]
    processor = engine_data["processor"]
    prev_fft = engine_data["prev_fft"]
    
    try:
        while True:
            proc_output = processor(stream, config, prev_fft)
            prev_fft = proc_output["prev_fft"]
            loop_func(proc_output)
            sys.stdout.flush()
            time.sleep(1 / fps)
    except KeyboardInterrupt:
        print("Keyboard interrupt")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
