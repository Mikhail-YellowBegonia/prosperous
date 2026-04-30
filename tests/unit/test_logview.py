"""
Unit tests for the new LogView and wrap_segments logic.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prosperous import LogView, Style, DEFAULT_STYLE
from prosperous.markup import wrap_segments


class TestWrapSegments:
    def test_basic_wrap(self):
        # "Hello World" (11 chars) with width 5
        style = Style(fg=1)
        segments = [("Hello World", style)]
        lines = wrap_segments(segments, 5)

        # Should be: "Hello", " Worl", "d"
        assert len(lines) == 3
        assert lines[0] == [("Hello", style)]
        assert lines[1] == [(" Worl", style)]
        assert lines[2] == [("d", style)]

    def test_cjk_wrap(self):
        # "你好世界" (8 visual width) with width 5
        # Line 1: "你好" (4) fits, "世" (2) would make it 6 > 5
        # Line 2: "世界" (4) fits
        style = Style(fg=2)
        segments = [("你好世界", style)]
        lines = wrap_segments(segments, 5)

        assert len(lines) == 2
        assert lines[0] == [("你好", style)]
        assert lines[1] == [("世界", style)]

    def test_cjk_wrap_narrow(self):
        # width 3, "你好世界" (8)
        # Line 1: "你" (2), "好" (2) > 3
        # Line 2: "好" (2)
        # ...
        style = Style(fg=2)
        segments = [("你好世界", style)]
        lines = wrap_segments(segments, 3)
        assert len(lines) == 4
        assert lines[0] == [("你", style)]
        assert lines[1] == [("好", style)]
        assert lines[2] == [("世", style)]
        assert lines[3] == [("界", style)]

    def test_mixed_wrap_and_style_preservation(self):
        s1 = Style(fg=1)
        s2 = Style(fg=2)
        segments = [("ABC", s1), ("DEF", s2)]  # Total 6
        lines = wrap_segments(segments, 4)

        # Line 1: "ABC" (3) + "D" (1) = 4
        # Line 2: "EF" (2)
        assert len(lines) == 2
        assert lines[0] == [("ABC", s1), ("D", s2)]
        assert lines[1] == [("EF", s2)]


class TestLogView:
    def test_append_and_auto_scroll(self):
        log = LogView(width=10, height=3, auto_scroll=True)
        log.append("Line 1")
        log.append("Line 2")
        log.append("Line 3")

        assert len(log._buffer) == 3
        assert log.scroll_offset == 0

        log.append("Line 4")
        assert len(log._buffer) == 4
        # Height is 3, buffer is 4 -> offset should be 1 to show 2,3,4
        assert log.scroll_offset == 1

    def test_markup_support(self):
        log = LogView(width=20, height=5, markup=True)
        log.append("<red>Red Text</>")

        line = log._buffer[0]
        assert len(line) == 1
        assert line[0][0] == "Red Text"
        assert line[0][1].fg is not None  # Specific color check depends on theme/parser

    def test_manual_scroll_disables_auto(self):
        log = LogView(width=10, height=2, auto_scroll=True)
        for i in range(5):
            log.append(f"L{i}")

        assert log.auto_scroll is True
        assert log.scroll_offset == 3  # L3, L4 visible

        # Scroll up
        log.scroll(-1)
        assert log.scroll_offset == 2
        assert log.auto_scroll is False

        # Add new line while auto_scroll is False
        log.append("New")
        assert log.scroll_offset == 2  # Should NOT move

        # Scroll to bottom
        log.scroll(2)
        assert log.scroll_offset == 4  # L4, New visible
        assert log.auto_scroll is True

    def test_max_lines_limit(self):
        log = LogView(width=10, height=5, max_lines=10)
        for i in range(15):
            log.append(str(i))

        assert len(log._buffer) == 10
        assert log._buffer[0] == [("5", DEFAULT_STYLE)]
        assert log._buffer[-1] == [("14", DEFAULT_STYLE)]
