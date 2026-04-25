"""
Unit tests for coordinate and layout calculations.

Covers:
  - BaseComponent.get_absolute_pos() for root and nested components
  - BaseComponent.get_child_origin() default behaviour
  - Panel.get_child_origin() — border + padding offset
  - Box.get_child_origin() — border + padding offset
  - VStack: get_child_origin() row accumulation, gap, align, reverse
  - VStack: get_height() / get_width()
  - HStack: get_child_origin() col accumulation, gap, align, reverse
  - HStack: get_height() / get_width()
  - pos offset is additive on top of container origin
  - Edge cases: empty containers, single child, zero-gap
"""
import sys
import os
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from components import BaseComponent, Panel, Box, VStack, HStack, Text, InputBox, Button, LogView


# ---------------------------------------------------------------------------
# Helper: minimal concrete BaseComponent (get_height/get_width overridden)
# ---------------------------------------------------------------------------

def make_block(pos=(0, 0), height=2, width=4):
    """Return a plain BaseComponent that reports a fixed height/width."""
    c = BaseComponent(pos=pos)
    c.get_height = lambda: height
    c.get_width = lambda: width
    return c


# ===========================================================================
# 1.  BaseComponent — absolute position
# ===========================================================================

class TestGetAbsolutePos:
    def test_root_component_returns_own_pos(self):
        c = BaseComponent(pos=(3, 5))
        assert c.get_absolute_pos() == (3, 5)

    def test_root_component_origin(self):
        c = BaseComponent(pos=(0, 0))
        assert c.get_absolute_pos() == (0, 0)

    def test_child_of_plain_parent_adds_parent_pos(self):
        parent = BaseComponent(pos=(2, 3))
        child = BaseComponent(pos=(1, 1))
        parent.add_child(child)
        # parent.get_child_origin() == parent.get_absolute_pos() == (2, 3)
        # child absolute = (2+1, 3+1) = (3, 4)
        assert child.get_absolute_pos() == (3, 4)

    def test_three_level_nesting(self):
        root = BaseComponent(pos=(1, 2))
        mid = BaseComponent(pos=(0, 1))
        leaf = BaseComponent(pos=(1, 0))
        root.add_child(mid)
        mid.add_child(leaf)
        # root abs = (1,2); mid origin = root.abs = (1,2); mid abs = (1,3)
        # leaf origin = mid.abs = (1,3); leaf abs = (2,3)
        assert leaf.get_absolute_pos() == (2, 3)

    def test_pos_zero_zero_child_lands_on_parent(self):
        parent = BaseComponent(pos=(5, 7))
        child = BaseComponent(pos=(0, 0))
        parent.add_child(child)
        assert child.get_absolute_pos() == (5, 7)


# ===========================================================================
# 2.  Panel — child origin includes border + padding
# ===========================================================================

class TestPanelChildOrigin:
    def test_default_padding_is_1_from_theme(self):
        # DEFAULT_THEME["Panel"]["padding"] == 1 → offset = 1 (border) + 1 (padding) = 2
        panel = Panel(pos=(0, 0), width=20, height=10)
        child = BaseComponent(pos=(0, 0))
        panel.add_child(child)
        # offset = 1 (border) + panel.padding (1 by default from theme)
        expected_offset = 1 + panel.padding
        assert child.get_absolute_pos() == (expected_offset, expected_offset)

    def test_explicit_padding_zero(self):
        panel = Panel(pos=(0, 0), width=20, height=10, padding=0)
        child = BaseComponent(pos=(0, 0))
        panel.add_child(child)
        # offset = 1 (border) + 0 = 1
        assert child.get_absolute_pos() == (1, 1)

    def test_explicit_padding_two(self):
        panel = Panel(pos=(0, 0), width=20, height=10, padding=2)
        child = BaseComponent(pos=(0, 0))
        panel.add_child(child)
        assert child.get_absolute_pos() == (3, 3)

    def test_panel_at_nonzero_pos_with_child_offset(self):
        panel = Panel(pos=(3, 5), width=20, height=10, padding=0)
        child = BaseComponent(pos=(1, 2))
        panel.add_child(child)
        # panel abs = (3, 5); child_origin = (3+1, 5+1) = (4, 6); child abs = (5, 8)
        assert child.get_absolute_pos() == (5, 8)

    def test_panel_height_and_width(self):
        panel = Panel(pos=(0, 0), width=30, height=8)
        assert panel.get_height() == 8
        assert panel.get_width() == 30


# ===========================================================================
# 3.  Box — child origin includes border + padding
# ===========================================================================

class TestBoxChildOrigin:
    def test_padding_zero_offset_is_one(self):
        box = Box(pos=(0, 0), width=10, height=5, padding=0)
        child = BaseComponent(pos=(0, 0))
        box.add_child(child)
        assert child.get_absolute_pos() == (1, 1)

    def test_padding_two_offset_is_three(self):
        box = Box(pos=(0, 0), width=10, height=5, padding=2)
        child = BaseComponent(pos=(0, 0))
        box.add_child(child)
        assert child.get_absolute_pos() == (3, 3)

    def test_box_at_nonzero_pos(self):
        box = Box(pos=(4, 6), width=10, height=5, padding=0)
        child = BaseComponent(pos=(0, 0))
        box.add_child(child)
        # box abs = (4,6); origin = (4+1, 6+1) = (5, 7)
        assert child.get_absolute_pos() == (5, 7)

    def test_box_get_height_width(self):
        box = Box(pos=(0, 0), width=15, height=7)
        assert box.get_height() == 7
        assert box.get_width() == 15


# ===========================================================================
# 4.  VStack — layout math
# ===========================================================================

class TestVStack:
    def test_single_child_at_top(self):
        stack = VStack(pos=(0, 0), gap=0)
        c = make_block(pos=(0, 0), height=3, width=5)
        stack.add_child(c)
        assert c.get_absolute_pos() == (0, 0)

    def test_two_children_stacked_without_gap(self):
        stack = VStack(pos=(0, 0), gap=0)
        c1 = make_block(pos=(0, 0), height=3, width=5)
        c2 = make_block(pos=(0, 0), height=2, width=5)
        stack.add_child(c1)
        stack.add_child(c2)
        assert c1.get_absolute_pos() == (0, 0)
        assert c2.get_absolute_pos() == (3, 0)  # after c1's height=3

    def test_two_children_stacked_with_gap(self):
        stack = VStack(pos=(0, 0), gap=2)
        c1 = make_block(pos=(0, 0), height=3, width=5)
        c2 = make_block(pos=(0, 0), height=2, width=5)
        stack.add_child(c1)
        stack.add_child(c2)
        assert c2.get_absolute_pos() == (5, 0)  # 3 + 2 gap

    def test_three_children_gap(self):
        stack = VStack(pos=(0, 0), gap=1)
        c1 = make_block(pos=(0, 0), height=2, width=4)
        c2 = make_block(pos=(0, 0), height=3, width=4)
        c3 = make_block(pos=(0, 0), height=1, width=4)
        stack.add_child(c1)
        stack.add_child(c2)
        stack.add_child(c3)
        assert c1.get_absolute_pos() == (0, 0)
        assert c2.get_absolute_pos() == (3, 0)   # 2 + 1
        assert c3.get_absolute_pos() == (7, 0)   # 2 + 1 + 3 + 1

    def test_child_pos_offset_is_additive(self):
        stack = VStack(pos=(0, 0), gap=0)
        c1 = make_block(pos=(0, 0), height=3, width=5)
        c2 = make_block(pos=(1, 2), height=2, width=5)  # pos offset
        stack.add_child(c1)
        stack.add_child(c2)
        # c2 origin = (3, 0); absolute = (3+1, 0+2) = (4, 2)
        assert c2.get_absolute_pos() == (4, 2)

    def test_stack_at_nonzero_pos(self):
        stack = VStack(pos=(5, 10), gap=0)
        c1 = make_block(pos=(0, 0), height=2, width=4)
        c2 = make_block(pos=(0, 0), height=2, width=4)
        stack.add_child(c1)
        stack.add_child(c2)
        assert c1.get_absolute_pos() == (5, 10)
        assert c2.get_absolute_pos() == (7, 10)

    def test_get_height_no_children(self):
        stack = VStack(pos=(0, 0))
        assert stack.get_height() == 0

    def test_get_height_with_children_and_gap(self):
        stack = VStack(pos=(0, 0), gap=1)
        stack.add_child(make_block(height=3, width=4))
        stack.add_child(make_block(height=2, width=4))
        # 3 + 1 + 2 = 6
        assert stack.get_height() == 6

    def test_get_width_is_max_child_width(self):
        stack = VStack(pos=(0, 0))
        stack.add_child(make_block(height=1, width=10))
        stack.add_child(make_block(height=1, width=6))
        assert stack.get_width() == 10

    def test_get_width_no_children(self):
        stack = VStack(pos=(0, 0))
        assert stack.get_width() == 0

    def test_align_right(self):
        stack = VStack(pos=(0, 0), align="right")
        c_wide = make_block(pos=(0, 0), height=1, width=10)
        c_narrow = make_block(pos=(0, 0), height=1, width=4)
        stack.add_child(c_wide)
        stack.add_child(c_narrow)
        # max_w=10; c_narrow col_offset = 10 - 4 = 6
        assert c_wide.get_absolute_pos() == (0, 0)
        assert c_narrow.get_absolute_pos() == (1, 6)

    def test_align_center(self):
        stack = VStack(pos=(0, 0), align="center")
        c_wide = make_block(pos=(0, 0), height=1, width=10)
        c_narrow = make_block(pos=(0, 0), height=1, width=4)
        stack.add_child(c_wide)
        stack.add_child(c_narrow)
        # max_w=10; col_offset = (10 - 4) // 2 = 3
        assert c_narrow.get_absolute_pos() == (1, 3)

    def test_reverse_order(self):
        stack = VStack(pos=(0, 0), gap=0, reverse=True)
        c1 = make_block(pos=(0, 0), height=2, width=4)
        c2 = make_block(pos=(0, 0), height=3, width=4)
        stack.add_child(c1)
        stack.add_child(c2)
        # ordered = [c2, c1]; c2 at row 0, c1 at row 3
        assert c2.get_absolute_pos() == (0, 0)
        assert c1.get_absolute_pos() == (3, 0)


# ===========================================================================
# 5.  HStack — layout math
# ===========================================================================

class TestHStack:
    def test_single_child_at_left(self):
        stack = HStack(pos=(0, 0), gap=0)
        c = make_block(pos=(0, 0), height=2, width=5)
        stack.add_child(c)
        assert c.get_absolute_pos() == (0, 0)

    def test_two_children_side_by_side_no_gap(self):
        stack = HStack(pos=(0, 0), gap=0)
        c1 = make_block(pos=(0, 0), height=2, width=5)
        c2 = make_block(pos=(0, 0), height=2, width=3)
        stack.add_child(c1)
        stack.add_child(c2)
        assert c1.get_absolute_pos() == (0, 0)
        assert c2.get_absolute_pos() == (0, 5)

    def test_two_children_with_gap(self):
        stack = HStack(pos=(0, 0), gap=3)
        c1 = make_block(pos=(0, 0), height=2, width=5)
        c2 = make_block(pos=(0, 0), height=2, width=3)
        stack.add_child(c1)
        stack.add_child(c2)
        assert c2.get_absolute_pos() == (0, 8)  # 5 + 3

    def test_three_children_gap(self):
        stack = HStack(pos=(0, 0), gap=2)
        c1 = make_block(pos=(0, 0), height=1, width=4)
        c2 = make_block(pos=(0, 0), height=1, width=6)
        c3 = make_block(pos=(0, 0), height=1, width=3)
        stack.add_child(c1)
        stack.add_child(c2)
        stack.add_child(c3)
        assert c1.get_absolute_pos() == (0, 0)
        assert c2.get_absolute_pos() == (0, 6)   # 4 + 2
        assert c3.get_absolute_pos() == (0, 14)  # 4 + 2 + 6 + 2

    def test_child_pos_offset_additive(self):
        stack = HStack(pos=(0, 0), gap=0)
        c1 = make_block(pos=(0, 0), height=2, width=5)
        c2 = make_block(pos=(1, 2), height=2, width=3)
        stack.add_child(c1)
        stack.add_child(c2)
        # c2 origin = (0, 5); absolute = (0+1, 5+2) = (1, 7)
        assert c2.get_absolute_pos() == (1, 7)

    def test_stack_at_nonzero_pos(self):
        stack = HStack(pos=(4, 10), gap=0)
        c1 = make_block(pos=(0, 0), height=1, width=5)
        c2 = make_block(pos=(0, 0), height=1, width=5)
        stack.add_child(c1)
        stack.add_child(c2)
        assert c1.get_absolute_pos() == (4, 10)
        assert c2.get_absolute_pos() == (4, 15)

    def test_get_height_is_max_child_height(self):
        stack = HStack(pos=(0, 0))
        stack.add_child(make_block(height=5, width=4))
        stack.add_child(make_block(height=3, width=4))
        assert stack.get_height() == 5

    def test_get_width_no_children(self):
        stack = HStack(pos=(0, 0))
        assert stack.get_width() == 0

    def test_get_width_with_gap(self):
        stack = HStack(pos=(0, 0), gap=2)
        stack.add_child(make_block(height=1, width=5))
        stack.add_child(make_block(height=1, width=6))
        assert stack.get_width() == 13  # 5 + 2 + 6

    def test_align_bottom(self):
        stack = HStack(pos=(0, 0), align="bottom")
        c_tall = make_block(pos=(0, 0), height=5, width=4)
        c_short = make_block(pos=(0, 0), height=2, width=4)
        stack.add_child(c_tall)
        stack.add_child(c_short)
        # max_h=5; c_short row_offset = 5 - 2 = 3
        assert c_tall.get_absolute_pos() == (0, 0)
        assert c_short.get_absolute_pos() == (3, 4)

    def test_align_center(self):
        stack = HStack(pos=(0, 0), align="center")
        c_tall = make_block(pos=(0, 0), height=6, width=4)
        c_short = make_block(pos=(0, 0), height=2, width=4)
        stack.add_child(c_tall)
        stack.add_child(c_short)
        # max_h=6; row_offset = (6 - 2) // 2 = 2
        assert c_short.get_absolute_pos() == (2, 4)

    def test_reverse_order(self):
        stack = HStack(pos=(0, 0), gap=0, reverse=True)
        c1 = make_block(pos=(0, 0), height=1, width=4)
        c2 = make_block(pos=(0, 0), height=1, width=6)
        stack.add_child(c1)
        stack.add_child(c2)
        # ordered = [c2, c1]; c2 at col 0, c1 at col 6
        assert c2.get_absolute_pos() == (0, 0)
        assert c1.get_absolute_pos() == (0, 6)

    def test_get_height_no_children(self):
        stack = HStack(pos=(0, 0))
        assert stack.get_height() == 0


# ===========================================================================
# 6.  InputBox and Button dimensions
# ===========================================================================

class TestComponentDimensions:
    def test_inputbox_get_height_is_3(self):
        box = InputBox(pos=(0, 0), width=20, label="X")
        assert box.get_height() == 3

    def test_inputbox_get_width_matches_constructor(self):
        box = InputBox(pos=(0, 0), width=35, label="X")
        assert box.get_width() == 35

    def test_button_get_height_is_1(self):
        btn = Button(pos=(0, 0), label="OK")
        assert btn.get_height() == 1

    def test_button_default_width_from_label(self):
        # width = get_visual_width("OK") + 4 = 2 + 4 = 6
        btn = Button(pos=(0, 0), label="OK")
        assert btn.get_width() == 6

    def test_button_explicit_width(self):
        btn = Button(pos=(0, 0), label="GO", width=15)
        assert btn.get_width() == 15

    def test_logview_get_height(self):
        lv = LogView(pos=(0, 0), width=40, height=7)
        assert lv.get_height() == 7

    def test_logview_get_width(self):
        lv = LogView(pos=(0, 0), width=40, height=7)
        assert lv.get_width() == 40


# ===========================================================================
# 7.  add_child / remove_child and layer ordering
# ===========================================================================

class TestChildManagement:
    def test_add_child_sets_parent(self):
        parent = BaseComponent(pos=(0, 0))
        child = BaseComponent(pos=(0, 0))
        parent.add_child(child)
        assert child.parent is parent

    def test_add_child_appends_to_children(self):
        parent = BaseComponent(pos=(0, 0))
        c1 = BaseComponent(pos=(0, 0))
        c2 = BaseComponent(pos=(0, 0))
        parent.add_child(c1)
        parent.add_child(c2)
        assert c1 in parent.children
        assert c2 in parent.children

    def test_children_sorted_by_layer(self):
        parent = BaseComponent(pos=(0, 0))
        c_high = BaseComponent(pos=(0, 0), layer=5)
        c_low = BaseComponent(pos=(0, 0), layer=0)
        parent.add_child(c_high)
        parent.add_child(c_low)
        assert parent.children[0] is c_low
        assert parent.children[1] is c_high

    def test_remove_child_clears_parent(self):
        parent = BaseComponent(pos=(0, 0))
        child = BaseComponent(pos=(0, 0))
        parent.add_child(child)
        parent.remove_child(child)
        assert child not in parent.children
        assert child.parent is None

    def test_remove_nonexistent_child_is_safe(self):
        parent = BaseComponent(pos=(0, 0))
        orphan = BaseComponent(pos=(0, 0))
        parent.remove_child(orphan)  # must not raise
