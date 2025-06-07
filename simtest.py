import pyaudio
import numpy as np
import time

def check_blackhole_audio():
    p = pyaudio.PyAudio()
    
    # Find BlackHole device and print its capabilities
    blackhole_index = None
    for i in range(p.get_device_count()):
        dev_info = p.get_device_info_by_index(i)
        if 'BlackHole' in dev_info['name']:
            blackhole_index = i
            print(f"Found BlackHole at index {i}")
            print("Device Info:")
            print(f"  Name: {dev_info['name']}")
            print(f"  Max Input Channels: {dev_info['maxInputChannels']}")
            print(f"  Max Output Channels: {dev_info['maxOutputChannels']}")
            print(f"  Default Sample Rate: {dev_info['defaultSampleRate']}")
            break
    
    if blackhole_index is None:
        print("BlackHole not found!")
        return
    
    # Reduced buffer size and using non-blocking mode
    CHUNK = 512  # Smaller chunk size
    stream = p.open(
        format=pyaudio.paFloat32,
        channels=2,
        rate=44100,
        input=True,
        input_device_index=blackhole_index,
        frames_per_buffer=CHUNK,
        stream_callback=None,  # Using blocking mode for simplicity
        start=False  # Don't start yet
    )
    
    print("Monitoring BlackHole audio levels... (Ctrl+C to stop)")
    stream.start_stream()
    
    try:
        while True:
            try:
                data = np.frombuffer(stream.read(CHUNK, exception_on_overflow=False), dtype=np.float32)
                level = np.abs(data).mean()
                bars = int(level * 50)  # Scale for visualization
                print(f"Level: {'#' * bars}{' ' * (50-bars)} {level:.4f}", end='\r')
                time.sleep(0.01)  # Small delay to prevent CPU overuse
                
            except OSError as e:
                print(f"\nAudio buffer overflow detected: {e}")
                time.sleep(0.1)  # Give the buffer time to recover
                continue
                
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    check_blackhole_audio()