import numpy as np
import pyaudio
import time
import sys
import shutil
from scipy.ndimage import median_filter

# === TERMINAL CONFIG ===
def get_terminal_size():
    return shutil.get_terminal_size()

cols, rows = get_terminal_size()

# Initialize waveform buffer
WAVEFORM_WIDTH = cols
WAVEFORM_HEIGHT = rows - 1  # Leave one line for cursor
waveform_buffer = np.zeros(WAVEFORM_WIDTH)

def display_waveform(bounce_energy: float):
    """Display the bounce energy as a tall scrolling waveform using the full screen height."""
    global waveform_buffer
    
    # Shift buffer right and add new value
    waveform_buffer = np.roll(waveform_buffer, 1)
    waveform_buffer[0] = bounce_energy
    
    # Move cursor to top-left without clearing screen
    print('\033[H', end='')
    
    # Create a 2D array for the full height display
    display = np.zeros((WAVEFORM_HEIGHT, WAVEFORM_WIDTH))
    
    # Fill the display array based on the waveform height
    for x in range(WAVEFORM_WIDTH):
        height = int(waveform_buffer[x] * WAVEFORM_HEIGHT)
        if height > 0:
            display[WAVEFORM_HEIGHT-height:, x] = 1
    
    # Display using block characters
    blocks = '▁▂▃▄▅▆▇█'
    for row in range(WAVEFORM_HEIGHT):
        waveform_line = ''
        for col in range(WAVEFORM_WIDTH):
            if display[row, col]:
                # Use different blocks based on position in the waveform
                block_idx = min(int((WAVEFORM_HEIGHT - row) / WAVEFORM_HEIGHT * len(blocks)), len(blocks) - 1)
                waveform_line += blocks[block_idx]
            else:
                waveform_line += ' '
        print(waveform_line, end='\r\n', flush=True)

# === AUDIO CONFIG ===
CHUNK = 1024
RATE = 48000
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = None

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

# Initialize bounce tracking
prev_bounce_energy = 0.0
max_bounce_energy = 0.0
ENERGY_DECAY = 1

def get_bounce_energy(fft: np.ndarray, prev_fft: np.ndarray, decay_rate: float = 0.95) -> float:
    """
    Calculate a bounce energy value (0-1) based on the kick drum frequencies.
    Focuses on the low frequency range (50-100 Hz) where kick drums typically reside.
    """
    global max_bounce_energy
    
    # Calculate frequency bins for kick drum range
    # For 48kHz sample rate and 1024 chunk size:
    # bin 0 = 0 Hz
    # bin 1 = 46.875 Hz
    # bin 2 = 93.75 Hz
    # bin 3 = 140.625 Hz
    # etc.
    
    low_pass = 12

    # Focus on first 3 bins (0-140 Hz) for kick drum
    kick_bins = fft[:low_pass]
    prev_kick_bins = prev_fft[:low_pass]
    
    # Calculate energy in kick range
    kick_energy = np.mean(kick_bins)
    prev_kick_energy = np.mean(prev_kick_bins)
    
    # Calculate the rate of change in kick energy
    energy_diff = np.abs(kick_energy - prev_kick_energy)
    
    # Normalize the difference to get a 0-1 value
    normalized_diff = np.clip(energy_diff * 2, 0, 1)  # Increased multiplier for better sensitivity
    
    # Update max energy with decay
    max_bounce_energy = max(normalized_diff, max_bounce_energy * ENERGY_DECAY)
    
    # Apply exponential decay to previous bounce value
    global prev_bounce_energy
    prev_bounce_energy = max(normalized_diff, prev_bounce_energy * decay_rate)
    
    # Normalize by max observed energy
    return prev_bounce_energy / (max_bounce_energy + 1e-6)

# === MAIN LOOP ===
try:
    print('\033[?25l', end='')  # Hide cursor
    print('\033[2J', end='')    # Clear screen once at start
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)

        # Calculate FFT
        fft = np.abs(np.fft.fft(samples))[:64]
        
        # Apply frequency weighting (approximating A-weighting curve)
        freq_weights = np.linspace(1.0, 2.5, 64)  # Linear increase from 1.0 to 2.5
        fft = fft * freq_weights
        
        # Continue with existing processing
        fft = median_filter(fft, size=3)
        fft = fft / (np.max(fft) + 1e-6)
        fft = SMOOTHING * prev_fft + (1 - SMOOTHING) * fft
        
        # Calculate bounce energy
        bounce_energy = get_bounce_energy(fft, prev_fft, decay_rate=0.2)
        
        # Display waveform
        display_waveform(bounce_energy)
        
        prev_fft = fft.copy()
        
        # Consistent frame rate
        time.sleep(1/60)  # 30 FPS

except KeyboardInterrupt:
    print('\033[?25h', end='')  # Show cursor
    print('\033[2J', end='')    # Clear screen
    print("\nVisualizer stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
