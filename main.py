from live import Live
from components import Panel, InputBox, Text
from interaction import FocusManager
from styles import Style

frame_count = 0

with Live(fps=30) as live:
    focus = FocusManager()

    panel = Panel(pos=(2, 2), width=75, height=10, title="FOCUS SYSTEM TEST")
    input1 = InputBox(pos=(2, 3), width=30, label="BOX ONE")
    input2 = InputBox(pos=(2, 38), width=30, label="BOX TWO")
    status = Text(pos=(12, 2), text=lambda: f"Frame: {frame_count} | Focused: {focus.get_focused().__class__.__name__}", style=Style(fg=244))

    panel.add_child(input1)
    panel.add_child(input2)
    focus.add_component(input1)
    focus.add_component(input2)

    while live.running:
        for key in live.poll():
            focus.handle_input(key)
        frame_count += 1

        with live.frame() as engine:
            panel.draw(engine)
            status.draw(engine)
            engine.push(13, 2, "Use LEFT/RIGHT to switch focus, type to input.", Style(fg=238))
