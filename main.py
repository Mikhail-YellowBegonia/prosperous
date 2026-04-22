from live import Live
from components import Panel, InputBox, Text
from interaction import FocusManager
from styles import Style

frame_count = 0
last_submit = ""

with Live(fps=30) as live:
    focus = FocusManager()

    panel  = Panel(pos=(2, 2), width=75, height=8, title="EVENT DISPATCH TEST")
    input1 = InputBox(pos=(2, 3), width=30, label="BOX ONE")
    input2 = InputBox(pos=(2, 38), width=30, label="BOX TWO")

    hint   = Text(pos=(11, 2), text="LEFT/RIGHT: switch focus  |  ENTER: submit  |  ESC: quit", style=Style(fg=238))
    status = Text(pos=(12, 2), text=lambda: f"Frame: {frame_count}  |  Last submit: {last_submit!r}", style=Style(fg=244))

    panel.add_child(input1)
    panel.add_child(input2)
    focus.add_component(input1)
    focus.add_component(input2)

    # 组件级回调：ENTER 提交时保存内容，清空输入框
    def submit(box):
        global last_submit
        last_submit = box.text
        box.text = ""

    input1.on_enter = lambda: submit(input1)
    input2.on_enter = lambda: submit(input2)

    while live.running:
        for key in live.poll():
            if key == "ESC":
                live.engine.is_running = False
                break
            focus.handle_input(key)

        frame_count += 1

        with live.frame() as engine:
            panel.draw(engine)
            hint.draw(engine)
            status.draw(engine)
