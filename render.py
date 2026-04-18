import os
import sys
import time
import threading
from PIL import Image, ImageFont, ImageDraw

#region init

is_running = True
render_lock = threading.Lock() # New lock for buffer synchronization

# Compositing Spaces
image_space = [] 
binmap_space = []
dirty_cells = set()

size_dump = (0,0)
cli_width = 80
cli_height = 24
screen_prepare = []
screen_buffer = []
screen_dump = []
screen_diff = []

def listen_size():

    global size_dump, cli_width, cli_height, screen_buffer, screen_dump, screen_diff, screen_prepare
    global image_space, binmap_space, dirty_cells
    
    try:
        size = os.get_terminal_size()
    except OSError:
        return

    if size != size_dump:
        
        cli_width = size.columns
        cli_height = size.lines

        with render_lock:
            # per char slot in prepare/buffer/dump: (char->str, fg->int, bg->int, style->int)
            screen_prepare = [[(" ", 0, 0, 0) for _ in range(cli_width)] for _ in range(cli_height)]
            screen_buffer = [[(" ", 0, 0, 0) for _ in range(cli_width)] for _ in range(cli_height)]
            screen_dump = [[("A", 0, 0, 0) for _ in range(cli_width)] for _ in range(cli_height)]

            # Initialize compositing spaces
            image_space = [[None for _ in range(cli_width)] for _ in range(cli_height)]
            binmap_space = [[None for _ in range(cli_width)] for _ in range(cli_height)]
            dirty_cells.clear()

            # per char slot in diff: (y, x, char, fg, bg, style)
            screen_diff = []

        clear_screen()

    size_dump = size

#endregion


#region core

def clear_spaces():
    global dirty_cells
    for y, x in dirty_cells:
        image_space[y][x] = None
        binmap_space[y][x] = None
    dirty_cells.clear()

def push_image(y, x, char, fg, bg, style):
    """Bridge for ImageRenderer: Merges top/bottom colors."""
    # Ensure spaces are initialized and large enough
    if not image_space: return
    
    # Robust boundary check
    if y < 0 or y >= len(image_space) or x < 0 or x >= len(image_space[0]):
        return
    
    # Initialize cell if empty
    if image_space[y][x] is None:
        image_space[y][x] = [None, None]
    
    # Merge logic
    if char == "▀":
        image_space[y][x][0] = fg
        if bg is not None: image_space[y][x][1] = bg
    elif char == "▄":
        image_space[y][x][1] = fg
    elif char == "█":
        image_space[y][x] = [fg, bg]
    
    dirty_cells.add((y, x))

def push_binmap(y, x, char, fg, bg, style):
    """Bridge for BinmapRenderer: Bitwise OR merging of quadrant sub-pixels."""
    if not binmap_space: return
    
    if y < 0 or y >= len(binmap_space) or x < 0 or x >= len(binmap_space[0]):
        return
    
    bits = QUAD_TO_BITS.get(char, 0)
    if bits == 0: return

    # Initialize cell if empty
    if binmap_space[y][x] is None:
        binmap_space[y][x] = [0, fg]
    
    # Merge
    binmap_space[y][x][0] |= bits
    if fg is not None: binmap_space[y][x][1] = fg
    
    dirty_cells.add((y, x))

# Map quadrant characters back to bits for merging
QUAD_CHAR_MAP = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"
QUAD_TO_BITS = {c: i for i, c in enumerate(QUAD_CHAR_MAP)}

def flush_spaces():
    """Composite spaces into screen_prepare using two-pass natural coverage."""
    # Ensure buffers exist and match
    if not screen_prepare or not image_space or not binmap_space: return
    
    # Use current buffer dimensions as the source of truth
    limit_y = len(screen_prepare)
    limit_x = len(screen_prepare[0])

    # Pass 1: Binmap Space (Lower Priority)
    for y, x in dirty_cells:
        if y >= limit_y or x >= limit_x: continue
        
        bm_data = binmap_space[y][x]
        if bm_data is not None:
            bits, fg_color = bm_data
            if bits > 0:
                char = QUAD_CHAR_MAP[bits]
                push(y, x, char, fg_color, None, 0)
    
    # Pass 2: Image Space (Higher Priority - Overwrites Binmap)
    for y, x in dirty_cells:
        if y >= limit_y or x >= limit_x: continue
        
        img_data = image_space[y][x]
        if img_data is not None:
            top, bottom = img_data
            if top is not None or bottom is not None:
                # Based on presence of top/bottom colors, determine the best block character
                if top is not None and bottom is not None:
                    push(y, x, "▀", top, bottom, 0)
                elif top is not None:
                    push(y, x, "▀", top, None, 0)
                else:
                    push(y, x, "▄", bottom, None, 0)

def push(y, x, content, fg, bg, style):
    """Simplified push with boundary safety."""
    if not screen_prepare or y < 0 or y >= len(screen_prepare): return
    
    curr_x = x
    for char in content:
        if curr_x < 0 or curr_x >= len(screen_prepare[0]): break
        
        # Detect character width (Block elements are width 1)
        width = 2 if ord(char) > 128 and not (0x2500 <= ord(char) <= 0x259F) else 1
        
        screen_prepare[y][curr_x] = (char, fg, bg, style)
        
        if width == 2:
            if curr_x + 1 < len(screen_prepare[0]):
                screen_prepare[y][curr_x + 1] = ("", fg, bg, style)
            curr_x += 2
        else:
            curr_x += 1
    return 0

def find_diff():
    screen_diff.clear()
    for y in range(len(screen_buffer)):
        for x in range(len(screen_buffer[y])):
            new_cell = screen_buffer[y][x]
            if new_cell != screen_dump[y][x]:
                screen_diff.append((
                    y,
                    x,
                    new_cell[0], # char
                    new_cell[1], # fg
                    new_cell[2], # bg
                    new_cell[3]  # style
                ))

last_job = (-1, -1)
def putchar(task):
    global last_job
    y, x, char, fg, bg, style = task
    
    if y != last_job[0] or x != last_job[1] + 1:
        sys.stdout.write(f"\033[{y + 1};{x + 1}H")  

    style_cmd = ansilookup(fg, bg, style)

    sys.stdout.write(f"{style_cmd}{char}")    

    last_job = (y, x)
                
#endregion

#region image


'''
Load an image and render it to the screen.

Args:
    path: The path to the image.
    target_width: The width of the image in characters.

Returns:
    None

Features: 
    It uses the half-width char "▀", so height is 2x upscaled, while width is not.
'''



from PIL import Image, ImageFont, ImageDraw

# ... (rest of the imports and init region)

class FontManager:
    def __init__(self, font_path, size=16, vertical_compress=False):
        self.font_path = font_path
        self.size = size
        self.vertical_compress = vertical_compress
        self.atlas = {} 
        
        debug_log(f"[FontManager] Loading: {font_path} at size {size}, vertical_compress={vertical_compress}")
        try:
            self.font = ImageFont.truetype(font_path, size)
            # Get global font metrics
            self.ascent, self.descent = self.font.getmetrics()
            self.cell_height = self.ascent + self.descent
            debug_log(f"[FontManager] Metrics: Ascent={self.ascent}, Descent={self.descent}, Total Height={self.cell_height}")
            self._generate_atlas()
        except Exception as e:
            debug_log(f"[FontManager] Error loading font: {e}")
            self.font = None

    def _generate_atlas(self):
        debug_log(f"[FontManager] Starting alignment-corrected atlas generation.")
        valid_count = 0
        for i in range(32, 127):
            char = chr(i)
            try:
                # getmask2 returns (mask, offset_tuple)
                mask, offset = self.font.getmask2(char, mode='L')
                mask_w, mask_h = mask.size
                
                advance_width = self.font.getlength(char)
                if advance_width <= 0: advance_width = self.size // 2
                
                canvas_w = int(advance_width)
                canvas_h = self.cell_height
                
                full_cell_img = Image.new('L', (canvas_w, canvas_h), 0)
                
                # If mask is not empty, paste it using an explicit 4-item box
                # to avoid the 'cannot determine region size' error.
                if mask_w > 0 and mask_h > 0:
                    # offset is relative to the pen position. 
                    # We ensure we stay within canvas bounds
                    dest_x = offset[0]
                    dest_y = offset[1]
                    
                    # Fix: Provide the full (left, top, right, bottom) box
                    box = (dest_x, dest_y, dest_x + mask_w, dest_y + mask_h)
                    full_cell_img.paste(mask, box)
                
                # Convert to binary matrix
                pixels = full_cell_img.load()
                raw_matrix = []
                for y in range(canvas_h):
                    row = [1 if pixels[x, y] > 127 else 0 for x in range(canvas_w)]
                    raw_matrix.append(row)
                
                if self.vertical_compress:
                    self.atlas[char] = [raw_matrix[y] for y in range(0, canvas_h, 2)]
                    final_h = len(self.atlas[char])
                else:
                    self.atlas[char] = raw_matrix
                    final_h = canvas_h
                
                valid_count += 1
                
                if char == 'S':
                    debug_log(f"[FontManager] --- Visual Matrix for 'S' ({canvas_w}x{final_h}) ---")
                    for rd in self.atlas[char]:
                        debug_log("".join(["#" if v else "." for v in rd]))
                    debug_log("[FontManager] ---------------------------------------")

            except Exception as e:
                debug_log(f"[FontManager] Error processing char '{char}': {e}")
                self.atlas[char] = [[0] * 8 for _ in range(8)]

        debug_log(f"[FontManager] Atlas complete. {valid_count} chars aligned and loaded.")

    def get_char(self, char):
        return self.atlas.get(char, [[0]])

class BigTextRenderer:
    def __init__(self, font_manager):
        self.fm = font_manager

    def render_string(self, text, start_y, start_x, fg=(255, 255, 255), bg=None, push_func=None):
        if not text: return
        
        # Filter and get valid matrices
        char_matrices = []
        for c in text:
            m = self.fm.get_char(c)
            # Ensure matrix is not just a placeholder
            if len(m) > 0 and len(m[0]) > 0:
                char_matrices.append(m)
        
        if not char_matrices: return

        # 1. Determine bounding box
        max_h = max(len(m) for m in char_matrices)
        total_w = sum(len(m[0]) for m in char_matrices)
        
        full_matrix = [[0 for _ in range(total_w)] for _ in range(max_h)]
        
        curr_x = 0
        for matrix in char_matrices:
            h = len(matrix)
            w = len(matrix[0])
            for y in range(h):
                for x in range(w):
                    full_matrix[y][curr_x + x] = matrix[y][x]
            curr_x += w
        
        # 2. Draw using the provided bridge function
        br = BinmapRenderer(full_matrix, fg=fg, bg=bg)
        br.draw(start_y, start_x, push_func)

class BinmapImageRenderer:
    def __init__(self, path, target_width, fg=(255, 255, 255), vertical_compress=True):
        """
        path: Path to the image.
        target_width: Desired width in terminal CHARACTERS.
        fg: The monochrome color to use for non-zero pixels.
        vertical_compress: If True, compresses source height by 2x to fix terminal distortion.
        """
        self.path = path
        self.fg = fg
        
        # Load and convert to RGBA to check alpha
        img = Image.open(path).convert('RGBA')
        orig_w, orig_h = img.size
        aspect = orig_h / orig_w
        
        # In Binmap mode, 1 terminal char = 2 pixels wide
        pixel_width = target_width * 2
        pixel_height = int(pixel_width * aspect)
        
        # Initial resize to the high-res binary target
        img = img.resize((pixel_width, pixel_height), Image.Resampling.NEAREST)
        
        if vertical_compress:
            # Squash height to compensate for 2:1 terminal aspect ratio
            pixel_height = max(1, pixel_height // 2)
            img = img.resize((pixel_width, pixel_height), Image.Resampling.NEAREST)
            
        # Convert to binary matrix based on user criteria
        self.matrix = []
        pixels = img.load()
        for y in range(pixel_height):
            row = []
            for x in range(pixel_width):
                r, g, b, a = pixels[x, y]
                # Criteria: Not transparent AND not pure black
                if a > 0 and (r > 0 or g > 0 or b > 0):
                    row.append(1)
                else:
                    row.append(0)
            self.matrix.append(row)
            
        # Initialize internal renderer
        self.renderer = BinmapRenderer(self.matrix, fg=self.fg, skip_empty=True)

    def draw(self, start_y, start_x, push_func):
        self.renderer.draw(start_y, start_x, push_func)

class ImageRenderer:

    def __init__(self, path: str, target_width: int, enable_256_color_reduction: bool = False):
        self.path = path
        self.width = target_width
        self.pixels = None
        self.processed_colors = [] # Cache for processed color data
        self.height = 0
        self.enable_256_color_reduction = enable_256_color_reduction
        self._palette_map = None # Stores mapping from Pillow's palette index to standard ANSI 256 index
        
        self._load_and_resize()
        self._preprocess_colors() # Pre-calculate all colors once

    # Helper to generate the standard 256-color palette for mapping.
    # This is a common approximation. A more precise mapping might involve
    # knowing the exact RGB values for the first 16 colors in a given terminal.
    # For general compatibility, this set is widely used.
    @staticmethod
    def _generate_ansi256_palette_rgb():
        palette = []
        # Basic 16 colors (0-15) - common approximations.
        # These are often terminal-dependent, but these are widely accepted defaults.
        basic_16 = [
            (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
            (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
            (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
            (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)
        ]
        palette.extend(basic_16)

        # 6x6x6 color cube (16-231)
        levels = [0, 95, 135, 175, 215, 255]
        for r_idx in range(6):
            for g_idx in range(6):
                for b_idx in range(6):
                    palette.append((levels[r_idx], levels[g_idx], levels[b_idx]))

        # Grayscale ramp (232-255)
        for i in range(24):
            gray = 8 + i * 10 # Grayscale values from 8 to 238
            palette.append((gray, gray, gray))
        return palette

    # Cache the generated palette to avoid recomputing it for every instance
    _ansi256_palette_rgb_cache = _generate_ansi256_palette_rgb()

    def _rgb_to_ansi256(self, rgb_tuple: tuple) -> int:
        r, g, b = rgb_tuple[:3]
        min_dist = float('inf')
        closest_idx = 0

        for i, (pr, pg, pb) in enumerate(self._ansi256_palette_rgb_cache):
            dist = (r - pr)**2 + (g - pg)**2 + (b - pb)**2 # Euclidean distance
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
        return closest_idx

    def _preprocess_colors(self):
        """Pre-calculates colors for all pixels to avoid per-frame overhead."""
        self.processed_colors = [[None for _ in range(self.width)] for _ in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                pixel = self.pixels[x, y]
                if self.enable_256_color_reduction:
                    self.processed_colors[y][x] = self._rgb_to_ansi256(pixel)
                else:
                    self.processed_colors[y][x] = pixel

    def _load_and_resize(self):
        global cli_width, cli_height # Access global terminal dimensions

        img = Image.open(self.path).convert('RGBA')
        aspect = img.height / img.width

        original_img_width = img.width
        original_img_height = img.height

        max_allowed_width = min(original_img_width, cli_width, self.width)
        max_allowed_height = min(original_img_height, cli_height * 2)

        calculated_width = max_allowed_width
        calculated_height = int(calculated_width * aspect)

        # If this calculated height exceeds the max_allowed_height,
        # then we must scale down based on height instead.
        if calculated_height > max_allowed_height:
            calculated_height = max_allowed_height
            calculated_width = int(calculated_height / aspect)
        

        self.width = max(1, calculated_width)
        self.height = max(1, calculated_height)


        if self.height % 2 != 0:
            self.height = max(2, self.height - 1) 

        img = img.resize((self.width, self.height), Image.Resampling.NEAREST)
        self.pixels = img.load()


    def draw(self, start_y, start_x, push_func):
        threshold = 128
        for y in range(0, self.height, 2):
            for x in range(self.width):
                top_raw = self.pixels[x, y]
                bottom_raw = self.pixels[x, y+1]
                
                # Use pre-calculated colors from cache
                top_color = self.processed_colors[y][x]
                bottom_color = self.processed_colors[y+1][x]
                
                # Alpha still needs to be checked from original pixels for transparency logic
                t_alpha = top_raw[3] if len(top_raw) > 3 else 255
                b_alpha = bottom_raw[3] if len(bottom_raw) > 3 else 255

                if t_alpha < threshold and b_alpha < threshold:
                    # Both transparent, skip this cell
                    continue
                elif t_alpha < threshold:
                    # Top transparent, draw bottom only using ▄ (lower half block)
                    push_func(start_y + (y // 2), start_x + x, "▄", bottom_color, None, 0)
                elif b_alpha < threshold:
                    # Bottom transparent, draw top only using ▀ (upper half block)
                    push_func(start_y + (y // 2), start_x + x, "▀", top_color, None, 0)
                else:
                    # Both opaque, draw normally
                    push_func(start_y + (y // 2), start_x + x, "▀", top_color, bottom_color, 0)

class BinmapRenderer:
    def __init__(self, binmap, fg=(255, 255, 255), bg=None, skip_empty=True):
        """
        binmap: A 2D list of 0/1 or booleans.
        fg: Foreground color (RGB tuple or ANSI index).
        bg: Background color.
        skip_empty: If True, do not draw cells that are entirely background.
        """
        self.binmap = binmap
        self.height = len(binmap)
        self.width = len(binmap[0]) if self.height > 0 else 0
        self.fg = fg
        self.bg = bg
        self.skip_empty = skip_empty
        # Quadrant characters map (binary 2x2): TL=1, TR=2, BL=4, BR=8
        # Index calculation: 1*TL + 2*TR + 4*BL + 8*BR
        self.char_map = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"

    def draw(self, start_y, start_x, push_func):
        # Step through original matrix in 2x2 blocks
        for y in range(0, self.height, 2):
            for x in range(0, self.width, 2):
                # Safely get 2x2 block pixels
                tl = self.binmap[y][x] if y < self.height and x < self.width else 0
                tr = self.binmap[y][x+1] if (y < self.height) and (x+1 < self.width) else 0
                bl = self.binmap[y+1][x] if (y+1 < self.height) and (x < self.width) else 0
                br = self.binmap[y+1][x+1] if (y+1 < self.height) and (x+1 < self.width) else 0

                # Map 2x2 to 4-bit index
                index = (1 if tl else 0) + (2 if tr else 0) + (4 if bl else 0) + (8 if br else 0)

                if self.skip_empty and index == 0:
                    continue
                
                char = self.char_map[index]
                push_func(start_y + (y // 2), start_x + (x // 2), char, self.fg, self.bg, 0)






#endregion

#region render

def render():
    global screen_diff, screen_dump
    find_diff()
    for task in screen_diff:
        putchar(task)
    sys.stdout.flush()
    screen_dump = [row[:] for row in screen_buffer]
    screen_diff.clear()

def swap_buffers():
    global screen_buffer, screen_prepare
    with render_lock:
        for y in range(cli_height):
            screen_buffer[y] = screen_prepare[y][:]

#endregion

#region convenience

def convlen(content):
    length = 0
    for char in content:
        code = ord(char)
        if code < 128 or (0x2500 <= code <= 0x259F):
            length += 1
        elif 0x1100 <= code <= 0x11FF or 0x2E80 <= code <= 0x9FFF or 0xAC00 <= code <= 0xD7AF:
            length += 2
        else:
            length += 1
    return length

def ansilookup(fg, bg, style):
    parts = []

    # 1. 样式处理：只有当 style 不是 None 且不为 0 时才添加（0 往往是默认，可加可不加）
    if style is not None:
        parts.append(str(style))

    # 2. 前景色处理
    if fg is not None: # Only process if foreground color is provided
        if isinstance(fg, int):
            if fg < 8:
                parts.append(str(30 + fg))
            elif fg < 16:
                parts.append(str(90 + (fg - 8)))
            else:
                parts.append(f"38;5;{fg}")
        elif isinstance(fg, tuple):
            parts.append(f"38;2;{fg[0]};{fg[1]};{fg[2]}")

    # 3. 背景色处理
    if bg is not None: # Only process if background color is provided
        if isinstance(bg, int):
            if bg < 8:
                parts.append(str(40 + bg))
            elif bg < 16:
                parts.append(str(100 + (bg - 8)))
            else:
                parts.append(f"48;5;{bg}")
        elif isinstance(bg, tuple):
            parts.append(f"48;2;{bg[0]};{bg[1]};{bg[2]}")

    # 4. 关键：如果没有有效参数，返回空字符串；否则拼装
    if not parts:
        return ""
    
    res = "\033[" + ";".join(parts) + "m"
    return res

def clear_screen():
    # 建议合并发送：先清屏，再归位
    sys.stdout.write("\033[3J")
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def cleanup():
    # 1. 移到最后一行 2. 重置颜色 3. 换行 4. 显示光标
    sys.stdout.write(f"\033[{cli_height + 1};1H\033[0m\n\033[?25h")
    sys.stdout.flush()

def debug_log(msg):
    with open("debug.log", "a") as f:
        f.write(str(msg) + "\n")

#endregion

#region QoL

THEME = {
    "normal": (7, 0, 0),
    "test256": (46, 0, 0),
    "testrgb": ((255, 85, 85), 0, 0)
}


def text(y, x, content, type_name="normal"):
    # 从 THEME 拿到元组：(fg, bg, style)
    conf = THEME.get(type_name, THEME["normal"])
    push(y, x, content, conf[0], conf[1], conf[2])



#endregion




# Main Program


listen_size()
clear_screen()
frame_count = 0

def clear_prepare():
    global screen_prepare
    for y in range(cli_height):
        for x in range(cli_width):
            screen_prepare[y][x] = (" ", 0, 0, 0)

def logic_loop():
    global frame_count, is_running
    
    # Pre-initialize resources
    image = ImageRenderer("img/sanae_RGBA.png", 59, True)
    # Re-using your earlier BinmapImageRenderer mention
    logo = BinmapImageRenderer("img/Aliya.png", 20, fg=(100, 200, 250))
    
    # Using vertical_compress=True for best proportions
    fm = FontManager("ToshibaT300.ttf", 16, vertical_compress=True) 
    big_text = BigTextRenderer(fm)

    while is_running:
        # 1. 动态感知尺寸
        listen_size() 
        
        with render_lock:
            # 2. 清除缓冲区
            clear_prepare()
            clear_spaces() # Important: Reset compositing spaces every frame
            
            # 3. 逻辑产出 (Direct text still works)
            text(1, 1, f"Frame: {frame_count}", "test256")
            text(2, 1, "Hello, world", "test8")

            # 4. 绘制图像 -> 推入 Image Space
            image.draw(5, 5, push_image)
            
            # 5. 绘制 Logo -> 推入 Binmap Space
            logo.draw(5, 50, push_binmap)
            
            # 6. 绘制超大字符 -> 推入 Binmap Space
            # This demonstrates that multiple binmap calls can now merge!
            big_text.render_string("SOS", 15, 20, fg=(255, 50, 50), push_func=push_binmap)
            
            # 7. 执行后期合成 (Compositing)
            # This combines spaces and does a single set of push() calls
            flush_spaces()
        
        time.sleep(0.01)

def render_loop(fps):
    global frame_count, is_running
    interval = 1.0 / fps
    while is_running:
        start = time.perf_counter()
        
        # 3. 渲染物理驱动
        swap_buffers() # 同步 Prepare 到 Buffer
        render()       # 增量渲染
        
        frame_count += 1
        
        # 稳帧逻辑
        elapsed = time.perf_counter() - start
        time.sleep(max(0, interval - elapsed))




# --- 执行阶段 ---
try:
    # 启动两个线程
    t1 = threading.Thread(target=logic_loop, daemon=True)
    t2 = threading.Thread(target=render_loop, args=(16,), daemon=True)
    t1.start()
    t2.start()

    # 主线程阻塞，等待退出指令（比如 Ctrl+C）
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    is_running = False
finally:
    # 最后的扫尾
    cleanup()
    print("\n[Prosperous] 已安全退出")
