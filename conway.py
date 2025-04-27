import numpy as np
import pyaudio
import random
import time
import sys
import shutil
from scipy.ndimage import median_filter
from typing import Tuple, List

cell_chars = ['█', '▓', '▒', '░']

# === TERMINAL CONFIG ===
def get_terminal_size():
    return shutil.get_terminal_size()

cols, rows = get_terminal_size()

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def create_grid(width: int, height: int) -> List[List[int]]:
    """Create an empty initial grid."""
    return [[0 for _ in range(width)] for _ in range(height)]

def get_neighbors(grid: List[List[int]], x: int, y: int) -> int:
    """Count live neighbors for a cell."""
    height, width = len(grid), len(grid[0])
    count = 0
    
    for i in range(-1, 2):
        for j in range(-1, 2):
            if i == 0 and j == 0:
                continue
            new_x, new_y = (x + i) % width, (y + j) % height
            count += grid[new_y][new_x]
    
    return count

def next_generation(grid: List[List[int]]) -> List[List[int]]:
    """Calculate the next generation of cells using classic Game of Life rules plus random death."""
    height, width = len(grid), len(grid[0])
    new_grid = [[0 for _ in range(width)] for _ in range(height)]
    
    # Calculate current density of live cells
    total_cells = width * height
    live_cells = sum(sum(row) for row in grid)
    density = live_cells / total_cells
    
    for y in range(height):
        for x in range(width):
            neighbors = get_neighbors(grid, x, y)
            if grid[y][x]:  # Live cell
                # Classic survival rules: 2 or 3 neighbors
                survives = neighbors in [2, 3]
                new_grid[y][x] = 1 if survives else 0
            else:  # Dead cell
                # Classic birth rule: exactly 3 neighbors
                new_grid[y][x] = 1 if neighbors == 3 else 0
    
    return new_grid

# === COLORS ===
colors = [
    "\033[91m", "\033[92m", "\033[93m",
    "\033[94m", "\033[95m", "\033[96m"
]
RESET = "\033[0m"

def display_grid(grid: List[List[int]], use_color: bool = False):
    """Display the grid using cell_chars and optional colors."""
    print('\033[H', end='')
    for row in grid:
        line = []
        for cell in row:
            if cell:
                char = random.choice(cell_chars)
                if use_color:
                    color = random.choice(colors)
                    line.append(f"{color}{char}{RESET}")
                else:
                    line.append(char)
            else:
                line.append(' ')
        print(''.join(line), end='\r\n', flush=True)

def generate_triplet(grid: List[List[int]]) -> None:
    """Generate a triplet (three cells in a line) at a random location."""
    height, width = len(grid), len(grid[0])
    # Pick random starting point
    x = random.randint(0, width-1)
    y = random.randint(0, height-1)
    
    # Randomly choose orientation (horizontal or vertical)
    if random.random() < 0.5:  # horizontal
        # Make sure triplet fits within bounds
        x = random.randint(0, width-3)
        grid[y][x:x+3] = [1, 1, 1]
    else:  # vertical
        # Make sure triplet fits within bounds
        y = random.randint(0, height-3)
        for i in range(3):
            grid[y+i][x] = 1

def get_position_from_fft(fft: np.ndarray, width: int, height: int) -> Tuple[int, int]:
    """
    Map FFT bins radially: low frequencies (bass) in center, high frequencies at edges.
    Uses polar coordinates for mapping.
    """
    # Ensure probabilities sum to 1 by using softmax-style normalization
    exp_fft = np.exp(fft - np.max(fft))  # Subtract max for numerical stability
    fft_normalized = exp_fft / np.sum(exp_fft)
    
    # Choose a frequency bin based on its energy
    chosen_bin = np.random.choice(64, p=fft_normalized)
    
    # Map bin number (0-63) to radius (0 = center, 1 = edge)
    radius_factor = chosen_bin / 63.0
    
    # Get random angle
    angle = random.random() * 2 * np.pi
    
    # Calculate center of grid
    center_x = width / 2
    center_y = height / 2
    
    # Convert polar to cartesian coordinates
    max_radius = min(width, height) / 2
    x = int(center_x + np.cos(angle) * radius_factor * max_radius)
    y = int(center_y + np.sin(angle) * radius_factor * max_radius)
    
    # Ensure coordinates are within bounds
    x = max(0, min(width-1, x))
    y = max(0, min(height-1, y))
    
    return x, y

def generate_pattern(grid: List[List[int]], fft: np.ndarray = None) -> None:
    """Generate a pattern at a position determined by FFT energy."""
    height, width = len(grid), len(grid[0])
    
    if fft is not None:
        x, y = get_position_from_fft(fft, width, height)
    else:
        # Fallback to random position if no FFT data
        x = random.randint(0, width-1)
        y = random.randint(0, height-1)
    
    patterns = [
        # Triplet (horizontal and vertical handled separately)
        ([[1, 1, 1]], 3, 1),
        ([[1], [1], [1]], 1, 3),
        
        # L-shape
        ([[1, 1], 
          [1, 0]], 2, 2),
        
        # Square block
        ([[1, 1],
          [1, 1]], 2, 2),
        
        # Glider
        ([[0, 1, 0],
          [0, 0, 1],
          [1, 1, 1]], 3, 3),
        
        # T-shape
        ([[1, 1, 1],
          [0, 1, 0]], 3, 2),
        
        # Plus shape
        ([[0, 1, 0],
          [1, 1, 1],
          [0, 1, 0]], 3, 3)
    ]
    
    pattern, pat_width, pat_height = random.choice(patterns)
    
    # Wrap x coordinate around the width of the grid instead of clamping
    x = x % (width - pat_width + 1)
    # Clamp y coordinate to ensure pattern fits vertically
    y = min(y, height - pat_height)
    
    # Place the pattern
    for dy in range(pat_height):
        for dx in range(pat_width):
            grid[y + dy][x + dx] = pattern[dy][dx]


# === AUDIO CONFIG ===
CHUNK = 1024
RATE = 48000
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = None

# === TERMINAL CONFIG ===
def get_terminal_size():
    return shutil.get_terminal_size(fallback=(80, 24))

cols, rows = get_terminal_size()
RESET = "\033[0m"

# === COLORS ===
colors = [
    "\033[91m", "\033[92m", "\033[93m",
    "\033[94m", "\033[95m", "\033[96m"
]



def get_low_energy(fft):
    """Extracts the kick energy from the FFT."""
    return int(np.mean(fft[:8]) * 100)

def get_high_energy(fft):
    """Extracts the hi-hat energy from the FFT."""
    return fft[-32]

def get_total_energy(fft):
    """Get total energy across all frequency bands."""
    return np.mean(fft)

def get_grid_density(grid):
    """Calculate the density of live cells in the grid."""
    total_cells = len(grid) * len(grid[0])
    live_cells = sum(sum(row) for row in grid)
    return (live_cells / total_cells) * 100

mantra = "Let the Making It Happen Happen"

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

# Initialize Conway's Game of Life grid
cols, rows = get_terminal_size()
# Reduce grid height by 2 to make room for status lines
grid = create_grid(width=cols-2, height=rows-3)
patterns_generated = 0

def get_position_from_fft(fft: np.ndarray, width: int, height: int) -> Tuple[int, int]:
    """
    Map FFT bins radially: low frequencies (bass) in center, high frequencies at edges.
    Uses polar coordinates for mapping.
    """
    # Ensure probabilities sum to 1 by using softmax-style normalization
    exp_fft = np.exp(fft - np.max(fft))  # Subtract max for numerical stability
    fft_normalized = exp_fft / np.sum(exp_fft)
    
    # Choose a frequency bin based on its energy
    chosen_bin = np.random.choice(64, p=fft_normalized)
    
    # Map bin number (0-63) to radius (0 = center, 1 = edge)
    radius_factor = chosen_bin / 63.0
    
    # Get random angle
    angle = random.random() * 2 * np.pi
    
    # Calculate center of grid
    center_x = width / 2
    center_y = height / 2
    
    # Convert polar to cartesian coordinates
    max_radius = min(width, height) / 2
    x = int(center_x + np.cos(angle) * radius_factor * max_radius)
    y = int(center_y + np.sin(angle) * radius_factor * max_radius)
    
    # Ensure coordinates are within bounds
    x = max(0, min(width-1, x))
    y = max(0, min(height-1, y))
    
    return x, y

def display_status(kick_val: int, hat_val: float, total_energy: float, patterns_generated: int, fft: np.ndarray):
    """Display status line at the bottom of the terminal."""
    
    # Get terminal dimensions
    terminal_width, terminal_height = get_terminal_size()
    
    # Move cursor to bottom line and clear it
    print(f"\033[{terminal_height-1};0H", end='')
    print("\033[K", end='')
    
    # Create FFT histogram using blocks
    blocks = '▁▂▃▄▅▆▇█'
    histogram = ''
    for val in fft:
        block_idx = min(int(val * len(blocks)), len(blocks) - 1)
        histogram += blocks[block_idx]
    
    # Display FFT histogram
    print(histogram, end='\r\n', flush=True)
    
    # Display status line
    print(f"\033[{terminal_height};0H", end='')
    print("\033[K", end='')
    status = f"Kick: {kick_val:3d} | Hat: {hat_val:.2f} | Energy: {total_energy:.2f} | Density: {get_grid_density(grid):.2f} | Patterns: {patterns_generated}"
    print(status, end='', flush=True)


# === MAIN LOOP ===
try:
    print('\033[?25l', end='')  # Hide cursor
    while True:
        data = stream.read(CHUNK, exception_on_overflow=False)
        samples = np.frombuffer(data, dtype=np.int16)
        is_silent = np.max(np.abs(samples)) < 100

        if is_silent:
            time.sleep(1/30)
            continue

        # Calculate FFT
        fft = np.abs(np.fft.fft(samples))[:64]
        
        # Apply frequency weighting (approximating A-weighting curve)
        # Higher frequencies get progressively more emphasis
        freq_weights = np.linspace(1.0, 2.5, 64)  # Linear increase from 1.0 to 2.5
        fft = fft * freq_weights
        
        # Continue with existing processing
        fft = median_filter(fft, size=3)
        fft = fft / (np.max(fft) + 1e-6)
        fft = SMOOTHING * prev_fft + (1 - SMOOTHING) * fft
        prev_fft = fft.copy()

        lo_energy = get_low_energy(fft)
        hi_energy = get_high_energy(fft)
        total_energy = get_total_energy(fft)
        density = get_grid_density(grid)
        
        # Mass extinction event if energy is low but density is high
        if total_energy < 0.2 and density > 0.3:
            height, width = len(grid), len(grid[0])
            for y in range(height):
                for x in range(width):
                    if random.random() < 0.5:  # 50% chance to die
                        grid[y][x] = 0
        
        patterns_to_generate = int((lo_energy / 100) * 5)
        
        # Generate patterns proportional to energy
        for _ in range(patterns_to_generate):
            generate_pattern(grid, fft)
            patterns_generated += 1

        # Update and display the game state
        use_color = hi_energy > 0.05
        display_grid(grid, use_color=use_color)
        display_status(lo_energy, hi_energy, total_energy, patterns_generated, fft)
        grid = next_generation(grid)
        
        time.sleep(0.01)

except KeyboardInterrupt:
    print('\033[?25h', end='')  # Show cursor
    print(RESET)
    print("\nVisualizer stopped.")
    stream.stop_stream()
    stream.close()
    p.terminate()
