#!/usr/bin/env python3
"""
console_demo.py

A demo-scroller style visualizer using framebuffer and overlaying terminal glitches.
Features:
- 8x8 grid of boxes pulsing with 64 frequency bands
- Gate on low signals: quiet cells go dark
- Cells occasionally show random lyric words when loud
- Dynamic multi-hue coloring per cell via full HSV mapping
- Techy name generator at top
- Three scrolling text bands rendered in framebuffer (top1, top2, bottom)
- Three parallel scrolling text lines in the terminal behind the FB
- Behind-FB terminal glitch prints: random logs & ASCII art
- Countdown-break effect in a 2x2 mini-window
- Explosion/flurry effect on break
- Ultra-low latency single-buffer writes
"""
import os, sys, time, random, subprocess, shutil
import numpy as np
import pyaudio
from scipy.ndimage import median_filter
from PIL import Image, ImageDraw, ImageFont
import colorsys

# === Configuration ===
CHUNK, RATE = 1024, 44100
CHANNELS, FORMAT = 2, pyaudio.paInt16
INPUT_INDEX = 1
NUM_BARS = 64
SMOOTHING = 0.2
SENSITIVITY = 5.0
GATE_THRESHOLD = 0.1
FPS = 30
DELAY = 1.0 / FPS
MAX_INT16 = 32768.0
GRID_COLS, GRID_ROWS = 8, 8
WIDTH, HEIGHT = 480, 360
FB_PATH = '/dev/fb0'
SCROLL_SPEED = 2
NAME_INTERVAL = 4
CELL_WORD_THRESHOLD = 0.7

# Countdown-break and explosion
COUNTDOWN_START = 10
BREAK_DURATION = FPS
EXPLOSION_DURATION = FPS // 2

# Terminal geometry
TERM_GEO = shutil.get_terminal_size(fallback=(80, 24))
TERM_ROWS, TERM_COLS = TERM_GEO.lines, TERM_GEO.columns
SCROLL_Y_TOP1 = 2
SCROLL_Y_TOP2 = 4
SCROLL_Y_BOTTOM = TERM_ROWS - 2

# Load words
lyric_file = os.path.expanduser('~/visualizers/out_there.txt')
if not os.path.exists(lyric_file): lyric_file = 'out_there.txt'
WORDS = []
with open(lyric_file, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        for w in line.strip().split():
            if all(ord(c) < 128 for c in w): WORDS.append(w)
if not WORDS:
    WORDS = ['DEMO','AUDIO','GLITCH','VISUAL']
GLITCH_LOGS = ['[OK]','[ERR]','@INIT','>SYS','<ALERT>']

# Framebuffer geometry
try:
    out = subprocess.check_output('fbset -s', shell=True).decode()
    FB_W, FB_H = next((int(p.split()[1]), int(p.split()[2])) for p in out.splitlines() if 'geometry' in p)
except:
    FB_W, FB_H = WIDTH, HEIGHT
X_OFF = (FB_W - WIDTH) // 2
Y_OFF = (FB_H - HEIGHT) // 2

# Load bold font
try:
    FONT = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 20)
except:
    FONT = ImageFont.load_default()

# Audio engine
class AudioEngine:
    def __init__(self):
        pa = pyaudio.PyAudio()
        self.stream = pa.open(format=FORMAT, channels=CHANNELS,
                              rate=RATE, input=True,
                              input_device_index=INPUT_INDEX,
                              frames_per_buffer=CHUNK)
    def read(self):
        data = self.stream.read(CHUNK, exception_on_overflow=False)
        return np.frombuffer(data, np.int16)[::CHANNELS]

# Spectrum compute
def compute_spectrum(samples, prev):
    fft = np.abs(np.fft.rfft(samples))
    focus = fft[:len(fft)*2//3]
    bands = np.interp(np.linspace(0, len(focus), NUM_BARS), np.arange(len(focus)), focus)
    bands *= SENSITIVITY
    p95 = np.percentile(bands, 95) + 1e-6
    norm = np.clip(bands / p95, 0, 1)
    norm[norm < GATE_THRESHOLD] = 0
    smooth = median_filter(norm**0.5, 1)
    return SMOOTHING * prev + (1 - SMOOTHING) * smooth

# Framebuffer visualizer
class FramebufferVisualizer:
    def __init__(self):
        self.prev = np.zeros(NUM_BARS)
        # scrolling text bands
        self.text_fb_top1 = self._new_text(); self.x_fb_top1 = WIDTH
        self.text_fb_top2 = self._new_text(); self.x_fb_top2 = WIDTH
        self.text_fb_bot = self._new_text(); self.x_fb_bot = WIDTH
        # name
        self.name = self._rand_name(); self.last_name = time.time()
        # countdown-break
        self.countdown = False; self.count_start = 0
        self.break_timer = 0; self.explosion_timer = 0
        self.window = (0,0)

    def _rand_name(self): return random.choice(WORDS).upper() + '-' + random.choice(WORDS).upper()
    def _new_text(self): return ' '.join(random.choice(WORDS) for _ in range(5))

    def render(self, spec):
        if self.explosion_timer > 0:
            self._explosion(); self.explosion_timer -= 1; return
        if self.break_timer > 0:
            self._break(); self.break_timer -= 1
            if self.break_timer == 0: self.explosion_timer = EXPLOSION_DURATION
            return
        if not self.countdown and random.random() < 0.002:
            self.countdown = True; self.count_start = time.time()
            r,c = random.randint(0,GRID_ROWS-2), random.randint(0,GRID_COLS-2)
            self.window = (r,c)
        if self.countdown:
            rem = COUNTDOWN_START - int(time.time() - self.count_start)
            if rem >= 0:
                self._draw(spec); self._draw_countdown(rem)
            else:
                self.countdown = False; self.break_timer = BREAK_DURATION
            return
        self._draw(spec)

    def _draw(self, spec):
        img = Image.new('RGB',(WIDTH,HEIGHT),'black'); d = ImageDraw.Draw(img)
        # name
        if time.time() - self.last_name > NAME_INTERVAL:
            self.name = self._rand_name(); self.last_name = time.time()
        bb = d.textbbox((0,0),self.name,font=FONT); w = bb[2]-bb[0]
        d.text(((WIDTH-w)//2,4), self.name, fill=(0,255,0), font=FONT)
        # grid
        cw, ch = WIDTH/GRID_COLS, (HEIGHT-100)/GRID_ROWS
        for i,v in enumerate(spec):
            r, c = divmod(i, GRID_COLS)
            x0, y0 = c*cw, 60+r*ch; x1, y1 = x0+cw-2, y0+ch-2
            hue = (v + i/NUM_BARS) % 1.0
            color = tuple(int(cc*255) for cc in colorsys.hsv_to_rgb(hue,1.0,v))
            d.rectangle([x0,y0,x1,y1], fill=color)
            if v > CELL_WORD_THRESHOLD and random.random() < 0.3:
                wtext = random.choice(WORDS)
                tb = d.textbbox((0,0),wtext,font=FONT)
                fw, fh = tb[2]-tb[0], tb[3]-tb[1]
                d.text((x0+(cw-fw)/2, y0+(ch-fh)/2), wtext, fill='white', font=FONT)
        # framebuffer scrolls
        for text, x, y, col in [
            (self.text_fb_top1, self.x_fb_top1, 20, (200,200,100)),
            (self.text_fb_top2, self.x_fb_top2, 40, (100,200,200)),
            (self.text_fb_bot, self.x_fb_bot, HEIGHT-20, (180,180,180))]:
            d.text((x,y), text, fill=col, font=FONT)
        # update scroll positions
        for attr in ['top1','top2','bot']:
            tx = f'x_fb_{attr}'; txt = f'text_fb_{attr}'
            val = getattr(self, tx) - SCROLL_SPEED
            if val < -len(getattr(self, txt))*12:
                setattr(self, txt, self._new_text()); val = WIDTH
            setattr(self, tx, val)
        # write to fb
        buf = self._to565(img)
        with open(FB_PATH,'rb+') as fb:
            for row in range(HEIGHT): fb.seek(((Y_OFF+row)*FB_W+X_OFF)*2); fb.write(buf[row*WIDTH*2:(row+1)*WIDTH*2])

    def _draw_countdown(self, rem):
        r,c = self.window; cw, ch = WIDTH/GRID_COLS, (HEIGHT-100)/GRID_ROWS
        x, y = c*cw, 60+r*ch; num = str(rem)
        cell = Image.new('RGB',(int(cw*2), int(ch*2)),'black'); dc = ImageDraw.Draw(cell)
        bb = dc.textbbox((0,0), num, font=FONT); fw, fh = bb[2]-bb[0], bb[3]-bb[1]
        dc.text(((cw*2-fw)/2, (ch*2-fh)/2), num, fill=(255,0,0), font=FONT)
        buf = self._to565(cell)
        with open(FB_PATH,'rb+') as fb:
            for dy in range(int(ch*2)):
                off = ((Y_OFF+int(y)+dy)*FB_W+X_OFF+int(x))*2; fb.seek(off)
                fb.write(buf[dy*int(cw*2)*2:(dy+1)*int(cw*2)*2])

    def _break(self):
        img = Image.new('RGB',(WIDTH,HEIGHT),'white'); d = ImageDraw.Draw(img)
        for _ in range(200):
            wtext = random.choice(WORDS)
            bb = d.textbbox((0,0), wtext, font=FONT); wx, wy = bb[2]-bb[0], bb[3]-bb[1]
            x = random.randint(0, WIDTH-wx); y = random.randint(0, HEIGHT-wy)
            d.text((x,y), wtext, fill=(random.randint(0,255),)*3, font=FONT)
        buf = self._to565(img)
        with open(FB_PATH,'rb+') as fb:
            for r in range(HEIGHT): fb.seek(((Y_OFF+r)*FB_W+X_OFF)*2); fb.write(buf[r*WIDTH*2:(r+1)*WIDTH*2])

    def _explosion(self):
        img = Image.new('RGB',(WIDTH,HEIGHT),'black'); d = ImageDraw.Draw(img)
        ex = ['  *  ',' *** ','*****',' *** ','  *  ']
        cx, cy = WIDTH//2, HEIGHT//2
        for i,line in enumerate(ex): d.text((cx-20, cy-30+i*15), line, fill=(255,255,0), font=FONT)
        buf = self._to565(img)
        with open(FB_PATH,'rb+') as fb:
            for r in range(HEIGHT): fb.seek(((Y_OFF+r)*FB_W+X_OFF)*2); fb.write(buf[r*WIDTH*2:(r+1)*WIDTH*2])

    def _to565(self, img):
        arr = np.array(img); r = (arr[:,:,0]>>3).astype(np.uint16)
        g = (arr[:,:,1]>>2).astype(np.uint16); b = (arr[:,:,2]>>3).astype(np.uint16)
        fb = (r<<11)|(g<<5)|b; return fb.flatten().astype(np.uint16).tobytes()

# Terminal glitch prints
class TerminalGlitch:
    def render(self):
        for _ in range(8):
            y = random.randint(1, TERM_ROWS-2)
            msg = random.choice(GLITCH_LOGS)
            print(f"\033[{y};1H\033[{random.choice([31,32,33,35,36,91,92])}m{msg}\033[0m", end='')
        for _ in range(6):
            y = random.randint(1, TERM_ROWS-2)
            ch = random.choice(['*','@','#','%','$','&','?'])
            print(f"\033[{y};{TERM_COLS}H\033[{random.choice([93,95,96,94])}m{ch}\033[0m", end='')
        sys.stdout.flush()

# Terminal scroller (background)
class TerminalScroller:
    def __init__(self):
        self.reset_all()
    def reset_all(self):
        self.txt1 = self.txt2 = self.txt3 = ''
        self.x1 = self.x2 = self.x3 = TERM_COLS
        self.txt1 = ' '.join(random.choice(WORDS) for _ in range(8))
        self.txt2 = ' '.join(random.choice(WORDS) for _ in range(6))
        self.txt3 = ' '.join(random.choice(WORDS) for _ in range(10))
    def render(self):
        for txt,x,y,color in [
            (self.txt1, self.x1, SCROLL_Y_TOP1, 36),
            (self.txt2, self.x2, SCROLL_Y_TOP2, 35),
            (self.txt3, self.x3, SCROLL_Y_BOTTOM, 33)]:
            print(f"\033[{y};{int(x)}H\033[{color}m{txt}\033[0m", end='')
        self.x1 -= 1; self.x2 -= 2; self.x3 -= 1
        if self.x1 < -len(self.txt1): self.txt1 = ' '.join(random.choice(WORDS) for _ in range(8)); self.x1 = TERM_COLS
        if self.x2 < -len(self.txt2): self.txt2 = ' '.join(random.choice(WORDS) for _ in range(6)); self.x2 = TERM_COLS
        if self.x3 < -len(self.txt3): self.txt3 = ' '.join(random.choice(WORDS) for _ in range(10)); self.x3 = TERM_COLS
        sys.stdout.flush()

# Main
if __name__=='__main__':
    audio = AudioEngine(); viz = FramebufferVisualizer(); glitch = TerminalGlitch(); scroller = TerminalScroller()
    try:
        while True:
            samples = audio.read()
            spec = compute_spectrum(samples, viz.prev); viz.prev = spec
            viz.render(spec)
            glitch.render()
            scroller.render()
            time.sleep(DELAY)
    except KeyboardInterrupt:
        print('\nBye')
