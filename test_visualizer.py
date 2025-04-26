#!/usr/bin/env python3
"""
Test script to run and log visualizer output
"""
import subprocess
import time
import os
import sys
import signal
from datetime import datetime

LOG_FILE = "/tmp/visualizer_test.log"
VIS_LOG_FILE = "/tmp/routercore2.log"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
    print(f"[{timestamp}] {msg}")

def check_vis_log():
    if os.path.exists(VIS_LOG_FILE):
        with open(VIS_LOG_FILE, 'r') as f:
            return f.read()
    return ""

def main():
    visualizer = "routercore2.py"
    log(f"Starting test of {visualizer}")
    
    try:
        # Run the visualizer
        process = subprocess.Popen(
            ["python3", f"/home/vispi2/visualizers/{visualizer}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        log("Visualizer process started")
        
        # Monitor for 10 seconds
        start_time = time.time()
        last_log_check = ""
        
        while time.time() - start_time < 10:
            # Check if process is still running
            if process.poll() is not None:
                out, err = process.communicate()
                log("Process ended unexpectedly!")
                log(f"Output: {out}")
                log(f"Error: {err}")
                return
            
            # Check visualizer log
            current_log = check_vis_log()
            if current_log != last_log_check:
                log(f"Visualizer log update: {current_log}")
                last_log_check = current_log
            
            time.sleep(1)
        
        # Test pause functionality
        log("Sending 'p' to test pause...")
        process.send_signal(signal.SIGUSR1)
        time.sleep(2)
        
        # Check final state
        final_log = check_vis_log()
        if final_log != last_log_check:
            log(f"Final log state: {final_log}")
        
        # Cleanup
        process.terminate()
        time.sleep(1)
        
        out, err = process.communicate()
        if out:
            log(f"Final output: {out}")
        if err:
            log(f"Final error: {err}")
            
        log("Test completed")
        
    except Exception as e:
        log(f"Test error: {e}")
    finally:
        # Make sure process is terminated
        try:
            process.terminate()
            process.wait(timeout=2)
        except:
            try:
                process.kill()
            except:
                pass

if __name__ == "__main__":
    # Clear previous logs
    for f in [LOG_FILE, VIS_LOG_FILE]:
        if os.path.exists(f):
            os.remove(f)
    main() 