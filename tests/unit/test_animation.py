"""Unit tests for Tween and easing functions."""

import time
import sys
import os
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from animation import Tween, linear, ease_in, ease_out, ease_in_out


# ── Easing functions ──────────────────────────────────────────────────────────


class TestEasingFunctions:
    def test_all_start_at_zero(self):
        for fn in (linear, ease_in, ease_out, ease_in_out):
            assert fn(0.0) == pytest.approx(0.0)

    def test_all_end_at_one(self):
        for fn in (linear, ease_in, ease_out, ease_in_out):
            assert fn(1.0) == pytest.approx(1.0)

    def test_all_stay_in_range(self):
        for fn in (linear, ease_in, ease_out, ease_in_out):
            for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                assert 0.0 <= fn(t) <= 1.0

    def test_linear_is_identity(self):
        assert linear(0.5) == pytest.approx(0.5)

    def test_ease_out_faster_than_linear_at_midpoint(self):
        assert ease_out(0.5) > linear(0.5)

    def test_ease_in_slower_than_linear_at_midpoint(self):
        assert ease_in(0.5) < linear(0.5)

    def test_ease_in_out_symmetric(self):
        assert ease_in_out(0.5) == pytest.approx(0.5)
        assert ease_in_out(0.25) == pytest.approx(1 - ease_in_out(0.75), abs=1e-9)

    def test_custom_easing_accepted(self):
        tw = Tween(0, 10, 1.0, easing=lambda t: t**3)
        assert isinstance(tw, Tween)


# ── Tween ─────────────────────────────────────────────────────────────────────


def _freeze(monkeypatch, tw, offset):
    """Patch time.perf_counter to return tw._t0 + offset."""
    monkeypatch.setattr(time, "perf_counter", lambda: tw._t0 + offset)


class TestTween:
    def test_value_starts_at_start(self, monkeypatch):
        tw = Tween(0.0, 10.0, 1.0)
        _freeze(monkeypatch, tw, 0)
        assert tw.value == pytest.approx(0.0)

    def test_value_ends_at_end(self, monkeypatch):
        tw = Tween(0.0, 10.0, 1.0)
        _freeze(monkeypatch, tw, 999)
        assert tw.value == pytest.approx(10.0)

    def test_progress_clamps_at_one(self, monkeypatch):
        tw = Tween(0.0, 1.0, 0.5)
        _freeze(monkeypatch, tw, 999)
        assert tw.progress == pytest.approx(1.0)

    def test_done_false_before_duration(self, monkeypatch):
        tw = Tween(0.0, 1.0, 1.0)
        _freeze(monkeypatch, tw, 0.1)
        assert not tw.done

    def test_done_true_after_duration(self, monkeypatch):
        tw = Tween(0.0, 1.0, 1.0)
        _freeze(monkeypatch, tw, 2.0)
        assert tw.done

    def test_midpoint_linear(self, monkeypatch):
        tw = Tween(0.0, 10.0, 1.0, easing=linear)
        _freeze(monkeypatch, tw, 0.5)
        assert tw.value == pytest.approx(5.0)

    def test_negative_range(self, monkeypatch):
        tw = Tween(10.0, -5.0, 1.0)
        _freeze(monkeypatch, tw, 999)
        assert tw.value == pytest.approx(-5.0)

    def test_default_easing_is_ease_out(self, monkeypatch):
        tw_default = Tween(0.0, 1.0, 1.0)
        tw_explicit = Tween(0.0, 1.0, 1.0, easing=ease_out)
        _freeze(monkeypatch, tw_default, 0.5)
        _freeze(monkeypatch, tw_explicit, 0.5)
        assert tw_default.value == pytest.approx(tw_explicit.value)

    def test_restart_restores_not_done(self, monkeypatch):
        tw = Tween(0.0, 10.0, 1.0)
        _freeze(monkeypatch, tw, 999)
        assert tw.done
        tw.restart()
        # after restart, _t0 is reset; patch relative to new _t0
        _freeze(monkeypatch, tw, 0.1)
        assert not tw.done

    def test_restart_updates_end(self, monkeypatch):
        tw = Tween(0.0, 5.0, 1.0)
        tw.restart(end=20.0)
        _freeze(monkeypatch, tw, 999)
        assert tw.value == pytest.approx(20.0)
