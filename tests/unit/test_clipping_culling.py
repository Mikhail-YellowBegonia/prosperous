"""
Unit tests for clipping and culling logic.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prosperous import BaseComponent, Box, Panel, Style


class TestLazyAABB:
    def test_dirty_flag_on_init(self):
        c = BaseComponent(pos=(1, 1))
        # Initial state should be dirty
        assert c._needs_update is True
        rect = c.get_abs_rect()
        assert rect == (1, 1, 1, 1)
        assert c._needs_update is False

    def test_dirty_flag_on_pos_change(self):
        c = BaseComponent(pos=(1, 1))
        c.get_abs_rect()  # Clear flag
        c.pos = (2, 2)
        assert c._needs_update is True
        assert c.get_abs_rect() == (2, 2, 1, 1)

    def test_recursive_dirty_flag(self):
        parent = BaseComponent(pos=(10, 10))
        child = BaseComponent(pos=(1, 1))
        parent.add_child(child)

        parent.get_abs_rect()
        child.get_abs_rect()
        assert parent._needs_update is False
        assert child._needs_update is False

        parent.pos = (20, 20)
        assert parent._needs_update is True
        assert child._needs_update is True

        assert child.get_abs_rect() == (21, 21, 1, 1)

    def test_box_size_change_triggers_dirty(self):
        box = Box(width=10, height=10)
        box.get_abs_rect()
        assert box._needs_update is False

        box.width = 20
        assert box._needs_update is True
        assert box.get_abs_rect() == (0, 0, 10, 20)

    def test_box_padding_change_triggers_dirty(self):
        box = Box(width=20, height=10, padding=1)
        child = BaseComponent(pos=(0, 0))
        box.add_child(child)

        assert child.get_abs_rect() == (2, 2, 1, 1) # border(1) + padding(1)
        
        box.padding = 2
        assert child._needs_update is True
        assert child.get_abs_rect() == (3, 3, 1, 1) # border(1) + padding(2)


class TestCulling:
    def test_culling_skips_draw(self):
        engine = MagicMock()
        engine.cli_height = 24
        engine.cli_width = 80
        engine.get_current_clip.return_value = None

        # In viewport
        c1 = BaseComponent(pos=(0, 0), culling=True)
        child1 = BaseComponent()
        child1.draw = MagicMock()
        c1.add_child(child1)

        c1.draw(engine)
        child1.draw.assert_called_once()

        # Outside viewport
        c2 = BaseComponent(pos=(100, 100), culling=True)
        child2 = BaseComponent()
        child2.draw = MagicMock()
        c2.add_child(child2)

        c2.draw(engine)
        child2.draw.assert_not_called()

    def test_culling_respects_current_clip(self):
        engine = MagicMock()
        engine.cli_height = 24
        engine.cli_width = 80
        # Clip to a small area
        engine.get_current_clip.return_value = (10, 10, 5, 5)

        # Inside clip
        c1 = BaseComponent(pos=(11, 11), culling=True)
        child1 = BaseComponent()
        child1.draw = MagicMock()
        c1.add_child(child1)
        c1.draw(engine)
        child1.draw.assert_called_once()

        # Outside clip (but inside screen)
        c2 = BaseComponent(pos=(0, 0), culling=True)
        child2 = BaseComponent()
        child2.draw = MagicMock()
        c2.add_child(child2)
        c2.draw(engine)
        child2.draw.assert_not_called()


class TestClipping:
    def test_clipping_calls_engine_push_pop(self):
        engine = MagicMock()
        engine.get_current_clip.return_value = None

        c = BaseComponent(pos=(2, 3), clipping=True)
        # Mock get_height/width
        c.get_height = lambda: 5
        c.get_width = lambda: 10

        c.draw(engine)

        engine.push_clip.assert_called_once_with(2, 3, 5, 10)
        engine.pop_clip.assert_called_once()

    def test_box_clipping_uses_content_area(self):
        engine = MagicMock()
        engine.get_current_clip.return_value = None

        box = Box(pos=(5, 5), width=20, height=10, padding=1, clipping=True)
        box.draw(engine)

        # Box clipping should be content area: (y+1, x+1, h-2, w-2)
        # ay=5, ax=5 -> content_y=6, content_x=6
        engine.push_clip.assert_called_once_with(6, 6, 8, 18)
