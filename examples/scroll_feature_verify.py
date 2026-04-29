import time
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from prosperous import (
    Live, Panel, ScrollBox,
    VStack, Label, Text, Button, Style, Kinetic, Tween, ease_in_out,
    BOX_SINGLE,
)


class AnimatedBox(Panel):
    """内嵌 Kinetic 动画的面板，用于验证 ScrollBox 内子组件动画。"""

    def __init__(self, title, **kwargs):
        super().__init__(width=20, height=5, title=title, **kwargs)
        self._k = Kinetic(0, stiffness=100, damping=10)
        self._target = 30
        self._k.set_target(self._target)

    def update(self, dt):
        if abs(self._k.value - self._target) < 0.1:
            self._target = 0 if self._target == 30 else 30
            self._k.set_target(self._target)
        self._k.update(dt)
        self.pos = (self.pos[0], int(self._k.value))


class FeatureVerifyApp:
    def __init__(self):
        # ── ScrollBox ──────────────────────────────────────────────────────────
        self.scroll_box = ScrollBox(
            pos=(3, 5), width=60, height=15,
            border_style=BOX_SINGLE, padding=1,
            clipping=True,
            focusable=True,
            style=Style(fg=244),
            focus_style=Style(fg=255, bold=True),
        )

        content = VStack(gap=1)
        self.scroll_box.add_child(content)

        # ── 动画区 ─────────────────────────────────────────────────────────────
        content.add_child(Text(text="<yellow bold>─── ANIMATION ───</>", markup=True))
        self.k_box = AnimatedBox("KINETIC")
        content.add_child(self.k_box)

        self.tween_label = Text(text="TWEENING COLOR...")
        content.add_child(self.tween_label)
        self._color_tween = Tween(start=16, end=231, duration=2.0, easing=ease_in_out)

        # ── 焦点区 ─────────────────────────────────────────────────────────────
        content.add_child(Text(text="<blue bold>─── FOCUS ───</>", markup=True))
        self.btns = []
        for i in range(10):
            btn = Button(label=f"BUTTON {i + 1}", width=20)
            self.btns.append(btn)
            content.add_child(btn)

    def run(self):
        hint = "[↑/↓] Scroll  [Wheel] Scroll  [TAB] Focus  [ESC] Quit"

        with Live(fps=30) as live:
            live.add(self.scroll_box)
            live.add(Label(pos=(1, 2), text=hint, style=Style(fg=244)))

            last = time.perf_counter()
            while live.running:
                now = time.perf_counter()
                dt = now - last
                last = now

                for key in live.poll():
                    if key == "ESC":
                        live.stop()
                    live.focus.handle_input(key)

                # 推进动画
                self.k_box.update(dt)
                self.scroll_box.update(dt)

                # Tween 颜色循环
                if self._color_tween.done:
                    self._color_tween = Tween(
                        start=self._color_tween.end,
                        end=16 if self._color_tween.end > 120 else 231,
                        duration=2.0,
                        easing=ease_in_out,
                    )
                self.tween_label.style = Style(fg=self._color_tween.int_value, bold=True)

                with live.frame():
                    pass


if __name__ == "__main__":
    FeatureVerifyApp().run()
