import time
import random
from live import Live
from components import Panel, InputBox, Button, Text, ProgressBar, LogView, VStack, HStack
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
    # ── 组件 ─────────────────────────────────────────────
    log = LogView(width=W - 4, height=5, style=Style(fg=250))
    log.append("[SYSTEM] Prosperous Monitor started.")

    cmd_box = InputBox(width=34, label="COMMAND", on_enter=lambda: submit())

    # ── Modal（初始隐藏，visible=False 使其子组件跳过自动焦点注册）
    modal = Panel(
        pos=(7, 18),
        width=40,
        height=6,
        title="CONFIRM",
        layer=10,
        visible=False,
        children=[
            Text(pos=(0, 1), text="Clear all tasks? This cannot be undone."),
            HStack(
                pos=(2, 2),
                gap=4,
                children=[
                    Button(label="YES", width=10, on_enter=lambda: confirm(True)),
                    Button(label="NO", width=10, on_enter=lambda: confirm(False)),
                ],
            ),
        ],
    )

    def confirm(yes):
        global status_text
        if yes:
            status_text = "cleared"
            log.append("[ACTION] Tasks cleared.")
        modal.visible = False
        live.focus.pop_group()

    def open_modal():
        modal.visible = True
        btn_yes, btn_no = modal.children[1].children
        live.focus.push_group([btn_yes, btn_no])

    # ── 场景声明（live.add 自动注册 focusable 组件）────────
    panel_metrics = Panel(
        pos=(1, 2),
        width=W,
        height=7,
        title="METRICS",
        children=[
            VStack(
                children=[
                    HStack(
                        gap=2,
                        children=[
                            Text(text="CPU  ", style=Style(fg=244)),
                            ProgressBar(width=28, value=next_cpu),
                        ],
                    ),
                    HStack(
                        gap=2,
                        children=[
                            Text(text="MEM  ", style=Style(fg=244)),
                            ProgressBar(
                                width=28,
                                value=next_mem,
                                filled_style=Style(fg=(100, 160, 240)),
                            ),
                        ],
                    ),
                ]
            ),
            HStack(
                pos=(3, 0),
                gap=4,
                children=[
                    Text(text=lambda: f"Uptime  {uptime_str()}", style=Style(fg=244)),
                    Text(text="Render  30 fps", style=Style(fg=244)),
                ],
            ),
        ],
    )

    panel_log = Panel(pos=(9, 2), width=W, height=7, title="LOG", children=[log])

    panel_ctrl = Panel(
        pos=(17, 2),
        width=W,
        height=5,
        title="CONTROL",
        children=[
            HStack(
                gap=2,
                children=[
                    cmd_box,
                    Button(label="Submit", width=12, on_enter=lambda: submit()),
                    Button(label="Clear", width=10, style=Style(fg=196), on_enter=open_modal),
                    Text(text=lambda: status_text, style=Style(fg=82)),
                ],
            ),
        ],
    )

    hint = Text(
        pos=(23, 2),
        text="Arrows: focus  |  ENTER: action  |  ESC: quit",
        style=Style(fg=238),
    )

    live.add(panel_metrics)
    live.add(panel_log)
    live.add(panel_ctrl)  # cmd_box, btn_submit, btn_clear 自动注册
    live.add(modal)  # visible=False，btn_yes/btn_no 跳过
    live.add(hint)

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
            live.focus.handle_input(key)

        with live.frame():
            pass
