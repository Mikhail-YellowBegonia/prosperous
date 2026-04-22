import time
import random
from live import Live
from components import Panel, InputBox, Text, ProgressBar, LogView
from interaction import FocusManager
from styles import Style

# ── 模拟数据 ──────────────────────────────────────────────
cpu = 0.45
mem = 0.62
start_time = time.time()

def next_cpu():
    global cpu
    cpu = max(0.0, min(1.0, cpu + random.uniform(-0.03, 0.03)))
    return cpu

def next_mem():
    global mem
    mem = max(0.0, min(1.0, mem + random.uniform(-0.01, 0.01)))
    return mem

def uptime_str():
    s = int(time.time() - start_time)
    return f"{s // 3600:02}:{(s % 3600) // 60:02}:{s % 60:02}"

# ── App ───────────────────────────────────────────────────
W = 76
status_text = "idle"

with Live(fps=30, logic_fps=60) as live:
    focus = FocusManager()
    log   = LogView(pos=(1, 1), width=W - 2, height=5, style=Style(fg=250))
    log.append("[SYSTEM] Prosperous Monitor started.")

    cmd_box    = InputBox(pos=(1, 1), width=40, label="COMMAND")
    txt_status = Text(pos=(1, 44), text=lambda: f"Status: {status_text}", style=Style(fg=82))

    live.add(Panel(
        pos=(1, 2), width=W, height=7, title="METRICS",
        children=[
            Text(pos=(1, 2),  text="CPU  ", style=Style(fg=244)),
            ProgressBar(pos=(1, 7),  width=30, value=next_cpu),
            Text(pos=(2, 2),  text="MEM  ", style=Style(fg=244)),
            ProgressBar(pos=(2, 7),  width=30, value=next_mem,
                        filled_style=Style(fg=(100, 160, 240))),
            Text(pos=(4, 2),  text=lambda: f"Uptime  {uptime_str()}", style=Style(fg=244)),
            Text(pos=(4, 30), text="Render  30 fps",               style=Style(fg=244)),
        ]
    ))
    live.add(Panel(pos=(9, 2),  width=W, height=7, title="LOG",     children=[log]))
    live.add(Panel(pos=(17, 2), width=W, height=5, title="CONTROL", children=[cmd_box, txt_status]))
    live.add(Text(pos=(23, 2), text="ENTER: submit  |  ESC: quit", style=Style(fg=238)))

    focus.add_component(cmd_box)

    def on_submit():
        global status_text
        cmd = cmd_box.text.strip()
        if cmd:
            log.append(f"[CMD] {cmd}")
            status_text = f"last: {cmd[:20]}"
        cmd_box.text = ""

    cmd_box.on_enter = on_submit

    while live.running:
        for key in live.poll():
            if key == "ESC":
                live.engine.is_running = False
                break
            focus.handle_input(key)

        with live.frame():
            pass
