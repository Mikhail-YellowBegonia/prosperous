import sys
import os


def get_visual_width(text):
    import unicodedata

    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ("W", "F"):
            width += 2
        else:
            width += 1
    return width


def ansilookup(style_obj):
    if style_obj is None:
        return ""

    parts = []

    # 处理基础样式属性
    style_map = {
        "bold": "1",
        "dim": "2",
        "italic": "3",
        "underline": "4",
        "blink": "5",
        "reverse": "7",
        "hidden": "8",
        "strike": "9",
    }

    for attr, code in style_map.items():
        if getattr(style_obj, attr, False):
            parts.append(code)

    fg = getattr(style_obj, "fg", None)
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

    bg = getattr(style_obj, "bg", None)
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
        return "\033[0m"

    return "\033[0m\033[" + ";".join(parts) + "m"


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
