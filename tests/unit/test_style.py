"""
Unit tests for Style.merge() and ansilookup().

Covers:
  - merge() when base has value and other is None → keeps base
  - merge() when other has value → overrides base
  - merge() boolean attributes use OR semantics
  - merge() returns a new Style object (immutability)
  - merge() chain produces correct cumulative result
  - ansilookup() with no attributes → reset only
  - ansilookup() bold / dim / italic / underline / blink / reverse / hidden / strike
  - ansilookup() fg: low int (<8), bright int (8-15), 256-color int (>=16), RGB tuple
  - ansilookup() bg: same three forms
  - ansilookup() combined fg + bg + bold
  - ansilookup() None style object → empty string
"""

import sys
import os
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from styles import Style, DEFAULT_STYLE
from utils import ansilookup


# ===========================================================================
# Style.merge()
# ===========================================================================


class TestStyleMerge:
    def test_fg_none_in_other_keeps_base_fg(self):
        base = Style(fg=5)
        other = Style(fg=None)
        result = base.merge(other)
        assert result.fg == 5

    def test_fg_in_other_overrides_base(self):
        base = Style(fg=5)
        other = Style(fg=10)
        result = base.merge(other)
        assert result.fg == 10

    def test_bg_none_in_other_keeps_base_bg(self):
        base = Style(bg=2)
        other = Style(bg=None)
        result = base.merge(other)
        assert result.bg == 2

    def test_bg_in_other_overrides_base(self):
        base = Style(bg=2)
        other = Style(bg=7)
        result = base.merge(other)
        assert result.bg == 7

    def test_fg_rgb_tuple_override(self):
        base = Style(fg=15)
        other = Style(fg=(255, 128, 0))
        result = base.merge(other)
        assert result.fg == (255, 128, 0)

    def test_bold_or_semantics_false_false(self):
        base = Style(bold=False)
        other = Style(bold=False)
        assert base.merge(other).bold is False

    def test_bold_or_semantics_true_false(self):
        base = Style(bold=True)
        other = Style(bold=False)
        assert base.merge(other).bold is True

    def test_bold_or_semantics_false_true(self):
        base = Style(bold=False)
        other = Style(bold=True)
        assert base.merge(other).bold is True

    def test_all_boolean_attrs_or_semantics(self):
        attrs = ["bold", "dim", "italic", "underline", "blink", "reverse", "hidden", "strike"]
        for attr in attrs:
            base = Style(**{attr: True})
            other = Style(**{attr: False})
            result = base.merge(other)
            assert getattr(result, attr) is True, f"OR semantics failed for {attr}"

    def test_returns_new_instance(self):
        base = Style(fg=1)
        other = Style(fg=2)
        result = base.merge(other)
        assert result is not base
        assert result is not other

    def test_original_not_mutated(self):
        base = Style(fg=1, bold=False)
        other = Style(fg=2, bold=True)
        base.merge(other)
        assert base.fg == 1
        assert base.bold is False

    def test_chain_merge(self):
        # Simulate parent → child style inheritance chain
        root = Style(fg=15, bold=False)
        mid = Style(fg=None, bold=True)
        leaf = Style(fg=200, bg=1)
        result = root.merge(mid).merge(leaf)
        assert result.fg == 200
        assert result.bg == 1
        assert result.bold is True  # accumulated from mid

    def test_merge_empty_base_with_empty_other(self):
        s1 = Style()
        s2 = Style()
        result = s1.merge(s2)
        assert result.fg is None
        assert result.bg is None
        assert result.bold is False

    def test_merge_from_default_style(self):
        child_style = Style(fg=46)
        result = DEFAULT_STYLE.merge(child_style)
        assert result.fg == 46
        # DEFAULT_STYLE.bg is None, child.bg is None → stays None
        assert result.bg is None


# ===========================================================================
# ansilookup()
# ===========================================================================


class TestAnsiLookup:
    def test_none_returns_empty_string(self):
        assert ansilookup(None) == ""

    def test_style_with_no_attributes_returns_reset(self):
        # A Style with all defaults (no fg, no bg, no attrs)
        s = Style()
        result = ansilookup(s)
        assert result == "\033[0m"

    def test_bold(self):
        result = ansilookup(Style(bold=True))
        assert "1" in result
        assert result.startswith("\033[0m")

    def test_dim(self):
        result = ansilookup(Style(dim=True))
        assert "2" in result

    def test_italic(self):
        result = ansilookup(Style(italic=True))
        assert "3" in result

    def test_underline(self):
        result = ansilookup(Style(underline=True))
        assert "4" in result

    def test_blink(self):
        result = ansilookup(Style(blink=True))
        assert "5" in result

    def test_reverse(self):
        result = ansilookup(Style(reverse=True))
        assert "7" in result

    def test_hidden(self):
        result = ansilookup(Style(hidden=True))
        assert "8" in result

    def test_strike(self):
        result = ansilookup(Style(strike=True))
        assert "9" in result

    # ── fg int forms ────────────────────────────────────────────────────────

    def test_fg_low_int_uses_30_series(self):
        # fg=3 → "33"
        result = ansilookup(Style(fg=3))
        assert "33" in result

    def test_fg_low_int_boundary_zero(self):
        result = ansilookup(Style(fg=0))
        assert "30" in result

    def test_fg_low_int_boundary_seven(self):
        result = ansilookup(Style(fg=7))
        assert "37" in result

    def test_fg_bright_int_uses_90_series(self):
        # fg=8 → "90", fg=15 → "97"
        assert "90" in ansilookup(Style(fg=8))
        assert "97" in ansilookup(Style(fg=15))

    def test_fg_256_color_uses_38_5(self):
        result = ansilookup(Style(fg=200))
        assert "38;5;200" in result

    def test_fg_rgb_tuple_uses_38_2(self):
        result = ansilookup(Style(fg=(255, 128, 64)))
        assert "38;2;255;128;64" in result

    # ── bg int forms ────────────────────────────────────────────────────────

    def test_bg_low_int_uses_40_series(self):
        result = ansilookup(Style(bg=0))
        assert "40" in result

    def test_bg_bright_int_uses_100_series(self):
        result = ansilookup(Style(bg=8))
        assert "100" in result

    def test_bg_256_color_uses_48_5(self):
        result = ansilookup(Style(bg=220))
        assert "48;5;220" in result

    def test_bg_rgb_tuple_uses_48_2(self):
        result = ansilookup(Style(bg=(10, 20, 30)))
        assert "48;2;10;20;30" in result

    # ── combined ────────────────────────────────────────────────────────────

    def test_combined_fg_bg_bold(self):
        result = ansilookup(Style(fg=15, bg=0, bold=True))
        assert "1" in result  # bold
        assert "97" in result  # fg=15 → bright white
        assert "40" in result  # bg=0 → black background

    def test_result_starts_with_reset(self):
        # Any non-trivial style must start with ESC[0m (reset) before the codes
        result = ansilookup(Style(fg=1))
        assert result.startswith("\033[0m\033[")
