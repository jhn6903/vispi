import random
from common.base_vis import BaseVisualizer
from common.config import (
    HIGH_ENERGY_THRESHOLD,
    EXPLOSION_THRESHOLD, PAT_THRESHOLD
)
import numpy as np
RESET = "\033[0m"

COLORS = [
    "\033[91m", "\033[92m", "\033[93m",
    "\033[94m", "\033[95m", "\033[96m"
]

# === ASCII DECAY CHARACTERS ===
DECAY_CHARS = list(".*:,'`> &")

WAVE_CHARS = ['▁', '▂', '▃', '▄', '▅', '▆', '█']

# === EXPLOSIONS ===
EXPLOSIONS = [
    [r"   .   ", r"  . .  ", r"   .   "],
    [r" \ o / ", r"-  O  -", r" / o \ "],
    [r"  ***  ", r" ***** ", r"  ***  "]
]

# === PROJECT PAT SPRITE ===
PAT_SPRITE = [
    r"   _____   ",
    r"  /     \  ",
    r" | () () | ",
    r"  \  ^  /  ",
    r"   |||||   ",
    r"   |||||   ",
]


class BilboVisualizer(BaseVisualizer):
    def setup(self):
        # Load lyrics
        with open("out_there.txt", "r") as f:
            self.all_lines = [line.strip() for line in f if line.strip()]
        
        self.line_index = random.randrange(len(self.all_lines))
        
        # Lyric state
        self.lyric_state = {
            "text": "",
            "color": "",
            "x": 0,
            "y": self.rows // 2,
            "timer": 0,
            "fade_frames": [],
        }
        
        # Pat state
        self.pat_timer = 0
        self.pat_pos = (0, 0)
        
        # Explosion state
        self.explosion_active = False
        self.explosion_frame = 0
        self.explosion_delay = 0
        self.explosion_pos = (0, 0)
        self.explosion_color = random.choice(COLORS)
        self.explosion_cooldown = 0
    
    def get_snare_val(self, fft, bin_index=20):
        return fft[bin_index]
    
    def get_hat_val(self, fft, bin_index=-1):
        return fft[bin_index]
    
    def draw(self, samples, fft, low_energy, high_energy, total_energy):
        if self.is_silent:
            self.lyric_state["timer"] = 0
            self.lyric_state["fade_frames"].clear()
            self.pat_timer = 0
            self.explosion_active = False
            self.explosion_cooldown = 0
            return
        
        # === CHAOS CHARACTERS ===
        if high_energy > HIGH_ENERGY_THRESHOLD:
            density = int(high_energy * 120)
            for _ in range(density):
                y = random.randint(1, self.rows - 2)
                if abs(y - self.lyric_state["y"]) < 2:  # avoid printing *on* the lyric
                    continue
                x = random.randint(0, self.cols - 1)
                char = random.choice("~!@#$%^&*()_+=-▌▐▒░█▓▄▀▁▂▃▅▆")
                color = random.choice(COLORS)
                print(f"\033[{y};{x}H{color}{char}{RESET}")
        
        # === EXPLOSIONS ===
        if not self.explosion_active and self.explosion_cooldown <= 0:
            if low_energy > EXPLOSION_THRESHOLD and total_energy > EXPLOSION_THRESHOLD and random.random() < 0.2:
                self.explosion_active = True
                self.explosion_frame = 0
                self.explosion_delay = 3
                self.explosion_color = random.choice(COLORS)
                self.explosion_pos = (
                    random.randint(5, max(5, self.cols - 10)),
                    random.randint(2, max(2, self.rows - 5))
                )
                self.explosion_cooldown = 10
        
        if self.explosion_active:
            if self.explosion_frame < len(EXPLOSIONS):
                frame = EXPLOSIONS[self.explosion_frame]
                x, y = self.explosion_pos
                for i, line in enumerate(frame):
                    if 0 <= y + i < self.rows:
                        print(f"\033[{y+i};{x}H{self.explosion_color}{line}{RESET}")
                self.explosion_delay -= 1
                if self.explosion_delay <= 0:
                    self.explosion_frame += 1
                    self.explosion_delay = 3
            else:
                self.explosion_active = False
        
        if self.explosion_cooldown > 0:
            self.explosion_cooldown -= 1
            
            # === BACKGROUND NOISE FLICKER ===
            if total_energy < 0.25:
                for _ in range(10):
                    x = random.randint(0, self.cols - 1)
                    y = random.randint(1, self.rows - 2)
                    flicker = random.choice([".", "`", "'", " "])
                    print(f"\033[{y};{x}H\033[90m{flicker}{RESET}")
        
        # === PROJECT PAT ===
        if self.pat_timer == 0 and total_energy > PAT_THRESHOLD and random.random() < 0.03:
            self.pat_pos = (random.randint(3, self.cols - 15), random.randint(3, self.rows - 8))
            self.pat_timer = 10
        
        if self.pat_timer > 0:
            px, py = self.pat_pos
            for i, line in enumerate(PAT_SPRITE):
                if 0 <= py + i < self.rows:
                    print(f"\033[{py+i};{px}H\033[95m{line}{RESET}")
            self.pat_timer -= 1
        
        # === LYRICS ===
        if self.lyric_state["timer"] == 0 and total_energy > 0.25:
            line = self.all_lines[self.line_index % len(self.all_lines)]
            self.line_index += 1
            base_x = max(0, (self.cols - len(line)) // 2)
            x = base_x + random.choice([-1, 0, 1])
            x = max(0, min(self.cols - len(line), x))
            
            self.lyric_state.update({
                "text": line,
                "color": random.choice(COLORS),
                "x": x,
                "y": self.rows // 2,
                "timer": int(15 + total_energy * 50),
                "fade_frames": []
            })
        
        if self.lyric_state["timer"] > 0:
            print(f"\033[{self.lyric_state['y']};{self.lyric_state['x']}H{self.lyric_state['color']}{self.lyric_state['text']}{RESET}")
            self.lyric_state["timer"] -= 1
            
            if self.lyric_state["timer"] == 0:
                # Begin fade-out
                self.lyric_state["fade_frames"] = list(self.lyric_state["text"])
        
        elif self.lyric_state["fade_frames"]:
            for i in range(len(self.lyric_state["fade_frames"])):
                if self.lyric_state["fade_frames"][i] != " ":
                    self.lyric_state["fade_frames"][i] = random.choice(DECAY_CHARS)
            fade_line = ''.join(self.lyric_state["fade_frames"])
            print(f"\033[{self.lyric_state['y']};{self.lyric_state['x']}H{self.lyric_state['color']}{fade_line}{RESET}")
            if all(c == " " for c in fade_line):
                self.lyric_state["fade_frames"].clear()
        
        # === HUD BAR CHART UNDER LYRICS ===
        hud_bands = 8
        band_vals = np.mean(fft.reshape(hud_bands, -1), axis=1)
        hud_chars = [' ', '▁', '▂', '▃', '▄', '▅', '▆', '█']
        hud_height = len(hud_chars) - 1
        
        hud_y = self.lyric_state["y"] + 3
        hud_x = max((self.cols - hud_bands) // 2, 0)
        
        for i, val in enumerate(band_vals):
            level = min(int(val * hud_height * 1.5), hud_height)
            char = hud_chars[level]
            print(f"\033[{hud_y};{hud_x + i}H\033[96m{char}{RESET}")
        
        # === ENERGY NUMBER CENTERED TOO ===
        energy_value = int(np.mean(fft[:8]) * 100)
        energy_label = f"Kick: {energy_value:3d}%"
        kick_x = max((self.cols - len(energy_label)) // 2, 0)
        kick_y = hud_y + 1
        print(f"\033[{kick_y};{kick_x}H\033[94m{energy_label}{RESET}")
        
        # Hat line
        hat_val = self.get_hat_val(fft)
        hat_val_pct = int(hat_val * 100)
        hat_label = f"Hat:  {hat_val_pct:3d}%"
        print(f"\033[{hud_y+2};{kick_x}H\033[93m{hat_label}{RESET}")
        
        # Snare line
        snare_val = self.get_snare_val(fft)
        snare_val_pct = int(snare_val * 100)
        snare_label = f"Snare:{snare_val_pct:3d}%"
        print(f"\033[{hud_y+3};{kick_x}H\033[95m{snare_label}{RESET}")
        
        # === ASCII WAVEFORM ===
        wave_y = self.rows - 2
        wave = samples[::len(samples)//self.cols][:self.cols]
        norm_wave = np.interp(wave, (-30000, 30000), (0, 7)).astype(int)
        norm_wave = np.clip(norm_wave, 0, len(WAVE_CHARS) - 1)  # Ensure indices are in bounds
        for x, idx in enumerate(norm_wave):
            char = WAVE_CHARS[idx]
            print(f"\033[{wave_y};{x}H\033[92m{char}{RESET}")

if __name__ == "__main__":
    visualizer = BilboVisualizer()
    visualizer.run() 