"""
Unit tests for ScrollBox and coordinate translation.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prosperous import ScrollBox, BaseComponent, VStack, FocusManager


class TestScrollBox:
    def test_scroll_offset_affects_child_abs_pos(self):
        # ScrollBox at (0,0), padding 0, border 1
        # Content origin should be (1, 1)
        sb = ScrollBox(pos=(0, 0), width=10, height=10, padding=0)
        # Give child enough height (20) to allow scrolling
        child = BaseComponent(pos=(0, 0))
        child.get_height = lambda: 20
        sb.add_child(child)

        # Initial abs pos (no scroll)
        assert child.get_absolute_pos() == (1, 1)

        # Scroll down by 5. Content height is 20, viewport is 8. Max scroll is 12.
        sb.scroll_y = 5
        # Child abs pos should move UP relative to screen: 1 - 5 = -4
        assert child.get_absolute_pos() == (-4, 1)

        # Scroll right by 2. Content width is 1. Viewport width is 8. Max scroll is 0.
        # To test x-scroll, we need a wide child.
        child.get_width = lambda: 30
        sb.scroll_x = 2
        assert child.get_absolute_pos() == (-4, -1)

    def test_dirty_propagation_on_scroll(self):
        sb = ScrollBox(pos=(0, 0), width=10, height=10)
        child = BaseComponent(pos=(0, 0))
        child.get_height = lambda: 50
        sb.add_child(child)

        child.get_abs_rect()  # Clear flag
        assert child._needs_update is False

        sb.scroll_y = 10
        # Changing scroll should mark child as dirty
        assert child._needs_update is True

    def test_nested_layout_scrolling(self):
        # ScrollBox -> VStack -> [C1(h=10), C2(h=10)]
        sb = ScrollBox(pos=(0, 0), width=20, height=5, padding=0)
        vs = VStack(pos=(0, 0))
        c1 = BaseComponent()
        c1.get_height = lambda: 10
        c2 = BaseComponent()
        c2.get_height = lambda: 10

        vs.add_child(c1)
        vs.add_child(c2)
        sb.add_child(vs)

        # No scroll
        # content_origin = (1, 1)
        # vs abs_pos = (1, 1)
        # c1 abs_pos = (1, 1)
        # c2 abs_pos = (1 + 10, 1) = (11, 1)
        assert c1.get_absolute_pos() == (1, 1)
        assert c2.get_absolute_pos() == (11, 1)

        # Scroll down by 2. Total content height is 20, viewport is 3.
        sb.scroll_y = 2
        # c1 should move to (1-2, 1) = (-1, 1)
        # c2 should move to (11-2, 1) = (9, 1)
        assert c1.get_absolute_pos() == (-1, 1)
        assert c2.get_absolute_pos() == (9, 1)


class TestScrollIntoView:
    """ScrollBox.scroll_into_view 和 FocusManager 跟随滚动的集成测试。"""

    def _make_focusable(self, height=1):
        c = BaseComponent()
        c.focusable = True
        c.get_height = lambda: height
        c.get_width = lambda: 5
        return c

    @staticmethod
    def _settle(sb, max_steps=200, dt=0.05):
        """推进动画直到完成或超时。"""
        for _ in range(max_steps):
            sb.update(dt)
            if sb._scroll_anim_y is None and sb._scroll_anim_x is None:
                break

    def test_scroll_into_view_scrolls_down_when_below(self):
        # ScrollBox height=5, padding=0 → viewport_h = 3 (border 1 each side)
        # content_origin at screen row 1
        sb = ScrollBox(pos=(0, 0), width=10, height=5, padding=0)
        vs = VStack()
        # 4 children, each height=1, VStack total height=4
        items = [self._make_focusable() for _ in range(4)]
        for item in items:
            vs.add_child(item)
        sb.add_child(vs)

        # item[3] is at content_y=3, viewport is [0, 2] → below viewport
        sb.scroll_into_view(items[3])
        self._settle(sb)
        # Should scroll so item[3] bottom (4) fits: scroll_y = 4 - 3 = 1
        assert sb.scroll_y == 1

    def test_scroll_into_view_scrolls_up_when_above(self):
        sb = ScrollBox(pos=(0, 0), width=10, height=5, padding=0)
        vs = VStack()
        items = [self._make_focusable() for _ in range(6)]
        for item in items:
            vs.add_child(item)
        sb.add_child(vs)

        # Start scrolled to bottom
        sb.scroll_y = 3  # items[3..5] visible

        # scroll_into_view item[0] → should scroll up to 0
        sb.scroll_into_view(items[0])
        self._settle(sb)
        assert sb.scroll_y == 0

    def test_scroll_into_view_noop_when_already_visible(self):
        sb = ScrollBox(pos=(0, 0), width=10, height=5, padding=0)
        vs = VStack()
        items = [self._make_focusable() for _ in range(6)]
        for item in items:
            vs.add_child(item)
        sb.add_child(vs)
        sb.scroll_y = 1  # items[1..3] visible

        # item[2] is at content_y=2, within [1, 3] → no change，不应创建动画
        sb.scroll_into_view(items[2])
        assert sb._scroll_anim_y is None
        assert sb.scroll_y == 1

    def test_focus_manager_triggers_scroll_on_move(self):
        """move_focus 时 FocusManager 自动触发 scroll_into_view。"""
        sb = ScrollBox(pos=(0, 0), width=10, height=5, padding=0)
        vs = VStack()
        items = [self._make_focusable() for _ in range(4)]
        for item in items:
            vs.add_child(item)
        sb.add_child(vs)

        fm = FocusManager()
        for item in items:
            fm.add_component(item)

        # Initial scroll at 0, item[0] focused. Move to item[3].
        fm.move_focus("DOWN")
        fm.move_focus("DOWN")
        fm.move_focus("DOWN")

        assert fm.get_focused() is items[3]
        # 动画已被触发（但尚未推进），验证目标方向正确
        assert sb._scroll_anim_y is not None
        self._settle(sb)
        assert sb.scroll_y > 0
