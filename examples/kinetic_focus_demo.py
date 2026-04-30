import time
import math
import sys
import os

# 确保可以导入根目录下的模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from prosperous import (
    Live,
    BaseComponent,
    Box,
    Label,
    VStack,
    HStack,
    Style,
    BOX_DOUBLE,
    BOX_SINGLE,
    Kinetic,
)


class TargetBox(Box):
    def __init__(self, id_name, pos=(0, 0), width=10, height=5, culling=True):
        super().__init__(
            pos=pos, width=width, height=height, border_style=BOX_SINGLE, culling=culling
        )
        self.id_name = id_name
        self.is_active = False
        self.draw_count = 0

    def draw(self, engine):
        self.draw_count += 1
        self.style = Style(fg=220, bold=True) if self.is_active else Style(fg=238)
        super().draw(engine)
        ay, ax = self.get_absolute_pos()
        # 显示 ID 和 绘制计数（用于验证剔除）
        engine.push(ay, ax + 1, f" {self.id_name} ({self.draw_count}) ", self.style)


class KineticFollower(BaseComponent):
    def __init__(self, target, layer=50):
        super().__init__(layer=layer)
        self.target = target
        # 初始推荐值
        self.stiffness = 120.0
        self.damping = 16.0

        # 初始值设为目标位置
        ty, tx = target.pos
        self.k_y = Kinetic(ty, stiffness=self.stiffness, damping=self.damping)
        self.k_x = Kinetic(tx, stiffness=self.stiffness, damping=self.damping)
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
        if not self.visible or self._should_cull(engine):
            return

        # 核心修复：获取父级内容原点，将相对物理坐标转换为绝对坐标
        if not self.parent:
            py, px = 0, 0
        else:
            py, px = self.parent.get_child_origin(self)

        y = round(py + self.k_y.value)
        x = round(px + self.k_x.value)
        w, h = round(self.k_w.value), round(self.k_h.value)

        style = Style(fg=81, bold=True)

        if w > 1 and h > 1:
            engine.push(y, x, "▛" + "▀" * (w - 2) + "▜", style)
            for i in range(1, h - 1):
                engine.push(y + i, x, "▌", style)
                engine.push(y + i, x + w - 1, "▐", style)
            engine.push(y + h - 1, x, "▙" + "▄" * (w - 2) + "▟", style)


def main():
    # 调整坐标使其适合在 (20, 80) 的大视口内
    # 视口内容区原点相对于屏幕是 (5, 6)
    targets_data = [
        {"id": "SAFE", "pos": (2, 5), "w": 30, "h": 6},  # 完全在内
        {"id": "RIGHT", "pos": (12, 65), "w": 25, "h": 8},  # 跨越右边界
        {"id": "LEFT", "pos": (6, -10), "w": 20, "h": 10},  # 跨越左边界
        {"id": "OUT", "pos": (30, 20), "w": 20, "h": 5},  # 完全在下方外部
    ]

    with Live(fps=30, logic_fps=60) as live:
        from prosperous import Panel

        # 1. 创建大型裁剪视口 (Viewport)
        viewport = Panel(
            pos=(4, 5),
            width=80,
            height=20,
            title="PRESSURE TEST: CLIPPING & CULLING",
            clipping=True,
            style=Style(fg=242),
        )
        live.add(viewport)

        # 2. 填充内容块
        boxes = [TargetBox(d["id"], d["pos"], d["w"], d["h"], culling=True) for d in targets_data]
        for b in boxes:
            viewport.add_child(b)

        current_idx = 0
        boxes[current_idx].is_active = True

        follower = KineticFollower(boxes[current_idx], layer=100)
        viewport.add_child(follower)

        # UI 说明
        live.add(
            Label(
                pos=(1, 2),
                text="[TAB/Arrows] Switch | [C] Toggle Clip | [X] Toggle Cull | [ESC] Quit",
                style=Style(fg=250, bold=True),
            )
        )

        info_y = 25
        clip_label = Label(pos=(info_y, 2), text="")
        cull_label = Label(pos=(info_y + 1, 2), text="")
        live.add(clip_label)
        live.add(cull_label)

        last_time = time.perf_counter()
        while live.running:
            dt = time.perf_counter() - last_time
            last_time = time.perf_counter()

            for key in live.poll():
                if key == "ESC":
                    live.stop()

                # 切换目标
                if key in ("TAB", "RIGHT", "DOWN", "LEFT", "UP"):
                    boxes[current_idx].is_active = False
                    step = 1 if key in ("TAB", "RIGHT", "DOWN") else -1
                    current_idx = (current_idx + step) % len(boxes)
                    boxes[current_idx].is_active = True
                    follower.set_target(boxes[current_idx])

                # 切换裁剪/剔除开关
                if key == "c":
                    viewport.clipping = not viewport.clipping
                if key == "x":
                    for b in boxes:
                        b.culling = not b.culling
                    follower.culling = not follower.culling

            follower.update(dt)

            c_state = "<green bold>ON</>" if viewport.clipping else "<red bold>OFF</>"
            x_state = "<green bold>ON</>" if boxes[0].culling else "<red bold>OFF</>"
            clip_label.text = f"CLIPPING: {c_state} (Watch the edges of the box)"
            cull_label.text = f"CULLING:  {x_state} (Watch the draw count of 'OUT')"
            clip_label.markup = cull_label.markup = True

            with live.frame():
                pass


if __name__ == "__main__":
    main()
