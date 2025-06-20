#!/usr/bin/env python3
"""
Energy Debug Visualization
Full-screen display of all energy values from the audio engine
"""

import time
from common import engine

# === SETUP ===
engine_data = engine.initialize(debug=False)
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

def draw_bar(value, max_width, label, color_code):
    """Draw a horizontal bar with label"""
    bar_width = int(value * max_width)
    bar = "█" * bar_width + "░" * (max_width - bar_width)
    percentage = int(value * 100)
    line = f"{color_code}{label:12}: [{bar}] {percentage:3d}%\033[0m"
    # Pad line to full width to overwrite previous content
    return line + " " * max(0, cols - len(label) - max_width - 20)

def draw_history_graph(history, max_width, label, color_code):
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
    line = f"{color_code}{label:12}: {graph} {percentage:3d}%\033[0m"
    # Pad line to full width to overwrite previous content
    return line + " " * max(0, cols - len(label) - max_width - 20)

def main_loop(data):
    if data["is_silent"]:
        print("\033[H", end="")  # Just move cursor to home, don't clear
        print("Waiting for audio..." + " " * (cols - 20))  # Pad to clear previous text
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
    
    # Calculate display dimensions
    graph_width = cols - 20  # Leave space for labels and percentages
    
    # History graphs
    print("\033[1;33mHISTORY TIMELINE:\033[0m")
    print(draw_history_graph(state["history"]["total_energy"], graph_width, "Total Energy", "\033[97m"))
    print(draw_history_graph(state["history"]["low_energy"], graph_width, "Low Energy", "\033[94m"))
    print(draw_history_graph(state["history"]["high_energy"], graph_width, "High Energy", "\033[91m"))
    print(draw_history_graph(state["history"]["kick_energy"], graph_width, "Kick Energy", "\033[92m"))
    print(draw_history_graph(state["history"]["snare_energy"], graph_width, "Snare Energy", "\033[93m"))
    print(draw_history_graph(state["history"]["hat_energy"], graph_width, "Hat Energy", "\033[95m"))
    print()
    
    # FFT spectrum - full spectrum display
    fft_len = len(data["fft"])
    spectrum_width = min(fft_len, graph_width)
    print(f"\033[1;33mFFT SPECTRUM (all {fft_len} bins):\033[0m" + " " * (cols - 30))
    
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
    
    print(f"\033[96m{fft_display}\033[0m" + " " * max(0, cols - len(fft_display)))

# === RUN ===
engine.run(engine_data, main_loop)