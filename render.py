import os
import sys
import time
import threading

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
        width = 2 if ord(char) > 128 else 1

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
        if ord(char) < 128:
            length += 1
        else:
            length += 2
    return length

def ansilookup(fg, bg, style):
    parts = []

    # 1. 样式处理：只有当 style 不是 None 且不为 0 时才添加（0 往往是默认，可加可不加）
    if style is not None:
        parts.append(str(style))

    # 2. 前景色处理
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

def logic_loop():
    global frame_count, is_running
    while is_running:
        # 1. 动态感知尺寸 (逻辑端负责感知，并重建 buffer)
        listen_size() 
        
        # 2. 逻辑产出 (写入 screen_prepare)
        # 你可以根据 frame_count 让文字动起来
        text(1, 1, f"Frame: {frame_count}", "test256")
        text(2, 1, "Hello, world", "test8")
        
        time.sleep(0.01) # 逻辑频率略高于渲染

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








