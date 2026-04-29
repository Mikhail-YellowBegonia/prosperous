import time
import math
import sys
import os

# 确保可以导入根目录下的模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from prosperous import (
    Live, BaseComponent, Box, Panel, ScrollBox, 
    VStack, Label, Text, Button, Style, Kinetic, Tween, ease_in_out,
    BOX_SINGLE
)

class AnimatedBox(Panel):
    """一个带有内部动力学动画的盒子。"""
    def __init__(self, id_name, **kwargs):
        super().__init__(width=20, height=5, title=id_name, **kwargs)
        self.k_x = Kinetic(0, stiffness=100, damping=10)
        self.target_x = 30
        self.k_x.set_target(self.target_x)

    def update(self, dt):
        if abs(self.k_x.value - self.target_x) < 0.1:
            self.target_x = 0 if self.target_x == 30 else 30
            self.k_x.set_target(self.target_x)
        self.k_x.update(dt)
        self.pos = (self.pos[0], int(self.k_x.value))

class FeatureVerifyApp:
    def __init__(self):
        # 1. 创建滚动容器
        self.scroll_box = ScrollBox(
            pos=(3, 5), width=60, height=15,
            border_style=BOX_SINGLE, padding=1,
            clipping=True,
            focusable=True,
            style=Style(fg=244),
            focus_style=Style(fg=255, bold=True)
        )
        
        # 2. 创建布局容器
        self.content = VStack(gap=1)
        self.scroll_box.add_child(self.content)

        # 3. 填充多样化组件
        self.content.add_child(Text(text="<yellow bold>--- ANIMATION VERIFICATION ---</>", markup=True))
        
        # 动力学组件
        self.k_box = AnimatedBox("KINETIC")
        self.content.add_child(self.k_box)
        
        # Tween 组件
        self.tween_label = Text(text="TWEENING COLOR...")
        self.content.add_child(self.tween_label)
        self.color_anim = Tween(start=16, end=231, duration=2.0, easing=ease_in_out)

        self.content.add_child(Text(text="<blue bold>--- FOCUS VERIFICATION ---</>", markup=True))
        self.btns = []
        for i in range(10):
            btn = Button(label=f"BUTTON {i+1}", width=20)
            self.btns.append(btn)
            self.content.add_child(btn)

    def run(self):
        with Live(fps=30) as live:
            live.add(self.scroll_box)
            live.add(Label(pos=(1, 2), text="[UP/DOWN] Scroll | [TAB] Focus | [ESC] Quit", style=Style(fg=244)))
            
            last_time = time.perf_counter()
            while live.running:
                dt = time.perf_counter() - last_time
                last_time = time.perf_counter()

                for key in live.poll():
                    if key == "ESC": live.stop()
                    # 将输入交给焦点系统
                    live.focus.handle_input(key)

                # 更新动画
                self.k_box.update(dt)
                
                # 更新 Tween 颜色
                if self.color_anim.done:
                    self.color_anim = Tween(
                        start=self.color_anim.end, 
                        end=16 if self.color_anim.end > 120 else 231, 
                        duration=2.0, easing=ease_in_out
                    )
                color = int(self.color_anim.value)
                self.tween_label.style = Style(fg=color, bold=True)

                with live.frame():
                    pass

if __name__ == "__main__":
    FeatureVerifyApp().run()
