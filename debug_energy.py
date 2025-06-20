#!/usr/bin/env python3
"""
Energy Debug Visualization
Full-screen display of all energy values from the audio engine
"""

import time
from common import engine

# === SETUP ===
engine_data = engine.initialize(debug=True)
cols = engine_data["cols"]
rows = engine_data["rows"]

# Clear screen once at startup
print("\033[2J\033[H", end="")

# === STATE ===
state = {
    "history": {
        "low_energy": [],
        "high_energy": [],
        "total_energy": [],
        "kick_energy": [],
        "snare_energy": [],
        "hat_energy": []
    },
    "max_history": cols - 20  # Leave space for labels
}

def draw_bar(value, max_width, label, color_code, center_padding):
    """Draw a horizontal bar with label"""
    bar_width = int(value * max_width)
    bar = "█" * bar_width + "░" * (max_width - bar_width)
    percentage = int(value * 100)
    line = " " * center_padding + f"{color_code}{label:12}: [{bar}] {percentage:3d}%\033[0m"
    # Pad line to full width to overwrite previous content
    return line + " " * max(0, cols - len(line))

def draw_history_graph(history, max_width, label, color_code, center_padding):
    """Draw a mini timeline graph of recent values"""
    if len(history) == 0:
        graph = "░" * max_width
    else:
        # Normalize history for display
        if max(history) > 0:
            normalized = [int((val / max(history)) * 3) for val in history[-max_width:]]
        else:
            normalized = [0] * len(history[-max_width:])
        
        # Create graph with different characters for different heights
        chars = ["░", "▒", "▓", "█"]
        graph = "".join(chars[min(val, 3)] for val in normalized)
        graph += "░" * (max_width - len(graph))  # Fill remaining space
    
    current_val = history[-1] if history else 0
    percentage = int(current_val * 100)
    line = " " * center_padding + f"{color_code}{label:12}: {graph} {percentage:3d}%\033[0m"
    # Pad line to full width to overwrite previous content
    return line + " " * max(0, cols - len(line))

def draw_energy_buckets(data, max_width, center_padding):
    """Draw real-time energy buckets as horizontal bars"""
    buckets = [
        ("Total Energy", data["total_energy"], "\033[97m"),      # White
        ("Low Energy", data["low_energy"], "\033[94m"),          # Blue  
        ("High Energy", data["high_energy"], "\033[91m"),        # Red
        ("Kick Energy", data["kick_energy"], "\033[92m"),        # Green
        ("Snare Energy", data["snare_energy"], "\033[93m"),      # Yellow
        ("Hat Energy", data["hat_energy"], "\033[95m")           # Magenta
    ]
    
    lines = []
    for name, value, color in buckets:
        # Calculate bar width
        bar_width = int(value * max_width)
        bar = "█" * bar_width + "░" * (max_width - bar_width)
        percentage = int(value * 100)
        line = " " * center_padding + f"{color}{name:12}: [{bar}] {percentage:3d}%\033[0m"
        lines.append(line)
    
    return lines

def main_loop(data):
    if data["is_silent"]:
        print("\033[H", end="")  # Just move cursor to home, don't clear
        center_padding = int(cols * 0.15)  # 15% padding for centering
        silence_msg = " " * center_padding + "Waiting for audio..."
        print(silence_msg + " " * max(0, cols - len(silence_msg)))
        return
    
    # Update history
    state["history"]["low_energy"].append(data["low_energy"])
    state["history"]["high_energy"].append(data["high_energy"])
    state["history"]["total_energy"].append(data["total_energy"])
    state["history"]["kick_energy"].append(data["kick_energy"])
    state["history"]["snare_energy"].append(data["snare_energy"])
    state["history"]["hat_energy"].append(data["hat_energy"])
    
    # Trim history to max length
    for key in state["history"]:
        if len(state["history"][key]) > state["max_history"]:
            state["history"][key] = state["history"][key][-state["max_history"]:]
    
    # Move cursor to home position (no clear)
    print("\033[H", end="")
    
    # Add some vertical centering
    print()  # Add blank line at top
    
    # Calculate display dimensions (20% smaller and centered)
    total_width = int(cols * 0.7)  # 70% of screen width (20% smaller)
    center_padding = int(cols * 0.15)  # 15% padding on each side for centering
    graph_width = total_width - 20  # Leave space for labels and percentages
    
    # Real-time Energy Buckets Display
    bucket_width = graph_width
    section_title = " " * center_padding + "\033[1;33mREAL-TIME ENERGY BUCKETS:\033[0m"
    print(section_title + " " * max(0, cols - len(section_title)))
    bucket_lines = draw_energy_buckets(data, bucket_width, center_padding)
    for line in bucket_lines:
        print(line + " " * max(0, cols - len(line)))
    print()
    
    # History graphs
    history_title = " " * center_padding + "\033[1;33mHISTORY TIMELINE:\033[0m"
    print(history_title + " " * max(0, cols - len(history_title)))
    print(draw_history_graph(state["history"]["total_energy"], graph_width, "Total Energy", "\033[97m", center_padding))
    print(draw_history_graph(state["history"]["low_energy"], graph_width, "Low Energy", "\033[94m", center_padding))
    print(draw_history_graph(state["history"]["high_energy"], graph_width, "High Energy", "\033[91m", center_padding))
    print(draw_history_graph(state["history"]["kick_energy"], graph_width, "Kick Energy", "\033[92m", center_padding))
    print(draw_history_graph(state["history"]["snare_energy"], graph_width, "Snare Energy", "\033[93m", center_padding))
    print(draw_history_graph(state["history"]["hat_energy"], graph_width, "Hat Energy", "\033[95m", center_padding))
    print()
    
    # FFT spectrum - full spectrum display
    fft_len = len(data["fft"])
    spectrum_width = min(fft_len, graph_width)
    fft_title = " " * center_padding + f"\033[1;33mFFT SPECTRUM (all {fft_len} bins):\033[0m"
    print(fft_title + " " * max(0, cols - len(fft_title)))
    
    fft_display = ""
    if spectrum_width < fft_len:
        # If we need to compress, sample evenly across the spectrum
        step = fft_len / spectrum_width
        for i in range(spectrum_width):
            fft_index = int(i * step)
            height = int(data["fft"][fft_index] * 4)
            chars = ["░", "▒", "▓", "█"]
            fft_display += chars[min(height, 3)]
    else:
        # If we have enough space, show all bins
        for i in range(fft_len):
            height = int(data["fft"][i] * 4)
            chars = ["░", "▒", "▓", "█"]
            fft_display += chars[min(height, 3)]
    
    fft_line = " " * center_padding + f"\033[96m{fft_display}\033[0m"
    print(fft_line + " " * max(0, cols - len(fft_line)))

# === RUN ===
engine.run(engine_data, main_loop)