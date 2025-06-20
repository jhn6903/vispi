#!/usr/bin/env python3
import numpy as np
import pyaudio
import time
import sys
import psutil
import subprocess
from datetime import datetime

"""
This script will test the audio interface latency and clarity

This is accomplished by:
1. Reading audio data from the input stream
2. Playing the audio data back to the output stream
3. Measuring the time it takes to read the audio data and play it back
4. Printing the statistics to the console

You can actually hear "what the pi hears" by running the script listening to the output of the interface.
This can be helpful to tune the interface configuration for the best performance.
"""

# Audio configuration
CHUNK = 2048
RATE = 48000
FORMAT = pyaudio.paInt16
CHANNELS = 2
INPUT_INDEX = 1  # Default to index 1, can be changed
OUTPUT_INDEX = 1  # Default to index 0 for output

# Timing thresholds (in seconds)
FREEZE_THRESHOLD = 0.1  # Consider it a freeze if read takes longer than this
WARNING_THRESHOLD = 0.05  # Warning if read takes longer than this

class AudioLatencyTest:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.setup_audio()
        self.last_read_time = time.time()
        self.freeze_count = 0
        self.warning_count = 0
        self.total_reads = 0
        self.last_stats_time = time.time()
        self.process = psutil.Process()
        
    def get_system_stats(self):
        """Get current system statistics"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        usb_info = subprocess.check_output('lsusb -t', shell=True).decode()
        return {
            'cpu': cpu_percent,
            'memory_percent': memory.percent,
            'usb_info': usb_info
        }
        
    def setup_audio(self):
        """Initialize audio streams and verify devices"""
        try:
            # List available devices
            print("\nAvailable audio devices:")
            for i in range(self.p.get_device_count()):
                dev_info = self.p.get_device_info_by_index(i)
                print(f"Device {i}: {dev_info['name']}")
            
            # Try to open input stream
            self.input_stream = self.p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=INPUT_INDEX,
                frames_per_buffer=CHUNK
            )
            print(f"\nSuccessfully opened input stream on device {INPUT_INDEX}")
            
            # Try to open output stream
            self.output_stream = self.p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                output_device_index=OUTPUT_INDEX,
                frames_per_buffer=CHUNK
            )
            print(f"Successfully opened output stream on device {OUTPUT_INDEX}")
            
            # Print initial system stats
            stats = self.get_system_stats()
            print("\nInitial System State:")
            print(f"CPU Usage: {stats['cpu']}%")
            print(f"Memory Usage: {stats['memory_percent']}%")
            print("\nUSB Device Tree:")
            print(stats['usb_info'])
            
        except Exception as e:
            print(f"\nError setting up audio: {str(e)}")
            self.cleanup()
            sys.exit(1)
    
    def read_and_play_audio(self):
        """Read audio data, measure timing, and play it back"""
        start_time = time.time()
        
        try:
            # Read audio data
            data = self.input_stream.read(CHUNK, exception_on_overflow=False)
            read_time = time.time() - start_time
            
            # Calculate time since last read
            time_since_last = start_time - self.last_read_time
            self.last_read_time = start_time
            
            # Process timing information
            self.total_reads += 1
            
            if read_time > FREEZE_THRESHOLD:
                self.freeze_count += 1
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] FREEZE DETECTED!")
                print(f"Read time: {read_time:.3f}s")
                print(f"Time since last read: {time_since_last:.3f}s")
                
                # Get system stats during freeze
                stats = self.get_system_stats()
                print(f"CPU Usage: {stats['cpu']}%")
                print(f"Memory Usage: {stats['memory_percent']}%")
                
            elif read_time > WARNING_THRESHOLD:
                self.warning_count += 1
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Warning: Slow read")
                print(f"Read time: {read_time:.3f}s")
            
            # Play back the audio
            self.output_stream.write(data)
            
            # Print statistics every 100 reads
            if self.total_reads % 100 == 0:
                self.print_stats()
            
            return read_time
            
        except Exception as e:
            print(f"\nError in audio processing: {str(e)}")
            return None
    
    def print_stats(self):
        """Print current statistics"""
        stats = self.get_system_stats()
        print("\n=== Audio Interface Statistics ===")
        print(f"Total reads: {self.total_reads}")
        print(f"Freezes detected: {self.freeze_count}")
        print(f"Warnings: {self.warning_count}")
        if self.total_reads > 0:
            print(f"Freeze rate: {(self.freeze_count/self.total_reads)*100:.1f}%")
        print("\n=== System Statistics ===")
        print(f"CPU Usage: {stats['cpu']}%")
        print(f"Memory Usage: {stats['memory_percent']}%")
        print("================================")
    
    def run(self):
        """Main test loop"""
        print("\nStarting audio latency test with playback...")
        print("Press Ctrl+C to exit")
        print(f"Freeze threshold: {FREEZE_THRESHOLD}s")
        print(f"Warning threshold: {WARNING_THRESHOLD}s")
        
        try:
            while True:
                self.read_and_play_audio()
                time.sleep(0.01)  # Small delay to prevent CPU overuse
                
        except KeyboardInterrupt:
            print("\nTest stopped by user")
            self.print_stats()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up audio resources"""
        if hasattr(self, 'input_stream'):
            self.input_stream.stop_stream()
            self.input_stream.close()
        if hasattr(self, 'output_stream'):
            self.output_stream.stop_stream()
            self.output_stream.close()
        self.p.terminate()

if __name__ == "__main__":
    test = AudioLatencyTest()
    test.run()
