#!/usr/bin/env python3
"""
vis_config.py

Shared configuration and pause menu functionality for visualizers.
"""
import curses
import json
import os
from threading import Lock

CONFIG_FILE = os.path.expanduser('~/visualizers/vis_settings.json')

class VisualizerConfig:
    def __init__(self):
        self.lock = Lock()
        self.paused = False
        self.settings = {
            'intensity': 1.0,
            'sensitivity': 3.0,
            'smoothing': 0.3,
            'noise_gate': 100,
            'color_speed': 0.1
        }
        self.load_settings()
    
    def load_settings(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    saved = json.load(f)
                    self.settings.update(saved)
        except Exception as e:
            print(f"Error loading settings: {e}")
    
    def save_settings(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def draw_menu(self, stdscr):
        with self.lock:
            curses.curs_set(0)
            h, w = stdscr.getmaxyx()
            menu_w = 40
            menu_h = 10
            start_y = (h - menu_h) // 2
            start_x = (w - menu_w) // 2
            
            # Create menu window
            menu = curses.newwin(menu_h, menu_w, start_y, start_x)
            menu.box()
            menu.addstr(0, 2, "[ VISUALIZER SETTINGS ]")
            
            # Show current settings
            menu.addstr(2, 2, f"Intensity:   {self.settings['intensity']:.1f}")
            menu.addstr(3, 2, f"Sensitivity: {self.settings['sensitivity']:.1f}")
            menu.addstr(4, 2, f"Smoothing:   {self.settings['smoothing']:.1f}")
            menu.addstr(5, 2, f"Noise Gate:  {self.settings['noise_gate']}")
            menu.addstr(6, 2, f"Color Speed: {self.settings['color_speed']:.1f}")
            menu.addstr(8, 2, "ESC: Close  ←/→: Adjust  ↑/↓: Select")
            
            menu.refresh()
            return menu

    def handle_menu_input(self, key, selected_item=0):
        items = ['intensity', 'sensitivity', 'smoothing', 'noise_gate', 'color_speed']
        if selected_item >= len(items):
            return selected_item
            
        item = items[selected_item]
        
        if key in [curses.KEY_LEFT, ord('h')]:
            if item == 'noise_gate':
                self.settings[item] = max(0, self.settings[item] - 10)
            else:
                self.settings[item] = max(0.1, self.settings[item] - 0.1)
        elif key in [curses.KEY_RIGHT, ord('l')]:
            if item == 'noise_gate':
                self.settings[item] = min(1000, self.settings[item] + 10)
            else:
                self.settings[item] = min(10.0, self.settings[item] + 0.1)
        elif key in [curses.KEY_UP, ord('k')]:
            selected_item = (selected_item - 1) % len(items)
        elif key in [curses.KEY_DOWN, ord('j')]:
            selected_item = (selected_item + 1) % len(items)
        
        return selected_item

# Global config instance
config = VisualizerConfig() 