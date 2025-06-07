import numpy as np
import pyaudio
import time
import gc
import logging
import psutil
import os
from datetime import datetime
from pathlib import Path
from scipy.ndimage import median_filter
from common.config import (
    CHUNK, RATE, FORMAT, CHANNELS, INPUT_INDEX,
    get_terminal_size,
    SMOOTHING, FFT_SIZE,
    FRAME_DELAY,
    SILENCE_THRESHOLD
)

# GC event tracking
gc_start_time = None
gc_collection_count = 0
gc_collection_time = 0

# Performance tracking
process = psutil.Process(os.getpid())

def gc_callback(phase, info):
    global gc_start_time, gc_collection_count, gc_collection_time
    if phase == 'start':
        gc_start_time = time.time()
    elif phase == 'stop':
        if gc_start_time is not None:
            duration = time.time() - gc_start_time
            gc_collection_time += duration
            gc_collection_count += 1
            if duration > 0.1:  # 100ms threshold
                logger.warning(f"GC collection #{gc_collection_count} took {duration:.3f}s")
            gc_start_time = None

# Register GC callback
gc.callbacks.append(gc_callback)

# Setup logging at module level
def setup_logging():
    """Setup logging to file"""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"visualizer_{timestamp}.log"
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also log to console
        ]
    )
    return logging.getLogger(__name__)

# Initialize logger
logger = setup_logging()

class BaseVisualizer:
    def __init__(self):
        # Terminal setup
        self.cols, self.rows = get_terminal_size()
        
        # Audio setup
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            input_device_index=INPUT_INDEX,
            frames_per_buffer=CHUNK
        )
        
        # Audio processing state
        self.prev_fft = np.zeros(FFT_SIZE)
        self.is_silent = False
        
        # Performance tracking
        self.last_frame_time = time.time()
        self.frame_times = []
        self.slow_frames = 0
        self.total_slow_frame_time = 0
        
        # Derived classes can add their own state here
        self.setup()
        
        logger.info(f"Visualizer initialized with {self.cols}x{self.rows} terminal size")
        logger.info(f"System memory: {psutil.virtual_memory().total / (1024*1024):.0f}MB")
    
    def setup(self):
        """Override this method to initialize visualizer-specific state"""
        pass
    
    def process_audio(self):
        """Process audio input and return audio features"""
        data = self.stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)[::2]
        
        # Check for silence
        self.is_silent = np.max(np.abs(samples)) < SILENCE_THRESHOLD
        if self.is_silent:
            return None, None, None, None, None
        
        # FFT processing
        fft = np.abs(np.fft.fft(samples))[:FFT_SIZE]
        fft = median_filter(fft, size=3)
        fft = fft / (np.max(fft) + 1e-6)
        fft = SMOOTHING * self.prev_fft + (1 - SMOOTHING) * fft
        self.prev_fft = fft.copy()
        
        # Extract common features
        low_energy = np.mean(fft[:8])
        high_energy = np.mean(fft[32:])
        total_energy = np.mean(fft)
        
        return samples, fft, low_energy, high_energy, total_energy
    
    def clear_screen(self):
        """Clear the terminal screen"""
        print("\033[2J\033[H", end="")
    
    def draw(self, samples, fft, low_energy, high_energy, total_energy):
        """Override this method to implement visualizer-specific drawing logic"""
        raise NotImplementedError("Visualizer must implement draw() method")
    
    def log_performance_metrics(self):
        """Log performance metrics for the current frame"""
        current_time = time.time()
        frame_time = current_time - self.last_frame_time
        
        # Track slow frames (frames that take longer than expected)
        if frame_time > FRAME_DELAY * 2:  # More than 2x the expected frame time
            self.slow_frames += 1
            self.total_slow_frame_time += frame_time
            mem_info = process.memory_info()
            logger.warning(
                f"Slow frame detected: {frame_time:.1f}s (expected {FRAME_DELAY:.3f}s)\n"
                f"  Memory: {mem_info.rss / (1024*1024):.0f}MB RSS\n"
                f"  System memory: {psutil.virtual_memory().percent}% used"
            )
        
        self.frame_times.append(frame_time)
        
        # Keep only last 100 frame times for rolling average
        if len(self.frame_times) > 100:
            self.frame_times.pop(0)
        
        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
        fps = 1.0 / avg_frame_time if avg_frame_time > 0 else 0
        
        # Log frame time and GC stats
        logger.debug(
            f"Frame: {frame_time*1000:.1f}ms (target: {FRAME_DELAY*1000:.1f}ms), "
            f"FPS: {fps:.1f}, Memory: {process.memory_info().rss / (1024*1024):.0f}MB"
        )
        
        if gc_collection_count > 0:
            avg_gc_time = gc_collection_time / gc_collection_count
            logger.debug(f"GC: {gc_collection_count} collections, avg {avg_gc_time*1000:.1f}ms")
        
        self.last_frame_time = current_time
    
    def print_gc_stats(self):
        """Print GC statistics collected during runtime"""
        if gc_collection_count > 0:
            stats_msg = "\nGC Statistics:\n"
            stats_msg += f"Total collections: {gc_collection_count}\n"
            stats_msg += f"Total GC time: {gc_collection_time:.3f}s\n"
            stats_msg += f"Average GC time: {(gc_collection_time/gc_collection_count)*1000:.1f}ms\n"
            logger.info(stats_msg)
        
        if self.slow_frames > 0:
            frame_msg = "\nFrame Statistics:\n"
            frame_msg += f"Total slow frames: {self.slow_frames}\n"
            frame_msg += f"Total slow frame time: {self.total_slow_frame_time:.1f}s\n"
            frame_msg += f"Average slow frame time: {(self.total_slow_frame_time/self.slow_frames):.1f}s\n"
            logger.info(frame_msg)
    
    def run(self):
        """Main loop that handles audio processing and drawing"""
        logger.info("Starting main loop")
        
        try:
            while True:
                # Process audio
                audio_features = self.process_audio()
                if audio_features[0] is None:  # Silent
                    self.clear_screen()
                    self.draw(None, None, None, None, None)
                    time.sleep(FRAME_DELAY)
                    continue
                
                samples, fft, low_energy, high_energy, total_energy = audio_features
                
                # Clear screen and draw
                self.clear_screen()
                self.draw(samples, fft, low_energy, high_energy, total_energy)
                
                # Log performance metrics
                self.log_performance_metrics()
                
                # Maintain frame rate
                time.sleep(FRAME_DELAY)
                
        except KeyboardInterrupt:
            logger.info("Visualizer stopped by user")
            print("\nVisualizer stopped.")
            self.stream.stop_stream()
            self.stream.close()
            self.p.terminate()
            self.print_gc_stats()
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}", exc_info=True)
            raise
    
    def cleanup(self):
        """Override this method to implement visualizer-specific cleanup"""
        pass



