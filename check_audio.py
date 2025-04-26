#!/usr/bin/env python3
import pyaudio

p = pyaudio.PyAudio()

print("Available Audio Devices:")
print("----------------------")

for i in range(p.get_device_count()):
    dev = p.get_device_info_by_index(i)
    print(f"\nDevice {i}:")
    print(f"  Name: {dev['name']}")
    print(f"  Max Input Channels: {dev['maxInputChannels']}")
    print(f"  Max Output Channels: {dev['maxOutputChannels']}")
    print(f"  Default Sample Rate: {dev['defaultSampleRate']}")

p.terminate() 