import os
import sys
import time
import threading
from PIL import Image

#region init

is_running = True

size_dump = (0,0)
cli_width = 80
cli_height = 24
screen_prepare = []
screen_buffer = []
screen_dump = []
screen_diff = []

def listen_size():

    global size_dump, cli_width, cli_height, screen_buffer, screen_dump, screen_diff, screen_prepare
    
    try:
        size = os.get_terminal_size()
    except OSError:
        return

    if size != size_dump:
        
        cli_width = size.columns
        cli_height = size.lines

        # per char slot in prepare/buffer/dump: (char->str, fg->int, bg->int, style->int)
        screen_prepare = [[(" ", 0, 0, 0) for _ in range(cli_width)] for _ in range(cli_height)]
        screen_buffer = [[(" ", 0, 0, 0) for _ in range(cli_width)] for _ in range(cli_height)]
        screen_dump = [[("A", 0, 0, 0) for _ in range(cli_width)] for _ in range(cli_height)]

        # per char slot in diff: (y, x, char, fg, bg, style)
        screen_diff = []

        clear_screen()

    size_dump = size

#endregion


#region core

def push(y, x, content, fg, bg, style):

    pointer = y * cli_width + x
    for char in content:
        code = ord(char)
        if code < 128 or (0x2500 <= code <= 0x259F):
            width = 1
        elif 0x1100 <= code <= 0x11FF or 0x2E80 <= code <= 0x9FFF or 0xAC00 <= code <= 0xD7AF:
            width = 2
        else:
            width = 1

        y = pointer // cli_width
        x = pointer % cli_width

        if y >= cli_height or x >= cli_width:
            return
        
        if width == 2 and x == cli_width - 1:
            x = 0
            y += 1
        
        screen_prepare[y][x] = (char, fg, bg, style)
        
        if width == 2:
                screen_prepare[y][x + 1] = ("", fg, bg, style)

        pointer += width
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



class ImageRenderer:

    def __init__(self, path: str, target_width: int, enable_256_color_reduction: bool = False):
        self.path = path
        self.width = target_width
        self.pixels = None
        self.height = 0
        self.enable_256_color_reduction = enable_256_color_reduction
        self._palette_map = None # Stores mapping from Pillow's palette index to standard ANSI 256 index
        
        self._load_and_resize()

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

    # Converts an RGB tuple to the closest standard ANSI 256-color index.
    # This function can be replaced by a more optimized lookup table if provided.
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

    def _load_and_resize(self):
        global cli_width, cli_height # Access global terminal dimensions

        img = Image.open(self.path).convert('RGBA') # Read as RGBA to support transparency
        aspect = img.height / img.width

        original_img_width = img.width
        original_img_height = img.height

        # Determine the maximum allowed dimensions based on all constraints
        max_allowed_width = min(original_img_width, cli_width, self.width)


        max_allowed_height = min(original_img_height, cli_height * 2)


        
        # Start by scaling based on the max_allowed_width.
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
                top = self.pixels[x, y]
                bottom = self.pixels[x, y+1]
                
                # Check alpha channels if they exist
                t_alpha = top[3] if len(top) > 3 else 255
                b_alpha = bottom[3] if len(bottom) > 3 else 255

                # Pre-process colors for the final push
                if self.enable_256_color_reduction:
                    top_color = self._rgb_to_ansi256(top)
                    bottom_color = self._rgb_to_ansi256(bottom)
                else:
                    top_color = top
                    bottom_color = bottom

                if t_alpha < threshold and b_alpha < threshold:
                    # Both transparent, skip this cell
                    continue
                elif t_alpha < threshold:
                    # Top transparent, draw bottom only using ▄ (lower half block)
                    # We use the bottom color as the foreground of ▄
                    push_func(start_y + (y // 2), start_x + x, "▄", bottom_color, None, 0)
                elif b_alpha < threshold:
                    # Bottom transparent, draw top only using ▀ (upper half block)
                    # We use the top color as the foreground of ▀
                    push_func(start_y + (y // 2), start_x + x, "▀", top_color, None, 0)
                else:
                    # Both opaque, draw normally
                    push_func(start_y + (y // 2), start_x + x, "▀", top_color, bottom_color, 0)






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
    
    # Pre-initialize image to avoid high CPU usage in loop
    image = ImageRenderer("img/sanae_RGBA.png", 59, True)
    
    while is_running:
        # 1. 动态感知尺寸
        listen_size() 
        
        # 2. 清除缓冲区，确保透明像素不会留残影
        clear_prepare()
        
        # 3. 逻辑产出
        text(1, 1, f"Frame: {frame_count}", "test256")
        text(2, 1, "Hello, world", "test8")

        # 4. 绘制图像
        image.draw(0, 0, push)
        
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
