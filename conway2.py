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
display_buffer = np.zeros((WAVEFORM_HEIGHT, WAVEFORM_WIDTH))  # Persistent display buffer

# === CONWAY CONFIG ===
cell_chars = ['█', '▓', '▒', '░']
COLORS = [
    '\033[38;2;85;107;47m',      # Dark Olive Green
    '\033[38;2;210;180;140m',    # Tan
    '\033[38;2;255;182;193m',    # Light Pink
    '\033[38;2;176;224;230m',    # Powder Blue
    '\033[38;2;152;251;152m',    # Pale Green 
    '\033[38;2;255;218;185m',    # Peach
    '\033[38;2;230;230;250m',    # Lavender
    '\033[38;2;255;228;196m',    # Bisque
]
RESET_COLOR = '\033[0m'
MODE_SWITCH_INTERVAL = 3  # seconds
last_mode_switch = time.time()
current_mode = "waveform"  # or "conway"

def get_neighbors(grid, x, y):
    """Count live neighbors for a cell."""
    count = 0
    for i in range(-1, 2):
        for j in range(-1, 2):
            if i == 0 and j == 0:
                continue
            new_x = x + i
            new_y = y + j
            # Only count neighbors that are within bounds
            if 0 <= new_x < WAVEFORM_WIDTH and 0 <= new_y < WAVEFORM_HEIGHT:
                count += grid[new_y, new_x]
    return count

def next_generation():
    """Calculate the next generation of cells."""
    global display_buffer
    new_grid = np.zeros_like(display_buffer)
    
    for y in range(WAVEFORM_HEIGHT):
        for x in range(WAVEFORM_WIDTH):
            neighbors = get_neighbors(display_buffer, x, y)
            if display_buffer[y, x]:  # Live cell
                new_grid[y, x] = 1 if neighbors in [2, 3] else 0
            else:  # Dead cell
                new_grid[y, x] = 1 if neighbors == 3 else 0
    
    display_buffer = new_grid

def display_conway():
    """Display the Conway grid with colors."""
    global display_buffer
    print('\033[H', end='')
    for row in range(WAVEFORM_HEIGHT):
        line = ''
        for col in range(WAVEFORM_WIDTH):
            if display_buffer[row, col]:
                # Cycle through colors based on cell position
                color_idx = (row + col) % len(COLORS)
                # Randomly select a character from cell_chars
                char_idx = (row * col) % len(cell_chars)
                line += COLORS[color_idx] + cell_chars[char_idx] + RESET_COLOR
            else:
                line += ' '
        print(line, end='\r\n', flush=True)

def display_waveform(bounce_energy: float):
    """Display the bounce energy as a tall scrolling waveform using the full screen height."""
    global waveform_buffer, display_buffer
    
    # Shift buffer right and add new value
    waveform_buffer[1:] = waveform_buffer[:-1]  # Shift all values right by one
    waveform_buffer[0] = bounce_energy  # Add new value at the left
    
    # Shift the display buffer right
    display_buffer[:, 1:] = display_buffer[:, :-1]  # Shift all values right by one
    display_buffer[:, 0] = 0  # Clear the leftmost column
    
    # Add new waveform column
    height = int(bounce_energy * WAVEFORM_HEIGHT)
    if height > 0:
        display_buffer[WAVEFORM_HEIGHT-height:, 0] = 1
    
    # Move cursor to top-left without clearing screen
    print('\033[H', end='')
    
    # Display using block characters
    blocks = '▁▂▃▄▅▆▇█'
    for row in range(WAVEFORM_HEIGHT):
        waveform_line = ''
        for col in range(WAVEFORM_WIDTH):
            if display_buffer[row, col]:
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
        # Check if it's time to switch modes
        current_time = time.time()
        if current_time - last_mode_switch > MODE_SWITCH_INTERVAL:
            current_mode = "conway" if current_mode == "waveform" else "waveform"
            last_mode_switch = current_time
        
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
        
        if current_mode == "waveform":
            display_waveform(bounce_energy)
        else:  # conway mode
            display_conway()
            next_generation()
        
        prev_fft = fft.copy()
        
        # Consistent frame rate
        time.sleep(1/60)  # 60 FPS

except KeyboardInterrupt:
    print('\033[?25h', end='')  # Show cursor
    print('\033[2J', end='')    # Clear screen
    print("\nVisualizer stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
