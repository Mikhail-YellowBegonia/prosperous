import sys
import time

cli_width = 120
cli_height = 36

# per char slot in buffer/dump: (char->str, fg->int, bg->int, style->int)
screen_buffer = [[(" ", 0, 0, 0) for _ in range(cli_width)] for _ in range(cli_height)]
screen_dump = [[("A", 0, 0, 0) for _ in range(cli_width)] for _ in range(cli_height)]

# per char slot in diff: (y, x, char, fg, bg, style)
screen_diff = []


#region core

def push(y, x, content, fg, bg, style):
    current_x = x
    for char in content:
        width = 2 if ord(char) > 128 else 1
        
        screen_buffer[y][current_x] = (char, fg, bg, style)
        
        if width == 2:
            if current_x < cli_width - 2:
                screen_buffer[y][current_x + 1] = ("", fg, bg, style) 
                current_x+=2
            else:
                continue
            

        else:
            current_x += 1
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
    
    params = [str(style), str(fg), str(bg)]
    param_str = ";".join(params)
    
    sys.stdout.write(f"\033[{param_str}m{char}")
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
    return f"\033[{style};{fg};{bg}m"

def clear_screen():
    # 建议合并发送：先清屏，再归位
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def cleanup():
    # 1. 移到最后一行 2. 重置颜色 3. 换行 4. 显示光标
    sys.stdout.write(f"\033[{cli_height + 1};1H\033[0m\n\033[?25h")
    sys.stdout.flush()

#endregion

#region QoL

THEME = {
    "normal": (37, 40, 0),      # 白色文字，黑色背景，无样式
    "success": (32, 40, 1),     # 绿色加粗
    "danger": (31, 40, 5),      # 红色闪烁
    "ocean": (36, 44, 0),       # 青色文字，蓝色背景
}

def text(y,x,content,type = "normal"):
    push(y,x,content,THEME[type][0],THEME[type][1],THEME[type][2])

#endregion


# Main Program

try:
    clear_screen()

    while True:
        time.sleep(0.1)
        text(0, 0, "你好世界")

        render()
    

finally:
    cleanup()








