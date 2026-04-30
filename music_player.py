import math
import time
from prosperous import (
    Live,
    BaseComponent,
    VStack,
    HStack,
    Label,
    Text,
    Style,
    Tween,
    Kinetic,
    ease_out,
    ImageRenderer,
)
from prosperous.utils import get_visual_width

# ── Custom Components ────────────────────────────────────────


class KineticFocusBox(BaseComponent):
    """一个物理驱动的焦点跟随框，拥有动量和弹性感。"""

    def __init__(self, target_card, layer=5):
        super().__init__(layer=layer)
        # 使用标准推荐参数 (stiffness=120, damping=16)
        self.k_y = Kinetic(target_card.pos[0])
        self.k_x = Kinetic(target_card.pos[1])
        self.k_w = Kinetic(target_card.width)
        self.k_h = Kinetic(target_card.height)

    def update(self, dt, target_card):
        # 实时感应目标的物理属性
        self.k_y.set_target(target_card.pos[0])
        self.k_x.set_target(target_card.pos[1])
        self.k_w.set_target(target_card.width)
        self.k_h.set_target(target_card.height)

        # 步进
        self.k_y.update(dt)
        self.k_x.update(dt)
        self.k_w.update(dt)
        self.k_h.update(dt)

    def draw(self, engine):
        y, x = round(self.k_y.value), round(self.k_x.value)
        w, h = round(self.k_w.value), round(self.k_h.value)

        # 绘制一个亮色边框以示区别
        style = Style(fg=81, bold=True)
        top = "▛" + "▀" * (w - 2) + "▜"
        bot = "▙" + "▄" * (w - 2) + "▟"

        engine.push(y, x, top, style)
        for i in range(1, h - 1):
            engine.push(y + i, x, "▌", style)
            engine.push(y + i, x + w - 1, "▐", style)
        engine.push(y + h - 1, x, bot, style)


class AlbumArt(BaseComponent):
    """Aspect-aware Album Art with square-cat default."""

    def __init__(self, path="img/square_cat.png", pos=(1, 5), layer=0):
        super().__init__(pos=pos, layer=layer)
        self.width = 21
        self.height = 11
        self.renderer = ImageRenderer(path, self.width - 2)

    def get_height(self):
        return self.height

    def get_width(self):
        return self.width

    def draw(self, engine):
        if not self.visible:
            return
        ay, ax = self.get_absolute_pos()
        border_style = Style(fg=242)
        self.renderer.draw(ay + 1, ax + 1, engine.push_image)
        top = "┏" + "━" * (self.width - 2) + "┓"
        bot = "┗" + "━" * (self.width - 2) + "┛"
        engine.push(ay, ax, top, border_style)
        for i in range(1, self.height - 1):
            engine.push(ay + i, ax, "┃", border_style)
            engine.push(ay + i, ax + self.width - 1, "┃", border_style)
        engine.push(ay + self.height - 1, ax, bot, border_style)
        super().draw(engine)


class SpectrumVisualizer(BaseComponent):
    """Enhanced static visualizer."""

    def __init__(self, pos=(0, 0), width=40, height=5, style=None, layer=0):
        super().__init__(pos=pos, style=style, layer=layer)
        self.width = width
        self.height = height
        self.seed_heights = [
            0.2,
            0.4,
            0.8,
            0.6,
            0.9,
            0.3,
            0.5,
            0.7,
            1.0,
            0.4,
            0.2,
            0.6,
            0.8,
            0.5,
            0.3,
            0.7,
            0.9,
            0.4,
        ]

    def draw(self, engine):
        if not self.visible:
            return
        ay, ax = self.get_absolute_pos()
        chars = " ▂▃▄▅▆▇█"
        for i in range(self.width):
            val = self.seed_heights[i % len(self.seed_heights)]
            h = int(val * self.height)
            for row in range(self.height):
                color = 75 if row < 2 else 81
                char = (
                    "█"
                    if row < h
                    else (chars[int((val * self.height - h) * 8)] if row == h else " ")
                )
                engine.push(ay + (self.height - 1 - row), ax + i, char, Style(fg=color))
        super().draw(engine)


class SongCard(BaseComponent):
    def __init__(
        self,
        title,
        album,
        singer,
        duration,
        progress=0.0,
        pos=(0, 0),
        width=55,
        height=5,
        style=None,
        layer=0,
        selected=False,
    ):
        super().__init__(pos=pos, style=style, layer=layer)
        self.title, self.album, self.singer, self.duration = title, album, singer, duration
        self.progress, self.width, self.height, self.selected = progress, width, height, selected

    def draw(self, engine):
        if not self.visible:
            return
        ay, ax = self.get_absolute_pos()
        border_color = 75 if self.selected else 237
        content_style = Style(fg=255) if self.selected else Style(fg=244)
        engine.clear_rect(ay, ax, self.height, self.width, style=Style(bg=None))
        engine.push(ay, ax, "╭" + "─" * (self.width - 2) + "╮", Style(fg=border_color))
        for i in range(1, 4):
            engine.push(ay + i, ax, "│" + " " * (self.width - 2) + "│", Style(fg=border_color))
        engine.push(ay + 4, ax, "╰" + "─" * (self.width - 2) + "╯", Style(fg=border_color))
        engine.push(ay + 1, ax + 2, self.title[: self.width - 10], content_style)
        bar_w = self.width - 4
        filled = int(bar_w * self.progress)
        engine.push(ay + 2, ax + 2, "█" * filled, Style(fg=111 if self.selected else 239))
        engine.push(ay + 2, ax + 2 + filled, "░" * (bar_w - filled), Style(fg=234))
        meta_style = Style(fg=81 if self.selected else 240)
        engine.push(ay + 3, ax + 2, self.duration, meta_style)
        engine.push(
            ay + 3,
            ax + (self.width - get_visual_width(self.album[:15])) // 2,
            f"󰀥 {self.album[:15]}",
            Style(fg=141 if self.selected else 238),
        )
        engine.push(
            ay + 3,
            ax + self.width - 2 - get_visual_width(self.singer[:15]),
            f"󰠃 {self.singer[:15]}",
            Style(fg=214 if self.selected else 238),
        )
        if self.selected:
            engine.push(ay + 2, ax + self.width, " ◀ NOW PLAYING", Style(fg=255, bold=True))
        super().draw(engine)


def main():
    songs_data = [
        {"title": "This is a song", "album": "Alubm", "singer": "Singer", "duration": "03:35"},
        {"title": "Midnight City", "album": "Hurry Up", "singer": "M83", "duration": "04:03"},
        {"title": "Starboy", "album": "Starboy", "singer": "The Weeknd", "duration": "03:50"},
        {
            "title": "Blinding Lights",
            "album": "After Hours",
            "singer": "The Weeknd",
            "duration": "03:22",
        },
        {
            "title": "Levitating",
            "album": "Future Nostalgia",
            "singer": "Dua Lipa",
            "duration": "03:23",
        },
        {
            "title": "Save Your Tears",
            "album": "After Hours",
            "singer": "The Weeknd",
            "duration": "03:35",
        },
        {
            "title": "Physical",
            "album": "Future Nostalgia",
            "singer": "Dua Lipa",
            "duration": "03:13",
        },
        {"title": "One Kiss", "album": "One Kiss", "singer": "Calvin Harris", "duration": "03:34"},
    ]

    target_index = 0
    idx_tween = Tween(0, 0, 0.4, easing=ease_out)

    with Live(fps=30, logic_fps=60) as live:
        art = AlbumArt(pos=(1, 5))
        title_text = Text(
            pos=(10, 5), text="<bright_white bold>PROSPEROUS</> <#hot>MUSIC PLAYER</>", markup=True
        )
        lyric_stack = VStack(
            pos=(15, 5),
            children=[
                Label(text="You're the light, you're the night", style=Style(fg=244)),
                Label(text="You're the color of my blood", style=Style(fg=255, bold=True)),
                Label(text="You're the cure, you're the pain", style=Style(fg=244)),
            ],
        )
        controls = HStack(
            pos=(13, 5),
            gap=4,
            children=[
                Label(text="󰐊 PLAYING", style=Style(fg=118, bold=True)),
                Label(text="󰕇 CYCLE", style=Style(fg=81)),
                Label(text="󰓠 44.1kHz / 24bit", style=Style(fg=240)),
            ],
        )
        vis = SpectrumVisualizer(pos=(20, 5), width=40, height=6)
        live.add(art)
        live.add(title_text)
        live.add(lyric_stack)
        live.add(controls)
        live.add(vis)

        cards = []

        def calculate_layout(current_idx):
            base_y, base_x = 12, 85
            layout_data = []
            for i in range(len(songs_data)):
                diff = i - current_idx
                y = round(base_y + diff * 3.5)
                curve_x = round(diff**2 * 4.5)
                layer = int(30 - abs(i - target_index))
                selected = i == target_index
                layout_data.append((y, base_x + curve_x, layer, selected))
            return layout_data

        for i, song in enumerate(songs_data):
            card = SongCard(
                title=song["title"],
                album=song["album"],
                singer=song["singer"],
                duration=song["duration"],
            )
            cards.append(card)
            live.add(card)

        # 实例化幽灵焦点框
        ghost = KineticFocusBox(cards[target_index])
        live.add(ghost)

        last_time = time.perf_counter()
        while live.running:
            now = time.perf_counter()
            dt = now - last_time
            last_time = now

            for key in live.poll():
                if key == "ESC":
                    live.stop()
                    break
                if key == "UP" and target_index > 0:
                    target_index -= 1
                    idx_tween.restart(start=idx_tween.value, end=target_index)
                if key == "DOWN" and target_index < len(songs_data) - 1:
                    target_index += 1
                    idx_tween.restart(start=idx_tween.value, end=target_index)

            smoothed_idx = idx_tween.value
            layout_data = calculate_layout(smoothed_idx)
            for i, (y, x, l, s) in enumerate(layout_data):
                cards[i].pos = (y, x)
                cards[i].layer = l
                cards[i].selected = s

            # 物理步进
            ghost.update(dt, cards[target_index])

            with live.frame():
                playing_card = cards[target_index]
                playing_card.progress = (math.sin(time.time() * 2) + 1) / 2


if __name__ == "__main__":
    main()
