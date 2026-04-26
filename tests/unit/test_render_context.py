"""
Unit tests for _RenderContext — the incremental ANSI state machine.

Each test starts from a known context state and asserts that diff()
produces the minimal correct escape sequence to reach the desired style.
"""

import os
import sys
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from styles import Style
from engine import _RenderContext


def ctx():
    return _RenderContext()


# ---------------------------------------------------------------------------
# No-op cases
# ---------------------------------------------------------------------------


class TestNoChange:
    def test_same_default_style_emits_nothing(self):
        c = ctx()
        assert c.diff(Style()) == ""

    def test_same_fg_emits_nothing(self):
        c = ctx()
        c.diff(Style(fg=46))
        assert c.diff(Style(fg=46)) == ""

    def test_same_complex_style_emits_nothing(self):
        c = ctx()
        s = Style(fg=200, bg=10, bold=True, italic=True)
        c.diff(s)
        assert c.diff(s) == ""


# ---------------------------------------------------------------------------
# fg / bg changes
# ---------------------------------------------------------------------------


class TestColorChanges:
    def test_fg_256_color(self):
        c = ctx()
        result = c.diff(Style(fg=46))
        assert "38;5;46" in result

    def test_fg_rgb(self):
        c = ctx()
        result = c.diff(Style(fg=(255, 128, 0)))
        assert "38;2;255;128;0" in result

    def test_fg_low_int(self):
        c = ctx()
        result = c.diff(Style(fg=2))
        assert "32" in result  # 30 + 2

    def test_fg_bright_int(self):
        c = ctx()
        result = c.diff(Style(fg=9))  # bright red
        assert "91" in result  # 90 + (9-8)

    def test_bg_256_color(self):
        c = ctx()
        result = c.diff(Style(bg=196))
        assert "48;5;196" in result

    def test_fg_cleared_sends_39(self):
        c = ctx()
        c.diff(Style(fg=46))
        result = c.diff(Style())  # fg=None
        assert "39" in result

    def test_bg_cleared_sends_49(self):
        c = ctx()
        c.diff(Style(bg=10))
        result = c.diff(Style())  # bg=None
        assert "49" in result

    def test_only_fg_change_no_reset(self):
        """Changing only fg must not send a full reset code."""
        c = ctx()
        c.diff(Style(fg=1))
        result = c.diff(Style(fg=2))
        assert "\033[0m" not in result
        assert result != ""


# ---------------------------------------------------------------------------
# Boolean attribute changes
# ---------------------------------------------------------------------------


class TestAttrChanges:
    def test_bold_on(self):
        c = ctx()
        assert "1" in c.diff(Style(bold=True))

    def test_italic_on(self):
        c = ctx()
        assert "3" in c.diff(Style(italic=True))

    def test_bold_off_sends_22(self):
        c = ctx()
        c.diff(Style(bold=True))
        result = c.diff(Style())
        assert "22" in result

    def test_dim_off_sends_22(self):
        c = ctx()
        c.diff(Style(dim=True))
        result = c.diff(Style())
        assert "22" in result

    def test_italic_off_sends_23(self):
        c = ctx()
        c.diff(Style(italic=True))
        result = c.diff(Style())
        assert "23" in result

    def test_underline_off_sends_24(self):
        c = ctx()
        c.diff(Style(underline=True))
        result = c.diff(Style())
        assert "24" in result

    def test_bold_off_dim_stays_on(self):
        """Turning off bold (22) must not clear dim if dim should remain."""
        c = ctx()
        c.diff(Style(bold=True, dim=True))
        result = c.diff(Style(dim=True))  # bold off, dim stays
        # 22 turns off both; then 2 re-enables dim
        assert "22" in result
        assert "2" in result

    def test_dim_off_bold_stays_on(self):
        """Turning off dim (22) must not clear bold if bold should remain."""
        c = ctx()
        c.diff(Style(bold=True, dim=True))
        result = c.diff(Style(bold=True))  # dim off, bold stays
        assert "22" in result
        assert "1" in result


# ---------------------------------------------------------------------------
# State tracking
# ---------------------------------------------------------------------------


class TestStateTracking:
    def test_context_tracks_fg(self):
        c = ctx()
        c.diff(Style(fg=100))
        assert c.fg == 100

    def test_context_tracks_bg(self):
        c = ctx()
        c.diff(Style(bg=50))
        assert c.bg == 50

    def test_context_tracks_bold(self):
        c = ctx()
        c.diff(Style(bold=True))
        assert c.bold is True

    def test_reset_clears_all(self):
        c = ctx()
        c.diff(Style(fg=1, bold=True))
        c.reset()
        assert c.fg is None
        assert c.bold is False

    def test_incremental_sequence_shorter_than_reset(self):
        """Single color change should not include reset code."""
        c = ctx()
        c.diff(Style(fg=1, bold=True))
        # Change only fg, keep bold
        result = c.diff(Style(fg=2, bold=True))
        assert "\033[0m" not in result
