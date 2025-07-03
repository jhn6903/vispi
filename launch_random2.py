#!/usr/bin/env python3
import subprocess
import sys
import time
import random
from common.config import supported_visualizers

try:
    # Launch each visualizer as a subprocess
    while True:
        for visualizer in supported_visualizers:
            subprocess.Popen([sys.executable, f"{visualizer}.py"])
            # sleep for a random amount of time between 1 and 2 seconds
            time.sleep(random.uniform(5, 60))
            # close the process
            subprocess.Popen(["pkill", "-f", f"{visualizer}.py"])
            time.sleep(1)
            
except KeyboardInterrupt:
    print("\nExiting...")
    # close the processes
    for visualizer in supported_visualizers:
        subprocess.Popen(["pkill", "-f", f"{visualizer}.py"])
    sys.exit(0)
