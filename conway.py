import numpy as np
import pyaudio
import random
import sys
import shutil
import time
import os
from scipy.ndimage import median_filter
from typing import Tuple, List
from common.engine import AudioEngine

# === Initialize Engine ===
engine = AudioEngine()
engine.initialize(
    interface_type="focusrite2i4",
    processor_type="default",
    debug=True
)

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
    # Ensure probabilities sum to 1 by using softmax normalization
    exp_fft = np.exp(fft - np.max(fft))  # Subtract max for numerical stability
    exp_fft = exp_fft / np.sum(exp_fft)  # Normalize to sum to 1
    
    # Choose a frequency bin based on its energy
    chosen_bin = np.random.choice(len(fft), p=exp_fft)
    
    # Map bin number to radius (0 = center, 1 = edge)
    radius_factor = chosen_bin / (len(fft) - 1)
    
    # Get random angle
    angle = random.random() * 2 * np.pi
    
    # Calculate center of grid
    center_x = width / 2
    center_y = height / 2
    
    # Convert polar to cartesian coordinates
    max_radius = max(width, height) / 3
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


def get_grid_density(grid):
    """Calculate the density of live cells in the grid."""
    total_cells = len(grid) * len(grid[0])
    live_cells = sum(sum(row) for row in grid)
    return (live_cells / total_cells) * 100

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
    density = get_grid_density(grid)
    status = f"Kick: {kick_val:3d} | Hat: {hat_val:.2f} | Energy: {total_energy:.2f} | Density: {density:.2f} | Patterns: {patterns_generated}"
    print(status, end='', flush=True)

# === STATE ===
# Initialize Conway's Game of Life grid
cols, rows = get_terminal_size()
# Reduce grid height by 2 to make room for status lines
grid = create_grid(width=cols-2, height=rows-3)

state = {
    "patterns_generated": 0,
    "grid": grid
}


# === Main Loop Function ===
def main_loop(data):
    """Main Conway's Game of Life loop that receives processed audio data from engine"""
    
    if data["is_silent"]:
        # Continue evolution even during silence, but don't generate new patterns
        state["grid"] = next_generation(state["grid"])
        display_grid(state["grid"], use_color=False)
        return

    # Get processed audio data from engine
    fft = data["fft"]  # Already processed and normalized by engine
    total_energy = data["total_energy"]
    low_energy = data["low_energy"]
    high_energy = data["high_energy"]

    # Convert engine's normalized values back to our expected ranges
    lo_energy = int(low_energy * 100)  # Convert 0-1 to 0-100 range
    hi_energy = high_energy
    
    density = get_grid_density(state["grid"])
    density_factor = 0.5
    energy_factor = 10
    
    # Probabilistic mass extinction based on energy and density
    # extinction_probability = np.clip(density*density_factor - total_energy*energy_factor, 0, 1)
    # if random.random() < extinction_probability:
    #     height, width = len(state["grid"]), len(state["grid"][0])
    #     for y in range(height):
    #         for x in range(width):
    #             # Skip cells at the boundaries
    #             if x == 0 or x == width-1 or y == 0 or y == height-1:
    #                 continue
    #             center_x = width / 2
    #             # Distance factor: 0 at center, 1 at edges
    #             distance_factor = (abs(center_x - x) / center_x)**2
    #             # Reduce death probability for cells far from center
    #             death_probability = max(0, extinction_probability - distance_factor)
    #             if random.random() < death_probability:
    #                 state["grid"][y][x] = 0
    
    gen_coeff = 0.45
    patterns_to_generate = int((data["kick_energy"] + data["snare_energy"] + data["hat_energy"]) * gen_coeff)
    
    # Generate patterns proportional to energy
    for _ in range(patterns_to_generate):
        generate_pattern(state["grid"], fft)
        state["patterns_generated"] += 1

    # Update and display the game state
    use_color = data["kick_energy"] > 0.2
    display_grid(state["grid"], use_color=use_color)
    display_status(lo_energy, hi_energy, total_energy, state["patterns_generated"], fft)
    state["grid"] = next_generation(state["grid"])
    time.sleep(min(0.2 / engine.fps, (0.4 / engine.fps) * ((data["kick_energy"] + data["snare_energy"] + data["hat_energy"])/gen_coeff)))

# === Run Engine ===
print('\033[?25l', end='')  # Hide cursor
print("[conway] Starting Conway's Game of Life with engine...")
try:
    engine.run(main_loop)
except KeyboardInterrupt:
    print('\033[?25h', end='')  # Show cursor
    print(RESET)
    print("\nVisualizer stopped.")
