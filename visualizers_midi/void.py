#!/usr/bin/env python3
"""
voidcore_events.py

Blank by default. Numpad 1–9 toggle glitch events;
hold multiple keys at once to blend them.
‘/’, ‘*’, ‘-’ spawn ASCII explosions. Press ‘0’ for info.
Ctrl+C to quit.
"""
import os, sys, random, time, shutil
import termios, tty, fcntl
import numpy as np, pyaudio
from scipy.ndimage import median_filter

# === Load random words/phrases ===
WORDS_FILE = os.path.expanduser("~/visualizers/out_there.txt")
with open(WORDS_FILE, "r") as f:
    WORDS = [w.strip() for w in f if w.strip()]

# === Terminal geometry ===
def get_terminal_size():
    ts = shutil.get_terminal_size(fallback=(80,24))
    return ts.columns, ts.lines - 1
cols, rows = get_terminal_size()

# === Audio setup ===
CHUNK, RATE = 1024, 44100
FORMAT, CHANNELS = pyaudio.paInt16, 2
INPUT_INDEX = 1
p = pyaudio.PyAudio()
stream = p.open(format=FORMAT, channels=CHANNELS,
                rate=RATE, input=True,
                input_device_index=INPUT_INDEX,
                frames_per_buffer=CHUNK)
prev_fft = np.zeros(64)

# === Terminal input setup ===
fd = sys.stdin.fileno()
old_term = termios.tcgetattr(fd)
tty.setcbreak(fd)
old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)

def restore_terminal():
    termios.tcsetattr(fd, termios.TCSAFLUSH, old_term)
    fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)

# === Utility Draws ===
def clear_screen(): sys.stdout.write("\033[2J\033[H")

def draw_info():
    clear_screen()
    lines = [
        "voidcore_events.py INFO", "",
        "1: Word rain      2: Block bars      3: Static glitch",
        "4: Marquee text   5: Invert colors   6: Sparks",
        "7: Waveform       8: Rainbow noise   9: Mirror clear",
        " / : Radial expl   * : Asterisk burst  - : Shockwave",
        "0: Show this info", "",
        "Hold 1–9 to blend. Ctrl+C to quit.",
        "Press any key..."
    ]
    w = max(len(l) for l in lines) + 4
    h = len(lines)
    x0 = (cols - w)//2; y0 = (rows - h)//2
    for i, ln in enumerate(lines):
        sys.stdout.write(f"\033[{y0+i};{x0+2}H\033[1;37m{ln}\033[0m")
    sys.stdout.flush()
    # wait
    while True:
        if sys.stdin.read(1): break
    clear_screen()

# === Event functions ===
def event_word_rain(e):
    for _ in range(int(e*20)+1):
        w = random.choice(WORDS)
        x = random.randint(0, max(0, cols-len(w)))
        y = random.randint(0, rows-1)
        c = random.randint(31,36)
        sys.stdout.write(f"\033[{y};{x}H\033[{c}m{w}\033[0m")

def event_block_bars(e):
    for i,val in enumerate(prev_fft[:cols]):
        h = int(val*rows)
        for yy in range(rows-1, rows-1-h, -1):
            sys.stdout.write(f"\033[{yy};{i}H█")

def event_static_glitch(e):
    dens = int(cols*rows*0.15*e)+10
    chars = list("#@$%&*?=~;:")
    for _ in range(dens):
        x = random.randint(0,cols-1); y = random.randint(0,rows-1)
        ch = random.choice(chars); c = random.randint(31,37)
        sys.stdout.write(f"\033[{y};{x}H\033[{c}m{ch}\033[0m")

def event_marquee(e):
    global scroll_pos, phrase
    if scroll_pos == 0: phrase = random.choice(WORDS)
    scroll_pos = (scroll_pos + int(e*5)+1) % (len(phrase)+cols)
    y = rows//2
    for i,ch in enumerate(phrase):
        x = i-scroll_pos+cols
        if 0<=x<cols: sys.stdout.write(f"\033[{y};{x}H{ch}")

def event_invert(e):
    for yy in range(rows):
        for xx in range(0,cols, max(1,int(1/e))):
            c = 40 if random.random()<e else 47
            sys.stdout.write(f"\033[{yy};{xx}H\033[{c}m \033[0m")

def event_sparks(e):
    for _ in range(int(e*100)):
        x = random.randint(0,cols-1); y = random.randint(0,rows-1)
        sys.stdout.write(f"\033[{y};{x}H* ")

def event_waveform(e):
    st = max(1,len(prev_fft)//cols)
    for i in range(0,len(prev_fft),st):
        v = prev_fft[i]; y = rows-int(v*rows)
        x = i//st
        sys.stdout.write(f"\033[{y};{x}H~")

def event_rainbow_noise(e):
    for _ in range(int(e*50)+5):
        x = random.randint(0,cols-1); y = random.randint(0,rows-1)
        c = random.randint(31,36)
        sys.stdout.write(f"\033[{y};{x}H\033[{c}m█\033[0m")

def event_mirror(e): clear_screen()

# === Explosions ===
def explosion_radial(e):
    chars=list("@#%&*[]{}<>()")
    cx,cy=cols//2,rows//2
    for r in range(1,min(cols,rows)//2,2):
        for t in np.linspace(0,2*np.pi,r*4):
            x=int(cx+r*np.cos(t)); y=int(cy+r*np.sin(t))
            if 0<=x<cols and 0<=y<rows:
                ch=random.choice(chars); c=random.randint(31,37)
                sys.stdout.write(f"\033[{y};{x}H\033[{c}m{ch}\033[0m")
    sys.stdout.flush()

def explosion_asterisk(e):
    for _ in range(int(e*200)+20):
        x=random.randint(0,cols-1); y=random.randint(0,rows-1)
        sys.stdout.write(f"\033[{y};{x}H\033[1;33m*\033[0m")
    sys.stdout.flush()

def explosion_shockwave(e):
    for yy in range(0,rows, max(1,int(rows*(1-e)))):
        for xx in range(cols):
            sys.stdout.write(f"\033[{yy};{xx}H-\033[1;31m-\033[0m")
    sys.stdout.flush()

# === Mapping ===
EVENTS = {'1': event_word_rain,'2': event_block_bars,'3': event_static_glitch,
          '4': event_marquee,'5': event_invert,'6': event_sparks,
          '7': event_waveform,'8': event_rainbow_noise,'9': event_mirror}
EXPLOSIONS = {'/':explosion_radial,'*':explosion_asterisk,'-':explosion_shockwave}

# === Main Loop ===
active_events=set(); current_event=None
scroll_pos=0; phrase=''; explosion_key=None
clear_screen()
try:
    while True:
        # key input
        try: ch=sys.stdin.read(1)
        except: ch=None
        if ch in EVENTS:
            # toggle event
            if ch in active_events: active_events.remove(ch)
            else: active_events.add(ch)
            clear_screen()
        elif ch in EXPLOSIONS:
            explosion_key=ch
        elif ch=='0':
            draw_info(); active_events.clear(); continue

        # audio FFT
        data=stream.read(CHUNK,exception_on_overflow=False)
        samples=np.frombuffer(data,dtype=np.int16)[::2]
        if np.max(np.abs(samples))<80:
            fft=np.zeros_like(prev_fft)
        else:
            raw=np.abs(np.fft.fft(samples))[:CHUNK//2]
            fft=np.interp(np.linspace(0,len(raw),len(prev_fft)),np.arange(len(raw)),raw)
            fft/=(np.percentile(fft,98)+1e-6)
            fft=np.clip(np.sqrt(fft),0,1)
            fft=median_filter(fft,size=1)
        prev_fft[:]=0.3*prev_fft+0.7*fft
        energy=float(np.mean(prev_fft))

        # draw events
        clear_screen()
        for ev in active_events: EVENTS[ev](energy)
        if explosion_key:
            EXPLOSIONS[explosion_key](energy)
            explosion_key=None

        sys.stdout.flush(); time.sleep(1/30)

except KeyboardInterrupt: pass
finally:
    restore_terminal(); stream.stop_stream(); stream.close(); p.terminate()
    print("\033[0m\n[voidcore_events] Exited.")
