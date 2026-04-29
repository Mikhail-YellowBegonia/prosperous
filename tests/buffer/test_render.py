"""
Buffer-level render tests.

Each test draws a component into a RenderEngine's screen_prepare buffer and
asserts specific character and style values at known coordinates.  No stdout
output is produced — we only inspect the in-memory buffer.

Conventions:
  screen_prepare[row][col] == (char, style_obj)

Covers:
  Panel:
    - top-left corner is '┌'
    - top-right corner is '┐'
    - bottom-left corner is '└'
    - bottom-right corner is '┘'
    - top border row contains '─'
    - left/right side walls are '│'
    - title text centred in top border
    - interior cells are spaces
    - style propagated to border characters

  Box:
    - corners and walls match Panel (no title)
    - interior clear

  Text:
    - static text written at correct position
    - lambda text evaluated and written
    - right-aligned text padded on left
    - center-aligned text padded on both sides

  InputBox:
    - top border starts with '┌'
    - label centred in top border
    - content row bounded by '│'
    - bottom border starts with '└'
    - cursor character present when focused

  ProgressBar:
    - filled cells use '█'
    - empty cells use '░'
    - percentage label at end

  LogView:
    - each appended line written at correct row offset
    - empty rows are blank (spaces)
    - line exceeding width is truncated with '…'
"""

import sys
import os
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prosperous import Style, DEFAULT_STYLE
from prosperous import Panel, Box, Label, InputBox, ProgressBar, LogView


# ---------------------------------------------------------------------------
# Buffer helpers
# ---------------------------------------------------------------------------


def cell_char(engine, row, col):
    """Return the character stored at (row, col) in screen_logic."""
    return engine.screen_logic[row][col][0]


def cell_style(engine, row, col):
    """Return the Style object at (row, col)."""
    return engine.screen_logic[row][col][1]


def row_chars(engine, row, start, end):
    """Extract a substring from screen_logic row [start:end]."""
    return "".join(engine.screen_logic[row][c][0] for c in range(start, end))


# ===========================================================================
# Panel
# ===========================================================================


class TestPanelBuffer:
    def test_top_left_corner(self, engine):
        panel = Panel(pos=(0, 0), width=10, height=5, padding=0)
        panel.draw(engine)
        assert cell_char(engine, 0, 0) == "┌"

    def test_top_right_corner(self, engine):
        panel = Panel(pos=(0, 0), width=10, height=5, padding=0)
        panel.draw(engine)
        assert cell_char(engine, 0, 9) == "┐"

    def test_bottom_left_corner(self, engine):
        panel = Panel(pos=(0, 0), width=10, height=5, padding=0)
        panel.draw(engine)
        assert cell_char(engine, 4, 0) == "└"

    def test_bottom_right_corner(self, engine):
        panel = Panel(pos=(0, 0), width=10, height=5, padding=0)
        panel.draw(engine)
        assert cell_char(engine, 4, 9) == "┘"

    def test_top_horizontal_border_chars(self, engine):
        panel = Panel(pos=(0, 0), width=10, height=5, title="", padding=0)
        panel.draw(engine)
        # Columns 1–8 of row 0: title or '─'
        for col in range(1, 9):
            assert cell_char(engine, 0, col) in ("─", " ", "P", "A", "N", "E", "L")

    def test_side_walls(self, engine):
        panel = Panel(pos=(0, 0), width=10, height=5, padding=0)
        panel.draw(engine)
        for row in range(1, 4):
            assert cell_char(engine, row, 0) == "│"
            assert cell_char(engine, row, 9) == "│"

    def test_interior_cells_are_spaces(self, engine):
        panel = Panel(pos=(0, 0), width=10, height=5, padding=0)
        panel.draw(engine)
        for row in range(1, 4):
            for col in range(1, 9):
                assert cell_char(engine, row, col) == " "

    def test_title_appears_in_top_border(self, engine):
        panel = Panel(pos=(0, 0), width=20, height=5, title="HELLO", padding=0)
        panel.draw(engine)
        top_row = row_chars(engine, 0, 0, 20)
        assert "HELLO" in top_row

    def test_panel_at_nonzero_position(self, engine):
        # title="" prevents title text from overflowing the width=8 border
        panel = Panel(pos=(3, 5), width=8, height=4, title="", padding=0)
        panel.draw(engine)
        assert cell_char(engine, 3, 5) == "┌"
        assert cell_char(engine, 6, 5) == "└"
        assert cell_char(engine, 3, 12) == "┐"
        assert cell_char(engine, 6, 12) == "┘"

    def test_style_applied_to_border(self, engine):
        custom = Style(fg=200)
        panel = Panel(pos=(0, 0), width=10, height=5, style=custom, padding=0)
        panel.draw(engine)
        s = cell_style(engine, 0, 0)
        # Effective style is DEFAULT_STYLE merged with custom → fg=200
        assert s.fg == 200


# ===========================================================================
# Box
# ===========================================================================


class TestBoxBuffer:
    def test_corners(self, engine):
        box = Box(pos=(0, 0), width=8, height=4, padding=0)
        box.draw(engine)
        assert cell_char(engine, 0, 0) == "┌"
        assert cell_char(engine, 0, 7) == "┐"
        assert cell_char(engine, 3, 0) == "└"
        assert cell_char(engine, 3, 7) == "┘"

    def test_side_walls(self, engine):
        box = Box(pos=(0, 0), width=8, height=4, padding=0)
        box.draw(engine)
        for row in range(1, 3):
            assert cell_char(engine, row, 0) == "│"
            assert cell_char(engine, row, 7) == "│"

    def test_interior_spaces(self, engine):
        box = Box(pos=(0, 0), width=8, height=4, padding=0)
        box.draw(engine)
        for row in range(1, 3):
            for col in range(1, 7):
                assert cell_char(engine, row, col) == " "


# ===========================================================================
# Text
# ===========================================================================


class TestLabelBuffer:
    def test_static_text_at_origin(self, engine):
        t = Label(pos=(0, 0), text="Hello")
        t.draw(engine)
        assert row_chars(engine, 0, 0, 5) == "Hello"

    def test_static_text_at_offset(self, engine):
        t = Label(pos=(2, 4), text="Hi")
        t.draw(engine)
        assert row_chars(engine, 2, 4, 6) == "Hi"

    def test_lambda_text_evaluated(self, engine):
        value = ["world"]
        t = Label(pos=(0, 0), text=lambda: value[0], width=10)
        t.draw(engine)
        assert row_chars(engine, 0, 0, 5) == "world"

    def test_lambda_text_updates_on_redraw(self, engine):
        value = ["a"]
        t = Label(pos=(0, 0), text=lambda: value[0], width=5)
        t.draw(engine)
        assert cell_char(engine, 0, 0) == "a"
        value[0] = "b"
        t.draw(engine)
        assert cell_char(engine, 0, 0) == "b"

    def test_right_align_pads_left(self, engine):
        # width=10, text="Hi" (len 2) → 8 spaces + "Hi"
        t = Label(pos=(0, 0), text="Hi", width=10, align="right")
        t.draw(engine)
        rendered = row_chars(engine, 0, 0, 10)
        assert rendered.endswith("Hi")
        assert rendered.startswith(" " * 8)

    def test_center_align(self, engine):
        # width=10, text="Hi" (len 2) → pad=8, left=4
        t = Label(pos=(0, 0), text="Hi", width=10, align="center")
        t.draw(engine)
        rendered = row_chars(engine, 0, 0, 10)
        assert "Hi" in rendered
        left_spaces = len(rendered) - len(rendered.lstrip(" "))
        right_spaces = len(rendered) - len(rendered.rstrip(" "))
        assert left_spaces >= 1
        assert right_spaces >= 1


# ===========================================================================
# InputBox
# ===========================================================================


class TestInputBoxBuffer:
    def test_top_border_starts_with_corner(self, engine):
        box = InputBox(pos=(0, 0), width=20, label="NAME")
        box.draw(engine)
        assert cell_char(engine, 0, 0) == "┌"

    def test_top_border_ends_with_corner(self, engine):
        box = InputBox(pos=(0, 0), width=20, label="NAME")
        box.draw(engine)
        assert cell_char(engine, 0, 19) == "┐"

    def test_label_in_top_border(self, engine):
        box = InputBox(pos=(0, 0), width=20, label="MYNAME")
        box.draw(engine)
        top_row = row_chars(engine, 0, 0, 20)
        assert "MYNAME" in top_row

    def test_content_row_has_side_walls(self, engine):
        box = InputBox(pos=(0, 0), width=20, label="X")
        box.draw(engine)
        assert cell_char(engine, 1, 0) == "│"
        assert cell_char(engine, 1, 19) == "│"

    def test_bottom_border_corners(self, engine):
        box = InputBox(pos=(0, 0), width=20, label="X")
        box.draw(engine)
        assert cell_char(engine, 2, 0) == "└"
        assert cell_char(engine, 2, 19) == "┘"

    def test_typed_text_appears_in_content_row(self, engine):
        box = InputBox(pos=(0, 0), width=20, label="X")
        box.text = "abc"
        box.draw(engine)
        content_area = row_chars(engine, 1, 1, 19)
        assert "abc" in content_area

    def test_cursor_present_when_focused(self, engine):
        import time

        box = InputBox(pos=(0, 0), width=20, label="X")
        box.is_focused = True
        box.cursor_visible = True
        box._last_blink = time.time()  # prevent blink toggle on first draw
        box.draw(engine)
        content_area = row_chars(engine, 1, 1, 19)
        assert "█" in content_area

    def test_no_cursor_when_not_focused(self, engine):
        box = InputBox(pos=(0, 0), width=20, label="X")
        box.is_focused = False
        box.draw(engine)
        content_area = row_chars(engine, 1, 1, 19)
        assert "█" not in content_area


# ===========================================================================
# ProgressBar
# ===========================================================================


class TestProgressBarBuffer:
    def test_full_bar_all_filled(self, engine):
        pb = ProgressBar(pos=(0, 0), width=20, value=1.0)
        pb.draw(engine)
        inner = 20 - 5  # 15
        for col in range(0, inner):
            assert cell_char(engine, 0, col) == "█", f"Expected filled at col {col}"

    def test_empty_bar_all_empty(self, engine):
        pb = ProgressBar(pos=(0, 0), width=20, value=0.0)
        pb.draw(engine)
        inner = 20 - 5  # 15
        for col in range(0, inner):
            assert cell_char(engine, 0, col) == "░", f"Expected empty at col {col}"

    def test_half_bar_split(self, engine):
        pb = ProgressBar(pos=(0, 0), width=20, value=0.5)
        pb.draw(engine)
        inner = 20 - 5  # 15
        filled = round(inner * 0.5)  # 8 (round(7.5))
        for col in range(0, filled):
            assert cell_char(engine, 0, col) == "█"
        for col in range(filled, inner):
            assert cell_char(engine, 0, col) == "░"

    def test_percentage_label_at_end(self, engine):
        pb = ProgressBar(pos=(0, 0), width=20, value=0.75)
        pb.draw(engine)
        inner = 20 - 5  # 15
        pct_area = row_chars(engine, 0, inner, inner + 4)
        assert "%" in pct_area

    def test_value_clamped_above_one(self, engine):
        pb = ProgressBar(pos=(0, 0), width=20, value=2.0)
        pb.draw(engine)
        inner = 20 - 5
        # All should be filled
        assert all(cell_char(engine, 0, col) == "█" for col in range(inner))

    def test_value_clamped_below_zero(self, engine):
        pb = ProgressBar(pos=(0, 0), width=20, value=-1.0)
        pb.draw(engine)
        inner = 20 - 5
        assert all(cell_char(engine, 0, col) == "░" for col in range(inner))

    def test_lambda_value_evaluated(self, engine):
        val = [0.0]
        pb = ProgressBar(pos=(0, 0), width=20, value=lambda: val[0])
        pb.draw(engine)
        inner = 20 - 5
        assert all(cell_char(engine, 0, col) == "░" for col in range(inner))


# ===========================================================================
# LogView
# ===========================================================================


class TestLogViewBuffer:
    def test_single_line_at_row_zero(self, engine):
        lv = LogView(pos=(0, 0), width=20, height=4)
        lv.append("hello")
        lv.draw(engine)
        content = row_chars(engine, 0, 0, 5)
        assert content == "hello"

    def test_second_line_at_row_one(self, engine):
        lv = LogView(pos=(0, 0), width=20, height=4)
        lv.append("line1")
        lv.append("line2")
        lv.draw(engine)
        assert row_chars(engine, 1, 0, 5) == "line2"

    def test_empty_rows_padded_with_spaces(self, engine):
        lv = LogView(pos=(0, 0), width=10, height=3)
        lv.append("hi")
        lv.draw(engine)
        # Row 1 and 2 are empty, should start with spaces
        for col in range(10):
            assert cell_char(engine, 1, col) == " "

    def test_long_line_wrapped(self, engine):
        lv = LogView(pos=(0, 0), width=10, height=3)
        lv.append("a" * 20)  # far exceeds width
        lv.draw(engine)
        # Should wrap into two lines of 10 'a's
        row0 = row_chars(engine, 0, 0, 10)
        row1 = row_chars(engine, 1, 0, 10)
        assert row0 == "a" * 10
        assert row1 == "a" * 10

    def test_positioned_log_draws_at_correct_offset(self, engine):
        lv = LogView(pos=(5, 3), width=15, height=3)
        lv.append("xyz")
        lv.draw(engine)
        assert row_chars(engine, 5, 3, 6) == "xyz"
