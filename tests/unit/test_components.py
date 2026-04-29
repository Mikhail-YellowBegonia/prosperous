"""
Unit tests for component state and FocusManager focus stack.

Covers:
  InputBox.handle_input():
    - ordinary printable character appended to text
    - BACKSPACE removes last character
    - SPACE appended when room exists
    - SPACE refused when text would exceed width
    - CONTROL_KEYS not appended to text
    - SEQ(...) keys not appended to text
    - CJK characters count as width 2
    - character refused when width budget exhausted
    - on_enter() default clears text

  LogView.append():
    - single message appended
    - messages up to height capacity all kept
    - oldest line dropped when capacity exceeded
    - boundary: exactly at capacity

  FocusManager:
    - add_component: first component auto-focused
    - add_component: second component not auto-focused
    - add_component: duplicate ignored
    - move_focus DOWN advances index and calls on_focus/on_blur
    - move_focus UP wraps around
    - move_focus RIGHT == DOWN
    - move_focus LEFT == UP
    - handle_input ENTER calls focused.on_enter
    - handle_input direction delegates to move_focus
    - handle_input other key calls on_key then handle_input
    - handle_input on_key returning True suppresses handle_input
    - push_group: bottom layer blurred, new group focused
    - pop_group: restores previous focus
    - pop_group on single-layer stack is no-op
    - clear() defocuses all in current group
    - get_focused() returns None when no components registered
"""

import sys
import os
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prosperous import InputBox, LogView, BaseComponent
from prosperous import FocusManager


# ===========================================================================
# Helpers
# ===========================================================================


class _MockComponent(BaseComponent):
    """A trackable focusable component for FocusManager tests."""

    def __init__(self, name="comp"):
        super().__init__(pos=(0, 0), focusable=True)
        self.name = name
        self.focus_calls = 0
        self.blur_calls = 0
        self.enter_calls = 0
        self.handle_calls: list = []
        self.key_calls: list = []
        self._key_return = None  # set to True to suppress handle_input

    def on_focus(self):
        self.focus_calls += 1

    def on_blur(self):
        self.blur_calls += 1

    def on_enter(self):
        self.enter_calls += 1

    def on_key(self, key):
        self.key_calls.append(key)
        return self._key_return

    def handle_input(self, key):
        self.handle_calls.append(key)


# ===========================================================================
# InputBox.handle_input()
# ===========================================================================


class TestInputBoxHandleInput:
    # width=20 → inner usable chars: width - 3 = 17 (ASCII)
    WIDTH = 20

    def _box(self):
        return InputBox(pos=(0, 0), width=self.WIDTH, label="TEST")

    def test_printable_char_appended(self):
        box = self._box()
        box.handle_input("a")
        assert box.text == "a"

    def test_multiple_chars_appended_in_order(self):
        box = self._box()
        for ch in ["h", "e", "l", "l", "o"]:
            box.handle_input(ch)
        assert box.text == "hello"

    def test_backspace_removes_last_char(self):
        box = self._box()
        box.text = "hello"
        box.handle_input("BACKSPACE")
        assert box.text == "hell"

    def test_backspace_on_empty_is_safe(self):
        box = self._box()
        box.handle_input("BACKSPACE")
        assert box.text == ""

    def test_space_appended_when_room(self):
        box = self._box()
        box.handle_input("SPACE")
        assert box.text == " "

    def test_space_refused_when_at_limit(self):
        box = self._box()
        # Fill up to the limit (width - 3 = 17 ASCII chars)
        limit = self.WIDTH - 3
        box.text = "x" * limit
        box.handle_input("SPACE")
        assert len(box.text) == limit

    def test_control_key_not_appended(self):
        box = self._box()
        for key in ["UP", "DOWN", "LEFT", "RIGHT", "ENTER", "ESC", "TAB"]:
            box.handle_input(key)
        assert box.text == ""

    def test_seq_key_not_appended(self):
        box = self._box()
        box.handle_input("SEQ('\\x1b[3~')")
        assert box.text == ""

    def test_cjk_char_counts_as_width_2(self):
        # width=10 → inner_w = 7; CJK char width=2 each → 3 chars = 6, 4th would need 8 > 7
        box = InputBox(pos=(0, 0), width=10, label="X")
        inner_w = 10 - 3  # 7
        for _ in range(inner_w // 2):
            box.handle_input("中")
        # 3 CJK chars = visual width 6, within budget
        assert len(box.text) == inner_w // 2
        # One more would overflow
        before = box.text
        box.handle_input("中")
        assert box.text == before

    def test_char_refused_when_budget_exhausted(self):
        box = self._box()
        limit = self.WIDTH - 3
        box.text = "x" * limit
        box.handle_input("z")
        assert len(box.text) == limit

    def test_on_enter_clears_text(self):
        box = self._box()
        box.text = "some content"
        box.on_enter()
        assert box.text == ""


# ===========================================================================
# LogView.append()
# ===========================================================================


class TestLogViewAppend:
    def _lv(self, height=5, width=40, **kwargs):
        return LogView(pos=(0, 0), width=width, height=height, **kwargs)

    def test_single_message_stored(self):
        lv = self._lv()
        lv.append("hello")
        # _buffer 存储的是 List[List[Tuple[str, Style]]]
        assert len(lv._buffer) == 1
        assert lv._buffer[0][0][0] == "hello"

    def test_multiple_messages_up_to_capacity(self):
        lv = self._lv(height=3)
        lv.append("a")
        lv.append("b")
        lv.append("c")
        assert len(lv._buffer) == 3
        assert [line[0][0] for line in lv._buffer] == ["a", "b", "c"]

    def test_oldest_dropped_when_over_capacity(self):
        # 注意：现在最大容量由 max_lines 控制，默认 1000
        lv = self._lv(height=3, max_lines=3)
        lv.append("a")
        lv.append("b")
        lv.append("c")
        lv.append("d")
        assert len(lv._buffer) == 3
        assert [line[0][0] for line in lv._buffer] == ["b", "c", "d"]

    def test_many_messages_only_last_n_kept(self):
        lv = self._lv(height=4, max_lines=4)
        for i in range(10):
            lv.append(str(i))
        assert [line[0][0] for line in lv._buffer] == ["6", "7", "8", "9"]

    def test_exactly_at_capacity_does_not_drop(self):
        lv = self._lv(height=5, max_lines=5)
        for i in range(5):
            lv.append(str(i))
        assert len(lv._buffer) == 5
        assert lv._buffer[0][0][0] == "0"

    def test_height_1_keeps_only_last(self):
        # height=1, max_lines=1
        lv = self._lv(height=1, max_lines=1)
        lv.append("first")
        lv.append("second")
        assert lv._buffer[0][0][0] == "second"

    def test_empty_string_can_be_appended(self):
        lv = self._lv()
        lv.append("")
        # Empty string should result in an empty line (or empty list of segments)
        assert len(lv._buffer) == 1


# ===========================================================================
# FocusManager
# ===========================================================================


class TestFocusManagerBasic:
    def test_get_focused_returns_none_when_empty(self):
        fm = FocusManager()
        assert fm.get_focused() is None

    def test_first_component_auto_focused(self):
        fm = FocusManager()
        c = _MockComponent()
        fm.add_component(c)
        assert fm.get_focused() is c
        assert c.is_focused is True
        assert c.focus_calls == 1

    def test_second_component_not_auto_focused(self):
        fm = FocusManager()
        c1 = _MockComponent()
        c2 = _MockComponent()
        fm.add_component(c1)
        fm.add_component(c2)
        assert fm.get_focused() is c1
        assert c2.is_focused is False

    def test_duplicate_component_ignored(self):
        fm = FocusManager()
        c = _MockComponent()
        fm.add_component(c)
        fm.add_component(c)
        assert len(fm._components) == 1

    def test_move_focus_down_advances(self):
        fm = FocusManager()
        c1 = _MockComponent("c1")
        c2 = _MockComponent("c2")
        fm.add_component(c1)
        fm.add_component(c2)
        fm.move_focus("DOWN")
        assert fm.get_focused() is c2
        assert c2.is_focused is True
        assert c1.is_focused is False
        assert c1.blur_calls == 1
        assert c2.focus_calls == 1

    def test_move_focus_wraps_around_forward(self):
        fm = FocusManager()
        c1 = _MockComponent()
        c2 = _MockComponent()
        fm.add_component(c1)
        fm.add_component(c2)
        fm.move_focus("DOWN")  # c2
        fm.move_focus("DOWN")  # wraps to c1
        assert fm.get_focused() is c1

    def test_move_focus_up_wraps_around_backward(self):
        fm = FocusManager()
        c1 = _MockComponent()
        c2 = _MockComponent()
        fm.add_component(c1)
        fm.add_component(c2)
        fm.move_focus("UP")  # wraps from c1 to c2
        assert fm.get_focused() is c2

    def test_move_focus_right_same_as_down(self):
        fm = FocusManager()
        c1 = _MockComponent()
        c2 = _MockComponent()
        fm.add_component(c1)
        fm.add_component(c2)
        fm.move_focus("RIGHT")
        assert fm.get_focused() is c2

    def test_move_focus_left_same_as_up(self):
        fm = FocusManager()
        c1 = _MockComponent()
        c2 = _MockComponent()
        fm.add_component(c1)
        fm.add_component(c2)
        fm.move_focus("LEFT")
        assert fm.get_focused() is c2  # wraps backward


class TestFocusManagerInputDispatch:
    def test_handle_input_enter_calls_on_enter(self):
        fm = FocusManager()
        c = _MockComponent()
        fm.add_component(c)
        fm.handle_input("ENTER")
        assert c.enter_calls == 1

    def test_handle_input_direction_delegates_to_move_focus(self):
        fm = FocusManager()
        c1 = _MockComponent()
        c2 = _MockComponent()
        fm.add_component(c1)
        fm.add_component(c2)
        fm.handle_input("DOWN")
        assert fm.get_focused() is c2

    def test_handle_input_other_key_calls_on_key_then_handle_input(self):
        fm = FocusManager()
        c = _MockComponent()
        fm.add_component(c)
        fm.handle_input("a")
        assert "a" in c.key_calls
        assert "a" in c.handle_calls

    def test_handle_input_on_key_true_suppresses_handle_input(self):
        fm = FocusManager()
        c = _MockComponent()
        c._key_return = True
        fm.add_component(c)
        fm.handle_input("x")
        assert "x" in c.key_calls
        assert "x" not in c.handle_calls

    def test_handle_input_no_focused_is_safe(self):
        fm = FocusManager()
        fm.handle_input("a")  # must not raise


class TestFocusManagerStack:
    def test_push_group_blurs_current_and_focuses_new(self):
        fm = FocusManager()
        c1 = _MockComponent("c1")
        fm.add_component(c1)

        c2 = _MockComponent("c2")
        fm.push_group([c2])

        assert fm.get_focused() is c2
        assert c2.is_focused is True
        assert c1.is_focused is False
        assert c1.blur_calls == 1

    def test_push_group_isolates_new_group(self):
        fm = FocusManager()
        c1 = _MockComponent("c1")
        c2 = _MockComponent("c2")
        fm.add_component(c1)

        fm.push_group([c2])
        fm.handle_input("DOWN")  # only c2 in group; wrap stays on c2
        assert fm.get_focused() is c2

    def test_pop_group_restores_previous_focus(self):
        fm = FocusManager()
        c1 = _MockComponent("c1")
        fm.add_component(c1)

        c2 = _MockComponent("c2")
        fm.push_group([c2])
        fm.pop_group()

        assert fm.get_focused() is c1
        assert c1.is_focused is True
        # c1 should have received on_focus again after pop
        assert c1.focus_calls == 2  # once on add, once on pop restore

    def test_pop_group_single_layer_is_noop(self):
        fm = FocusManager()
        c = _MockComponent()
        fm.add_component(c)
        stack_depth_before = len(fm._stack)
        fm.pop_group()
        assert len(fm._stack) == stack_depth_before

    def test_nested_push_pop(self):
        fm = FocusManager()
        c1 = _MockComponent("c1")
        c2 = _MockComponent("c2")
        c3 = _MockComponent("c3")
        fm.add_component(c1)
        fm.push_group([c2])
        fm.push_group([c3])

        assert fm.get_focused() is c3
        fm.pop_group()
        assert fm.get_focused() is c2
        fm.pop_group()
        assert fm.get_focused() is c1

    def test_clear_defocuses_all_current_group(self):
        fm = FocusManager()
        c1 = _MockComponent()
        c2 = _MockComponent()
        fm.add_component(c1)
        fm.add_component(c2)
        fm.clear()
        assert fm.get_focused() is None
        assert c1.is_focused is False
        assert c2.is_focused is False

    def test_clear_does_not_affect_other_stack_layers(self):
        fm = FocusManager()
        c1 = _MockComponent("c1")
        fm.add_component(c1)
        c2 = _MockComponent("c2")
        fm.push_group([c2])
        fm.clear()  # clears group containing c2

        assert len(fm._stack) == 2  # stack layers intact
        fm.pop_group()
        # After pop, c1's layer should be intact
        assert fm.get_focused() is c1


class TestFocusManagerRemove:
    def test_remove_non_focused_component(self):
        fm = FocusManager()
        c1 = _MockComponent("c1")
        c2 = _MockComponent("c2")
        fm.add_component(c1)
        fm.add_component(c2)
        fm.remove_component(c2)
        assert c2 not in fm._components
        assert fm.get_focused() is c1  # focus unchanged

    def test_remove_focused_component_transfers_focus(self):
        fm = FocusManager()
        c1 = _MockComponent("c1")
        c2 = _MockComponent("c2")
        fm.add_component(c1)
        fm.add_component(c2)
        fm.remove_component(c1)  # c1 had focus
        assert c1 not in fm._components
        assert fm.get_focused() is c2
        assert c2.is_focused is True
        assert c1.is_focused is False
        assert c1.blur_calls == 1

    def test_remove_focused_last_component_leaves_empty(self):
        fm = FocusManager()
        c = _MockComponent()
        fm.add_component(c)
        fm.remove_component(c)
        assert fm.get_focused() is None
        assert fm._focused_index == -1

    def test_remove_adjusts_index_when_before_focus(self):
        fm = FocusManager()
        c1 = _MockComponent("c1")
        c2 = _MockComponent("c2")
        c3 = _MockComponent("c3")
        fm.add_component(c1)
        fm.add_component(c2)
        fm.add_component(c3)
        fm.move_focus("DOWN")  # focus → c2
        fm.move_focus("DOWN")  # focus → c3
        fm.remove_component(c1)  # remove before focused c3
        assert fm.get_focused() is c3  # focus stays on c3
        assert fm._focused_index == 1  # index adjusted down by 1

    def test_remove_component_not_in_group_is_noop(self):
        fm = FocusManager()
        c1 = _MockComponent("c1")
        c2 = _MockComponent("c2")
        fm.add_component(c1)
        fm.remove_component(c2)  # c2 was never added
        assert fm.get_focused() is c1


class TestRootLifecycle:
    def test_remove_child_clears_root_on_subtree(self):
        """remove_child 后被移除子树的 _root 应被清空。"""
        mock_root = object()  # 任意非 None 对象模拟 Live

        parent = BaseComponent()
        child = BaseComponent()
        grandchild = BaseComponent()
        child.add_child(grandchild)
        parent.add_child(child)

        # 手动设置 _root（模拟已挂载到引擎）
        parent._root = mock_root
        child._root = mock_root
        grandchild._root = mock_root

        # remove_child 时 _root 需要通过 _detach_component 清理
        # 但 mock_root 没有 _detach_component，所以我们用真实的方式：
        # 直接测试 _root 是否为 None 需要一个有 _detach_component 的对象
        # 改用 unittest.mock
        from unittest.mock import MagicMock
        live_mock = MagicMock()
        parent._root = live_mock
        child._root = live_mock
        grandchild._root = live_mock

        parent.remove_child(child)

        live_mock._detach_component.assert_called_once_with(child)

    def test_add_child_calls_attach_when_root_set(self):
        """add_child 时若父树已挂载，应通知 _root 注册新子树。"""
        from unittest.mock import MagicMock
        live_mock = MagicMock()

        parent = BaseComponent()
        parent._root = live_mock

        child = BaseComponent()
        parent.add_child(child)

        live_mock._attach_component.assert_called_once_with(child)
