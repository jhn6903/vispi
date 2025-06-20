import shutil
import pyaudio
import numpy as np
import time
import logging
import os
from datetime import datetime
from scipy.ndimage import median_filter
import sys
from .config import interface_configs, FFT_SIZE, SMOOTHING, possible_chunk_sizes

# Logger will be initialized conditionally
logger = None

def _setup_logger(debug: bool):
    """Initialize logger only if debug is True - logs to file"""
    global logger
    if debug and logger is None:
        logger = logging.getLogger('audio_engine')
        logger.setLevel(logging.DEBUG)
        
        # Create logs directory if it doesn't exist
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create timestamped log filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(log_dir, f"audio_engine_{timestamp}.log")
        
        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(file_handler)
        
        logger.info("=== Audio Engine Debug Session Started ===")
        logger.info(f"Log file: {log_file}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Working directory: {os.getcwd()}")
        
    elif not debug:
        logger = None

def _get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))

def _setup_audio(interface_type: str = "default", determine_chunk_size=False):
    global logger
    
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

    data = stream.read(config["chunk_size"], exception_on_overflow=True)
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

def initialize(
    interface_type: str = "default",
    processor_type: str = "default",
    debug=False
    ):
    _setup_logger(debug)
    cols, rows = _get_terminal_size()
    stream, p, config = _setup_audio(interface_type, determine_chunk_size=False)
    processor = _get_processor(processor_type)
    
    return {
        "cols": cols,
        "rows": rows,
        "stream": stream,
        "p": p,
        "config": config,
        "processor": processor,
        "prev_fft": np.zeros(64),
        "fps": config["sample_rate"] / config["chunk_size"] * 1.025,
        "debug": debug
    }

def run(engine_data, loop_func):
    global logger
    stream = engine_data["stream"]
    p = engine_data["p"]
    config = engine_data["config"]
    processor = engine_data["processor"]
    prev_fft = engine_data["prev_fft"]
    debug = engine_data.get("debug", False)
    stage_timer = StageDebugTimer()
    if logger:
        logger.info("Starting audio engine main loop")
        
    try:
        while True:
            stage_timer.global_start()
            debug and stage_timer.start("processor")
            proc_output = processor(stream, config, prev_fft)
            debug and stage_timer.stop("processor")
            prev_fft = proc_output["prev_fft"]
            debug and stage_timer.start("loop_func")
            loop_func(proc_output)
            debug and stage_timer.stop("loop_func")
            sys.stdout.flush()
            debug and stage_timer.start("sleep")
            time_left = (1 / engine_data["fps"]) - stage_timer.get_global_time()
            time.sleep(max(time_left, 0))
            debug and stage_timer.stop("sleep")
            debug and stage_timer.global_stop()
    except KeyboardInterrupt:
        print("Keyboard interrupt")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

from collections import defaultdict
class StageDebugTimer:
    def __init__(self):
        self.stage_times = defaultdict(float)
        self.global_time = 0
    
    def get_global_time(self):
        return time.time() - self.global_start_time
    
    def global_start(self):
        self.global_start_time = time.time()

    def start(self, stage_name):
        self.stage_times[stage_name] = time.time()

    def stop(self, stage_name):
        self.stage_times[stage_name] = time.time() - self.stage_times[stage_name]
    
    def global_stop(self):
        self.global_time = time.time() - self.global_start_time
        
        # Calculate actual FPS
        actual_fps = 1 / self.global_time
        
        # Log actual times and proportions
        logger.info("=== Stage Debug Timer ===")
        logger.info(f"Total frame time: {self.global_time:.6f}s")
        logger.info(f"Actual FPS: {actual_fps:.2f}")
        
        # Log each stage with both time and percentage
        for stage_name, stage_time in self.stage_times.items():
            percentage = (stage_time / self.global_time) * 100
            logger.info(f"{stage_name}: {stage_time:.6f}s ({percentage:.1f}%)")
        
        logger.info("=" * 25)