"""
Unit tests for RenderEngine buffer operations.
Covers swap_buffers pointer swap and clear_prepare acceleration.
"""

import os
import sys
import signal
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from styles import Style, DEFAULT_STYLE, BOX_SINGLE


# ---------------------------------------------------------------------------
# swap_buffers
# ---------------------------------------------------------------------------


class TestSwapBuffers:
    def test_swap_moves_prepare_into_buffer(self, engine):
        """After swap, screen_buffer should contain what was in screen_prepare."""
        sentinel = ("X", Style(fg=1))
        engine.screen_prepare[0][0] = sentinel
        engine.swap_buffers()
        assert engine.screen_buffer[0][0] == sentinel

    def test_swap_is_pointer_exchange(self, engine):
        """swap_buffers must not copy rows — the lists are exchanged by reference."""
        id_prepare_before = [id(row) for row in engine.screen_prepare]
        id_buffer_before = [id(row) for row in engine.screen_buffer]
        engine.swap_buffers()
        id_prepare_after = [id(row) for row in engine.screen_prepare]
        id_buffer_after = [id(row) for row in engine.screen_buffer]
        # Each list previously in prepare is now in buffer, and vice versa
        assert id_prepare_after == id_buffer_before
        assert id_buffer_after == id_prepare_before

    def test_double_swap_restores_state(self, engine):
        """Two swaps must return buffers to their original contents."""
        sentinel = ("Y", Style(fg=2))
        engine.screen_prepare[1][2] = sentinel
        engine.swap_buffers()
        engine.swap_buffers()
        assert engine.screen_prepare[1][2] == sentinel

    def test_swap_under_lock_does_not_deadlock(self, engine):
        """swap_buffers acquires engine.lock; must not deadlock from outside."""
        engine.swap_buffers()  # should complete without blocking


# ---------------------------------------------------------------------------
# clear_prepare
# ---------------------------------------------------------------------------


class TestClearPrepare:
    def test_clears_all_cells_to_blank(self, engine):
        engine.screen_logic[0][0] = ("Z", Style(fg=99))
        engine.clear_prepare()
        assert engine.screen_logic[0][0] == (" ", DEFAULT_STYLE)

    def test_clears_entire_buffer(self, engine):
        for y in range(engine.cli_height):
            for x in range(engine.cli_width):
                engine.screen_logic[y][x] = ("!", Style(fg=1))
        engine.clear_prepare()
        for y in range(engine.cli_height):
            for x in range(engine.cli_width):
                assert engine.screen_logic[y][x] == (" ", DEFAULT_STYLE)

    def test_clear_after_swap_does_not_corrupt_buffer(self, engine):
        """After swap, clear_prepare must not affect screen_buffer."""
        sentinel = ("S", Style(fg=3))
        engine.screen_logic[0][0] = sentinel
        engine.commit_logic()
        engine.swap_buffers()  # sentinel now in screen_buffer
        engine.clear_prepare()  # clears screen_logic
        assert engine.screen_buffer[0][0] == sentinel
        assert engine.screen_logic[0][0] == (" ", DEFAULT_STYLE)


# ---------------------------------------------------------------------------
# commit_logic
# ---------------------------------------------------------------------------


class TestCommitLogic:
    def test_commit_moves_logic_into_prepare(self, engine):
        sentinel = ("C", Style(fg=4))
        engine.screen_logic[0][0] = sentinel
        engine.commit_logic()
        assert engine.screen_prepare[0][0] == sentinel

    def test_commit_is_pointer_exchange(self, engine):
        id_logic_before = [id(row) for row in engine.screen_logic]
        id_prepare_before = [id(row) for row in engine.screen_prepare]
        engine.commit_logic()
        id_logic_after = [id(row) for row in engine.screen_logic]
        id_prepare_after = [id(row) for row in engine.screen_prepare]
        assert id_prepare_after == id_logic_before
        assert id_logic_after == id_prepare_before


# ---------------------------------------------------------------------------
# fill_rect
# ---------------------------------------------------------------------------


class TestFillRect:
    def test_fills_all_cells_with_char(self, engine):
        """fill_rect should write the given char to every cell in the rectangle."""
        custom_style = Style(fg=42)
        engine.fill_rect(0, 0, 3, 4, char="*", style=custom_style)
        for y in range(3):
            for x in range(4):
                char, style = engine.screen_logic[y][x]
                assert char == "*", f"Expected '*' at ({y},{x}), got {char!r}"
                assert style == custom_style

    def test_fills_correct_region_only(self, engine):
        """Cells outside the rectangle must remain untouched (default blank)."""
        engine.fill_rect(1, 2, 2, 3, char="#")
        # Row 0 should be untouched
        assert engine.screen_logic[0][0][0] == " "
        # Inside the rect
        assert engine.screen_logic[1][2][0] == "#"
        assert engine.screen_logic[2][4][0] == "#"
        # One row below the rect
        assert engine.screen_logic[3][2][0] == " "
        # One col to the right of the rect
        assert engine.screen_logic[1][5][0] == " "

    def test_default_char_is_space(self, engine):
        """fill_rect with no char argument should fill with spaces."""
        engine.fill_rect(0, 0, 2, 2)
        for y in range(2):
            for x in range(2):
                assert engine.screen_logic[y][x][0] == " "

    def test_default_style_is_default_style(self, engine):
        """fill_rect with no style argument should use DEFAULT_STYLE."""
        engine.fill_rect(0, 0, 2, 2, char="A")
        for y in range(2):
            for x in range(2):
                assert engine.screen_logic[y][x][1] == DEFAULT_STYLE

    def test_out_of_bounds_does_not_crash(self, engine):
        """fill_rect that extends beyond the buffer should not raise."""
        engine.fill_rect(engine.cli_height - 1, engine.cli_width - 1, 5, 5, char="X")
        # Only the in-bounds corner should be written
        assert engine.screen_logic[engine.cli_height - 1][engine.cli_width - 1][0] == "X"

    def test_negative_origin_does_not_crash(self, engine):
        """fill_rect starting at negative coords should not raise."""
        engine.fill_rect(-1, -1, 3, 3, char="Z")

    def test_zero_height_does_nothing(self, engine):
        """fill_rect with height=0 should write nothing."""
        engine.fill_rect(0, 0, 0, 4, char="Q")
        assert engine.screen_logic[0][0][0] == " "

    def test_zero_width_does_nothing(self, engine):
        """fill_rect with width=0 should write nothing."""
        engine.fill_rect(0, 0, 4, 0, char="Q")
        assert engine.screen_logic[0][0][0] == " "


# ---------------------------------------------------------------------------
# draw_vline
# ---------------------------------------------------------------------------


class TestDrawVline:
    def test_writes_char_to_each_row(self, engine):
        """draw_vline should write the char in column x for each of `length` rows."""
        engine.draw_vline(2, 5, 4, "|")
        for y in range(2, 6):
            assert engine.screen_logic[y][5][0] == "|", f"Expected '|' at row {y}"

    def test_style_applied_to_each_row(self, engine):
        custom_style = Style(fg=7)
        engine.draw_vline(0, 0, 3, "│", style=custom_style)
        for y in range(3):
            assert engine.screen_logic[y][0][1] == custom_style

    def test_default_style_when_none(self, engine):
        engine.draw_vline(0, 0, 2, "│")
        for y in range(2):
            assert engine.screen_logic[y][0][1] == DEFAULT_STYLE

    def test_does_not_write_beyond_length(self, engine):
        """Rows beyond start+length should not be touched."""
        engine.draw_vline(1, 0, 3, "X")
        assert engine.screen_logic[4][0][0] == " "

    def test_zero_length_does_nothing(self, engine):
        """draw_vline with length=0 should not write anything."""
        engine.draw_vline(0, 0, 0, "X")
        assert engine.screen_logic[0][0][0] == " "

    def test_out_of_bounds_does_not_crash(self, engine):
        """draw_vline extending below the buffer should not raise."""
        engine.draw_vline(engine.cli_height - 1, 0, 10, "|")

    def test_column_not_adjacent_to_line_untouched(self, engine):
        """draw_vline at col 3 should not alter col 4."""
        engine.draw_vline(0, 3, 5, "!")
        for y in range(5):
            assert engine.screen_logic[y][4][0] == " "


# ---------------------------------------------------------------------------
# draw_box
# ---------------------------------------------------------------------------


class TestDrawBox:
    def test_top_left_corner(self, engine):
        engine.draw_box(0, 0, 5, 8)
        assert engine.screen_logic[0][0][0] == BOX_SINGLE[0]  # '┌'

    def test_top_right_corner(self, engine):
        engine.draw_box(0, 0, 5, 8)
        assert engine.screen_logic[0][7][0] == BOX_SINGLE[1]  # '┐'

    def test_bottom_left_corner(self, engine):
        engine.draw_box(0, 0, 5, 8)
        assert engine.screen_logic[4][0][0] == BOX_SINGLE[2]  # '└'

    def test_bottom_right_corner(self, engine):
        engine.draw_box(0, 0, 5, 8)
        assert engine.screen_logic[4][7][0] == BOX_SINGLE[3]  # '┘'

    def test_top_horizontal_border(self, engine):
        """Inner cells of the top row should be '─' (BOX_SINGLE[4])."""
        engine.draw_box(0, 0, 5, 8)
        for col in range(1, 7):
            assert engine.screen_logic[0][col][0] == BOX_SINGLE[4], (
                f"Expected top horizontal at col {col}"
            )

    def test_bottom_horizontal_border(self, engine):
        """Inner cells of the bottom row should be '─' (BOX_SINGLE[5])."""
        engine.draw_box(0, 0, 5, 8)
        for col in range(1, 7):
            assert engine.screen_logic[4][col][0] == BOX_SINGLE[5], (
                f"Expected bottom horizontal at col {col}"
            )

    def test_left_vertical_border(self, engine):
        """Interior rows of column 0 should be '│' (BOX_SINGLE[6])."""
        engine.draw_box(0, 0, 5, 8)
        for row in range(1, 4):
            assert engine.screen_logic[row][0][0] == BOX_SINGLE[6], (
                f"Expected left vertical at row {row}"
            )

    def test_right_vertical_border(self, engine):
        """Interior rows of column width-1 should be '│' (BOX_SINGLE[7])."""
        engine.draw_box(0, 0, 5, 8)
        for row in range(1, 4):
            assert engine.screen_logic[row][7][0] == BOX_SINGLE[7], (
                f"Expected right vertical at row {row}"
            )

    def test_interior_not_written_by_draw_box(self, engine):
        """draw_box only draws the outline; interior cells should stay blank."""
        engine.draw_box(0, 0, 5, 8)
        for row in range(1, 4):
            for col in range(1, 7):
                assert engine.screen_logic[row][col][0] == " ", (
                    f"Interior cell ({row},{col}) should be space"
                )

    def test_custom_border_characters(self, engine):
        """draw_box with a custom border string should use those characters."""
        custom_border = "ABCD--||"
        engine.draw_box(0, 0, 4, 6, border=custom_border)
        assert engine.screen_logic[0][0][0] == "A"   # TL
        assert engine.screen_logic[0][5][0] == "B"   # TR
        assert engine.screen_logic[3][0][0] == "C"   # BL
        assert engine.screen_logic[3][5][0] == "D"   # BR
        for col in range(1, 5):
            assert engine.screen_logic[0][col][0] == "-"
        for row in range(1, 3):
            assert engine.screen_logic[row][0][0] == "|"
            assert engine.screen_logic[row][5][0] == "|"

    def test_style_applied_to_all_border_cells(self, engine):
        custom_style = Style(fg=55)
        engine.draw_box(0, 0, 4, 6, style=custom_style)
        # Check corners
        assert engine.screen_logic[0][0][1] == custom_style
        assert engine.screen_logic[0][5][1] == custom_style
        assert engine.screen_logic[3][0][1] == custom_style
        assert engine.screen_logic[3][5][1] == custom_style
        # Check vertical sides
        for row in range(1, 3):
            assert engine.screen_logic[row][0][1] == custom_style
            assert engine.screen_logic[row][5][1] == custom_style

    def test_height_2_width_2_boundary(self, engine):
        """draw_box with height=2, width=2 produces only corners, no inner segments."""
        engine.draw_box(0, 0, 2, 2)
        assert engine.screen_logic[0][0][0] == BOX_SINGLE[0]  # TL
        assert engine.screen_logic[0][1][0] == BOX_SINGLE[1]  # TR
        assert engine.screen_logic[1][0][0] == BOX_SINGLE[2]  # BL
        assert engine.screen_logic[1][1][0] == BOX_SINGLE[3]  # BR

    def test_positioned_box(self, engine):
        """draw_box at a non-zero origin positions corners correctly."""
        engine.draw_box(3, 5, 4, 6)
        assert engine.screen_logic[3][5][0] == BOX_SINGLE[0]   # TL
        assert engine.screen_logic[3][10][0] == BOX_SINGLE[1]  # TR
        assert engine.screen_logic[6][5][0] == BOX_SINGLE[2]   # BL
        assert engine.screen_logic[6][10][0] == BOX_SINGLE[3]  # BR

    def test_default_border_is_box_single(self, engine):
        """When no border is specified, BOX_SINGLE characters should appear."""
        engine.draw_box(0, 0, 3, 5)
        assert engine.screen_logic[0][0][0] == "┌"
        assert engine.screen_logic[0][4][0] == "┐"
        assert engine.screen_logic[2][0][0] == "└"
        assert engine.screen_logic[2][4][0] == "┘"
