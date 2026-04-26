import math
import time
from live import Live
from components import BaseComponent, VStack, HStack, Text
from styles import Style
from renderers import ImageRenderer
from utils import get_visual_width

# ── Custom Components ────────────────────────────────────────


class AlbumArt(BaseComponent):
    """Fixed 21x11 Album Art with thick border."""

    def __init__(self, path, pos=(1, 2), layer=0):
        # width=21 corresponds to roughly 11 rows in terminal height
        super().__init__(pos=pos, layer=layer)
        self.width = 21
        self.height = 11
        self.renderer = ImageRenderer(path, self.width)

    def get_height(self):
        return self.height

    def get_width(self):
        return self.width

    def draw(self, engine):
        if not self.visible:
            return
        ay, ax = self.get_absolute_pos()
        border_style = Style(fg=244)  # Metallic grey

        # Draw Image (rendered inside border)
        self.renderer.draw(ay + 1, ax + 1, engine.push_image)

        # Thick frame using heavy box drawing characters
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
            # Gradient color from bottom to top: blue -> cyan
            h = int(val * self.height)
            for row in range(self.height):
                color = 75 if row < 2 else 81
                char = " "
                if row < h:
                    char = "█"
                elif row == h:
                    char = chars[int((val * self.height - h) * 8)]
                engine.push(ay + (self.height - 1 - row), ax + i, char, Style(fg=color))
        super().draw(engine)


class SongCard(BaseComponent):
    """Opaque rich colored flat card with background clearing."""

    def __init__(
        self,
        title,
        album,
        singer,
        duration,
        progress=0.0,
        pos=(0, 0),
        width=50,
        height=5,
        style=None,
        layer=0,
        selected=False,
    ):
        super().__init__(pos=pos, style=style, layer=layer)
        self.title = title
        self.album = album
        self.singer = singer
        self.duration = duration
        self.progress = progress
        self.width = width
        self.height = height
        self.selected = selected

    def draw(self, engine):
        if not self.visible:
            return
        ay, ax = self.get_absolute_pos()

        # Selected high-contrast theme
        border_color = 75 if self.selected else 239
        bg_style = Style(fg=border_color)

        # ── BACKGROUND CLEARING (Essential for overlapping) ──
        # We push full-width strings to ensure the background is masked
        engine.push(ay, ax, "╭" + "─" * (self.width - 2) + "╮", bg_style)
        for i in range(1, 4):
            # Fill with spaces to mask lower layers
            engine.push(ay + i, ax, "│" + " " * (self.width - 2) + "│", bg_style)
        engine.push(ay + 4, ax, "╰" + "─" * (self.width - 2) + "╯", bg_style)

        # Content
        # Line 1: Title (Bold White)
        title_style = Style(fg=255, bold=True) if self.selected else Style(fg=248)
        engine.push(ay + 1, ax + 2, self.title[: self.width - 4], title_style)

        # Line 2: Themed Progress Bar
        bar_w = self.width - 4
        filled = int(bar_w * self.progress)
        engine.push(ay + 2, ax + 2, "█" * filled, Style(fg=111 if self.selected else 242))
        engine.push(ay + 2, ax + 2 + filled, "░" * (bar_w - filled), Style(fg=235))

        # Line 3: Multi-color Meta
        engine.push(ay + 3, ax + 2, self.duration, Style(fg=81))

        album_txt = f"󰀥 {self.album[:12]}"
        engine.push(
            ay + 3, ax + (self.width - get_visual_width(album_txt)) // 2, album_txt, Style(fg=141)
        )

        singer_txt = f"󰠃 {self.singer[:12]}"
        engine.push(
            ay + 3, ax + self.width - 2 - get_visual_width(singer_txt), singer_txt, Style(fg=214)
        )

        if self.selected:
            engine.push(ay + 2, ax + self.width, " ◀ NOW PLAYING", Style(fg=255, bold=True))

        super().draw(engine)


# ── Main Application ──────────────────────────────────────────


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

    target_index = 0.0
    smoothed_index = 0.0

    with Live(fps=30, logic_fps=60) as live:
        # Left Pane
        art = AlbumArt(path="img/square_cat.png", pos=(1, 5))

        lyric_stack = VStack(
            pos=(15, 5),
            gap=0,
            children=[
                Text(text="You're the light, you're the night", style=Style(fg=244)),
                Text(text="You're the color of my blood", style=Style(fg=255, bold=True)),
                Text(text="You're the cure, you're the pain", style=Style(fg=244)),
            ],
        )

        controls = HStack(
            pos=(13, 5),
            gap=4,
            children=[
                Text(text="󰐊 PLAYING", style=Style(fg=118, bold=True)),
                Text(text="󰕇 CYCLE", style=Style(fg=81)),
                Text(text="󰓠 44.1kHz / 24bit", style=Style(fg=240)),
            ],
        )

        vis = SpectrumVisualizer(pos=(20, 5), width=40, height=6)

        live.add(art)
        live.add(lyric_stack)
        live.add(controls)
        live.add(vis)

        cards = []

        def update_layout(idx):
            base_y = 12
            base_x = 80
            for i, card in enumerate(cards):
                diff = i - idx
                curve_x = diff**2 * 4
                # Round coordinates to nearest integer for rendering
                y = round(base_y + diff * 3)
                x = round(base_x + curve_x)
                card.pos = (y, x)
                # Layering logic: selected one is at top (20)
                card.layer = int(20 - abs(i - target_index))
                card.selected = i == int(target_index + 0.5)

        for i, song in enumerate(songs_data):
            card = SongCard(
                title=song["title"],
                album=song["album"],
                singer=song["singer"],
                duration=song["duration"],
                progress=0.0,
                width=50,
                height=5,
            )
            cards.append(card)
            live.add(card)

        # Main Loop
        while live.running:
            for key in live.poll():
                if key == "ESC":
                    live.stop()
                    break
                if key == "UP":
                    target_index = max(0.0, target_index - 1.0)
                if key == "DOWN":
                    target_index = min(len(songs_data) - 1.0, target_index + 1.0)

            # ── SMOOTH ANIMATION (LERP) ──
            # Move 15% closer to target each frame
            if abs(smoothed_index - target_index) > 0.01:
                smoothed_index += (target_index - smoothed_index) * 0.15
                update_layout(smoothed_index)
            else:
                smoothed_index = target_index
                update_layout(smoothed_index)

            with live.frame():
                # Dynamic update simulation
                cards[int(target_index)].progress = (math.sin(time.time()) + 1) / 2


if __name__ == "__main__":
    main()
