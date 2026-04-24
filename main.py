import time
import random
from live import Live
from components import Panel, InputBox, Button, Text, ProgressBar, LogView
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
# Theme 默认 padding=1，子组件 pos=(0,0) 即内容区左上角
W = 76
status_text = "idle"

with Live(fps=30, logic_fps=60) as live:
    focus = FocusManager()

    log = LogView(pos=(0, 0), width=W - 4, height=5, style=Style(fg=250))
    log.append("[SYSTEM] Prosperous Monitor started.")

    # ── Modal（初始隐藏）────────────────────────────────
    modal = Panel(
        pos=(7, 18), width=40, height=6, title="CONFIRM", layer=10,
        visible=False,
        children=[
            Text(pos=(0, 1), text="Clear all tasks? This cannot be undone."),
            Button(pos=(2, 2),  label="YES", width=10, on_enter=lambda: confirm(True)),
            Button(pos=(2, 16), label="NO",  width=10, on_enter=lambda: confirm(False)),
        ]
    )

    def confirm(yes):
        global status_text
        if yes:
            status_text = "cleared"
            log.append("[ACTION] Tasks cleared.")
        modal.visible = False
        focus.pop_group()

    def open_modal():
        modal.visible = True
        focus.push_group([modal.children[1], modal.children[2]])

    cmd_box = InputBox(pos=(0, 0), width=34, label="COMMAND",
                       on_enter=lambda: submit())

    # ── 场景声明 ─────────────────────────────────────────
    live.add(Panel(
        pos=(1, 2), width=W, height=7, title="METRICS",
        children=[
            Text(pos=(0, 0), text="CPU  ", style=Style(fg=244)),
            ProgressBar(pos=(0, 5), width=28, value=next_cpu),
            Text(pos=(1, 0), text="MEM  ", style=Style(fg=244)),
            ProgressBar(pos=(1, 5), width=28, value=next_mem,
                        filled_style=Style(fg=(100, 160, 240))),
            Text(pos=(3, 0), text=lambda: f"Uptime  {uptime_str()}", style=Style(fg=244)),
            Text(pos=(3, 28), text="Render  30 fps", style=Style(fg=244)),
        ]
    ))
    live.add(Panel(pos=(9,  2), width=W, height=7, title="LOG", children=[log]))
    live.add(Panel(
        pos=(17, 2), width=W, height=5, title="CONTROL",
        children=[
            cmd_box,
            Button(pos=(0, 36), label="Submit", width=12, on_enter=lambda: submit()),
            Button(pos=(0, 50), label="Clear",  width=10,
                   style=Style(fg=196), on_enter=open_modal),
            Text(pos=(0, 62), text=lambda: status_text, style=Style(fg=82)),
        ]
    ))
    live.add(modal)
    live.add(Text(
        pos=(23, 2),
        text="Arrows: focus  |  ENTER: action  |  ESC: quit",
        style=Style(fg=238)
    ))

    focus.add_component(cmd_box)
    focus.add_component(live._scene[2].children[1])  # btn_submit
    focus.add_component(live._scene[2].children[2])  # btn_clear

    def submit():
        global status_text
        cmd = cmd_box.text.strip()
        if cmd:
            log.append(f"[CMD] {cmd}")
            status_text = cmd[:16]
        cmd_box.text = ""

    # ── 主循环 ────────────────────────────────────────────
    while live.running:
        for key in live.poll():
            if key == "ESC":
                live.stop()
                break
            focus.handle_input(key)

        with live.frame():
            pass
