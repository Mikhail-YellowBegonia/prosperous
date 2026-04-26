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

from styles import Style, DEFAULT_STYLE


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
        engine.screen_prepare[0][0] = ("Z", Style(fg=99))
        engine.clear_prepare()
        assert engine.screen_prepare[0][0] == (" ", DEFAULT_STYLE)

    def test_clears_entire_buffer(self, engine):
        for y in range(engine.cli_height):
            for x in range(engine.cli_width):
                engine.screen_prepare[y][x] = ("!", Style(fg=1))
        engine.clear_prepare()
        for y in range(engine.cli_height):
            for x in range(engine.cli_width):
                assert engine.screen_prepare[y][x] == (" ", DEFAULT_STYLE)

    def test_clear_after_swap_does_not_corrupt_buffer(self, engine):
        """After swap, clear_prepare must not affect screen_buffer."""
        sentinel = ("S", Style(fg=3))
        engine.screen_prepare[0][0] = sentinel
        engine.swap_buffers()  # sentinel now in screen_buffer
        engine.clear_prepare()  # clears screen_prepare (formerly screen_buffer)
        assert engine.screen_buffer[0][0] == sentinel
        assert engine.screen_prepare[0][0] == (" ", DEFAULT_STYLE)
