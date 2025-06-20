#!/usr/bin/env python3
"""
Ultra-Simple Engine Example
"""

import time
from common import engine

# === SETUP ===
engine_data = engine.initialize()
cols = engine_data["cols"]
rows = engine_data["rows"]

# === STATE ===
state = {
    "color": 0,
}

# === MAIN LOOP ===
def main_loop(data):
    if data["is_silent"]:
        print("\033[2J\033[H", end="")
        print("Waiting for audio...")
        time.sleep(1/30)
        return
    
    # Clear and show energy
    print("\033[2J\033[H", end="")
    
    # Change color based on energy
    colors = ["\033[91m", "\033[92m", "\033[93m", "\033[94m", "\033[95m", "\033[96m"]
    energy = int(data["total_energy"] * 100)
    color = colors[state["color"] % len(colors)]
    
    # Show energy bar
    bar_length = int(data["total_energy"] * 50)
    bar = "█" * bar_length
    
    print(f"{color}Energy: {energy:3d}% {bar}\033[0m")
    
    # Cycle color
    if energy > 20:
        state["color"] += 1
    

# === RUN ===
engine.run(engine_data, main_loop)