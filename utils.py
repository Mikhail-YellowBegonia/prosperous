import sys
import os

def ansilookup(fg, bg, style):
    parts = []
    if style is not None:
        parts.append(str(style))

    if fg is not None:
        if isinstance(fg, int):
            if fg < 8:
                parts.append(str(30 + fg))
            elif fg < 16:
                parts.append(str(90 + (fg - 8)))
            else:
                parts.append(f"38;5;{fg}")
        elif isinstance(fg, tuple):
            parts.append(f"38;2;{fg[0]};{fg[1]};{fg[2]}")

    if bg is not None:
        if isinstance(bg, int):
            if bg < 8:
                parts.append(str(40 + bg))
            elif bg < 16:
                parts.append(str(100 + (bg - 8)))
            else:
                parts.append(f"48;5;{bg}")
        elif isinstance(bg, tuple):
            parts.append(f"48;2;{bg[0]};{bg[1]};{bg[2]}")

    if not parts:
        return ""
    
    return "\033[" + ";".join(parts) + "m"

def clear_screen():
    sys.stdout.write("\033[3J\033[2J\033[H")
    sys.stdout.flush()

def cleanup(cli_height=24):
    sys.stdout.write(f"\033[{cli_height + 1};1H\033[0m\n\033[?25h")
    sys.stdout.flush()

def debug_log(msg):
    # Log to a file in the project root
    with open("debug.log", "a") as f:
        f.write(str(msg) + "\n")
