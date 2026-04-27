import time
import math
import sys
import os

# 确保可以导入根目录下的模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from prosperous import Live, BaseComponent, Box, Label, VStack, HStack, Style, BOX_DOUBLE, BOX_SINGLE, Kinetic

class TargetBox(Box):
    def __init__(self, id_name, pos=(0, 0), width=10, height=5):
        super().__init__(pos=pos, width=width, height=height, border_style=BOX_SINGLE)
        self.id_name = id_name
        self.is_active = False

    def draw(self, engine):
        self.style = Style(fg=220, bold=True) if self.is_active else Style(fg=238)
        super().draw(engine)
        ay, ax = self.get_absolute_pos()
        engine.push(ay, ax + 1, f" {self.id_name} ", self.style)

class KineticFollower(BaseComponent):
    def __init__(self, target, layer=50):
        super().__init__(layer=layer)
        self.target = target
        # 初始推荐值
        self.stiffness = 120.0
        self.damping = 16.0
        
        self.k_y = Kinetic(target.pos[0], stiffness=self.stiffness, damping=self.damping)
        self.k_x = Kinetic(target.pos[1], stiffness=self.stiffness, damping=self.damping)
        self.k_w = Kinetic(target.width, stiffness=self.stiffness, damping=self.damping)
        self.k_h = Kinetic(target.height, stiffness=self.stiffness, damping=self.damping)

    def sync_params(self):
        """同步调节参数到所有动力学实例。"""
        for k in [self.k_y, self.k_x, self.k_w, self.k_h]:
            k.stiffness = self.stiffness
            k.damping = self.damping

    def set_target(self, target):
        self.target = target

    def update(self, dt):
        self.k_y.set_target(self.target.pos[0])
        self.k_x.set_target(self.target.pos[1])
        self.k_w.set_target(self.target.width)
        self.k_h.set_target(self.target.height)
        for k in [self.k_y, self.k_x, self.k_w, self.k_h]:
            k.update(dt)

    def draw(self, engine):
        y, x = round(self.k_y.value), round(self.k_x.value)
        w, h = round(self.k_w.value), round(self.k_h.value)
        style = Style(fg=81, bold=True)
        
        if w > 1 and h > 1:
            engine.push(y, x, "▛" + "▀" * (w - 2) + "▜", style)
            for i in range(1, h - 1):
                engine.push(y + i, x, "▌", style)
                engine.push(y + i, x + w - 1, "▐", style)
            engine.push(y + h - 1, x, "▙" + "▄" * (w - 2) + "▟", style)

def main():
    targets_data = [
        {"id": "A", "pos": (5, 10), "w": 25, "h": 6},
        {"id": "B", "pos": (4, 55), "w": 15, "h": 12},
        {"id": "C", "pos": (16, 8), "w": 40, "h": 5},
        {"id": "D", "pos": (18, 60), "w": 20, "h": 4},
    ]

    with Live(fps=30, logic_fps=60) as live:
        boxes = [TargetBox(d["id"], d["pos"], d["w"], d["h"]) for d in targets_data]
        for b in boxes: live.add(b)

        current_idx = 0
        boxes[current_idx].is_active = True
        follower = KineticFollower(boxes[current_idx], layer=100)
        live.add(follower)

        # UI 说明和控制面板
        live.add(Label(pos=(1, 2), text="[TAB/Arrows] Move | [+/-] Stiffness | [9/0] Damping | [R] Reset | [ESC] Quit", style=Style(fg=244)))
        
        panel_y = 22
        stiff_label = Label(pos=(panel_y, 2), text="")
        damp_label = Label(pos=(panel_y + 1, 2), text="")
        live.add(stiff_label); live.add(damp_label)

        last_time = time.perf_counter()
        while live.running:
            dt = time.perf_counter() - last_time
            last_time = time.perf_counter()

            for key in live.poll():
                if key == "ESC": live.stop()
                
                # 切换目标
                if key in ("TAB", "RIGHT", "DOWN", "LEFT", "UP"):
                    boxes[current_idx].is_active = False
                    step = 1 if key in ("TAB", "RIGHT", "DOWN") else -1
                    current_idx = (current_idx + step) % len(boxes)
                    boxes[current_idx].is_active = True
                    follower.set_target(boxes[current_idx])
                
                # 调节参数
                if key == "+": follower.stiffness += 10
                if key == "-": follower.stiffness = max(10, follower.stiffness - 10)
                if key == "0": follower.damping += 1
                if key == "9": follower.damping = max(1, follower.damping - 1)
                if key == "r":
                    follower.stiffness, follower.damping = 120.0, 16.0
                
                follower.sync_params()

            follower.update(dt)
            stiff_label.text = f"STIFFNESS: <#87afff bold>{follower.stiffness:>4.0f}</> (Spring Strength)"
            damp_label.text = f"DAMPING:   <#87afff bold>{follower.damping:>4.0f}</> (Stability)"
            stiff_label.markup = damp_label.markup = True

            with live.frame():
                pass

if __name__ == "__main__":
    main()
