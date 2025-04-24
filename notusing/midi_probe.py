#!/usr/bin/env python3
"""
midi_probe.py

Improved POC: Lists MIDI input ports, prompts you to select one,
and then enters a blocking loop that reacts to every incoming message.
Displays the last 10 messages and a bar for CC#1 or Note On.
Requires: mido, python-rtmidi
"""
import mido
import sys
import shutil
from collections import deque

# === MIDI Port Selection ===
ports = mido.get_input_names()
if not ports:
    print("No MIDI input ports found. Connect a device and try again.")
    sys.exit(1)
print("Available MIDI input ports:")
for idx, name in enumerate(ports):
    print(f"  [{idx}] {name}")

# Prompt user for port index
while True:
    choice = input(f"Select port [0-{len(ports)-1}]: ")
    if choice.isdigit() and 0 <= int(choice) < len(ports):
        port_idx = int(choice)
        break
    print("Invalid selection, please try again.")

inport_name = ports[port_idx]
print(f"Opening MIDI input port: {inport_name}")
inport = mido.open_input(inport_name)

# === Diagnostics and Bar ===
diagnostics = deque(maxlen=10)
level = 0.0     # normalized 0.0–1.0
BAR_WIDTH = 50  # characters

def redraw():
    # move cursor home and clear from there
    sys.stdout.write("\033[H\033[J")
    print("Last MIDI messages:")
    for line in diagnostics:
        print("  ", line)
    filled = int(level * BAR_WIDTH)
    empty = BAR_WIDTH - filled
    print("\nMIDI Level (CC#1 or Note On velocity):")
    print("[" + "█" * filled + " " * empty + "]", f"{level:.2f}")
    sys.stdout.flush()

# Initial clear
import sys
sys.stdout.write("\033[2J\033[H")
print("Listening for MIDI. Press Ctrl+C to exit.\n")

# === Main Loop ===
try:
    for msg in inport:
        # Append to diagnostics
        diagnostics.append(str(msg))
        # Map CC#1 or Note On to level
        if msg.type == 'control_change' and msg.control == 1:
            level = msg.value / 127.0
        elif msg.type == 'note_on':
            level = msg.velocity / 127.0
        redraw()
except KeyboardInterrupt:
    print("\nExiting midi_probe")
    sys.exit(0)
