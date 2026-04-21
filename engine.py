import os
import sys
import time
import threading
from utils import ansilookup, clear_screen, debug_log

from styles import Style, DEFAULT_STYLE

class RenderEngine:
    QUAD_CHAR_MAP = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"
    QUAD_TO_BITS = {c: i for i, c in enumerate(QUAD_CHAR_MAP)}

    def __init__(self):
        self.lock = threading.Lock()
        self.is_running = True
        self.cli_width = 80
        self.cli_height = 24
        
        # Primary Buffers
        self.screen_prepare = [] # Store (char, style_obj)
        self.screen_buffer = []
        self.screen_dump = []
        self.screen_diff = []
        
        # Compositing Spaces
        self.image_space = []
        self.binmap_space = []
        self.dirty_cells = set()
        
        # Input State
        self.last_key = None
        self.input_events = []
        
        self.last_cursor_pos = (-1, -1)
        self.size_dump = (0, 0)
        
        self.listen_size()

    def listen_size(self):
        try:
            size = os.get_terminal_size()
        except OSError:
            return

        if size != self.size_dump:
            with self.lock:
                self.cli_width = size.columns
                self.cli_height = size.lines
                
                # Reallocate all buffers
                self.screen_prepare = [[(" ", DEFAULT_STYLE) for _ in range(self.cli_width)] for _ in range(self.cli_height)]
                self.screen_buffer = [[(" ", DEFAULT_STYLE) for _ in range(self.cli_width)] for _ in range(self.cli_height)]
                self.screen_dump = [[("A", DEFAULT_STYLE) for _ in range(self.cli_width)] for _ in range(self.cli_height)]
                
                self.image_space = [[None for _ in range(self.cli_width)] for _ in range(self.cli_height)]
                self.binmap_space = [[None for _ in range(self.cli_width)] for _ in range(self.cli_height)]
                self.dirty_cells.clear()
                self.screen_diff = []
                
                clear_screen()
            self.size_dump = size

    def clear_prepare(self):
        for y in range(self.cli_height):
            for x in range(self.cli_width):
                self.screen_prepare[y][x] = (" ", DEFAULT_STYLE)

    def clear_spaces(self):
        for y, x in self.dirty_cells:
            if y < len(self.image_space) and x < len(self.image_space[0]):
                self.image_space[y][x] = None
                self.binmap_space[y][x] = None
        self.dirty_cells.clear()

    def push(self, y, x, content, style=None):
        if style is None: style = DEFAULT_STYLE
        if not self.screen_prepare: return
        if y < 0 or y >= len(self.screen_prepare): return
        
        limit_x = len(self.screen_prepare[0])
        curr_x = x
        for char in content:
            if curr_x < 0 or curr_x >= limit_x: break
            # 宽字符处理
            width = 2 if ord(char) > 128 and not (0x2500 <= ord(char) <= 0x259F) else 1
            self.screen_prepare[y][curr_x] = (char, style)
            if width == 2:
                if curr_x + 1 < limit_x:
                    self.screen_prepare[y][curr_x + 1] = ("", style)
                curr_x += 2
            else:
                curr_x += 1

    def push_image(self, y, x, char, fg, bg):
        if not self.image_space: return
        if y < 0 or y >= len(self.image_space) or x < 0 or x >= len(self.image_space[0]):
            return
        # ... (后续逻辑保持，已包含安全检查)
        if self.image_space[y][x] is None:
            self.image_space[y][x] = [None, None]
        if char == "▀":
            self.image_space[y][x][0] = fg
            if bg is not None: self.image_space[y][x][1] = bg
        elif char == "▄":
            self.image_space[y][x][1] = fg
        elif char == "█":
            self.image_space[y][x] = [fg, bg]
        self.dirty_cells.add((y, x))

    def push_binmap(self, y, x, char, fg):
        if not self.binmap_space: return
        if y < 0 or y >= len(self.binmap_space) or x < 0 or x >= len(self.binmap_space[0]):
            return
        # ... (保持检查)
        bits = self.QUAD_TO_BITS.get(char, 0)
        if bits == 0: return
        if self.binmap_space[y][x] is None:
            self.binmap_space[y][x] = [0, fg]
        self.binmap_space[y][x][0] |= bits
        if fg is not None: self.binmap_space[y][x][1] = fg
        self.dirty_cells.add((y, x))

    def flush_spaces(self):
        if not self.screen_prepare or not self.image_space: return
        limit_y, limit_x = len(self.screen_prepare), len(self.screen_prepare[0])
        # Pass 1: Binmap
        for y, x in self.dirty_cells:
            if y >= limit_y or x >= limit_x: continue
            bm = self.binmap_space[y][x]
            if bm and bm[0] > 0:
                self.push(y, x, self.QUAD_CHAR_MAP[bm[0]], Style(fg=bm[1]))
        # Pass 2: Image
        for y, x in self.dirty_cells:
            if y >= limit_y or x >= limit_x: continue
            img = self.image_space[y][x]
            if img and (img[0] is not None or img[1] is not None):
                if img[0] is not None and img[1] is not None:
                    self.push(y, x, "▀", Style(fg=img[0], bg=img[1]))
                elif img[0] is not None:
                    self.push(y, x, "▀", Style(fg=img[0]))
                else:
                    self.push(y, x, "▄", Style(fg=img[1]))

    def swap_buffers(self):
        with self.lock:
            for y in range(self.cli_height):
                self.screen_buffer[y] = self.screen_prepare[y][:]

    def find_diff(self):
        self.screen_diff.clear()
        for y in range(len(self.screen_buffer)):
            for x in range(len(self.screen_buffer[y])):
                if self.screen_buffer[y][x] != self.screen_dump[y][x]:
                    char, style = self.screen_buffer[y][x]
                    self.screen_diff.append((y, x, char, style))

    def render(self):
        self.find_diff()
        for y, x, char, style in self.screen_diff:
            if y != self.last_cursor_pos[0] or x != self.last_cursor_pos[1] + 1:
                sys.stdout.write(f"\033[{y + 1};{x + 1}H")
            sys.stdout.write(f"{ansilookup(style)}{char}")
            self.last_cursor_pos = (y, x)
        sys.stdout.flush()
        self.screen_dump = [row[:] for row in self.screen_buffer]
