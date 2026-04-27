from typing import List, Optional
from .components import BaseComponent


class FocusManager:
    """管理可聚焦组件之间的焦点切换与输入分发，支持焦点栈（用于 Modal 等场景）。

    基本用法：
        focus = FocusManager()
        focus.add_component(input_box)
        focus.add_component(button)

        for key in live.poll():
            focus.handle_input(key)

    Modal / 焦点隔离：
        focus.push_group([btn_yes, btn_no])   # 压栈，底层组件冻结
        focus.pop_group()                     # 弹栈，自动恢复上一组焦点

    焦点切换：方向键（UP/DOWN/LEFT/RIGHT）在当前组内线性循环。
    输入分发：ENTER 触发 on_enter，其余按键先经 on_key，再交 handle_input。
    """

    def __init__(self):
        self._stack: List[List[BaseComponent]] = [[]]
        self._idx_stack: List[int] = [-1]

    # ── 内部访问当前组 ─────────────────────────────────────

    @property
    def _components(self) -> List[BaseComponent]:
        return self._stack[-1]

    @property
    def _focused_index(self) -> int:
        return self._idx_stack[-1]

    @_focused_index.setter
    def _focused_index(self, v: int):
        self._idx_stack[-1] = v

    # ── 公开 API ───────────────────────────────────────────

    def add_component(self, component: BaseComponent):
        """向当前焦点组注册组件。首个注册的组件自动获得焦点。"""
        if component not in self._components:
            self._components.append(component)
            if self._focused_index == -1:
                self._focused_index = 0
                component.is_focused = True
                component.on_focus()

    def push_group(self, components: List[BaseComponent]):
        """压入新焦点组并注册组件，底层组件冻结直到 pop_group()。"""
        old = self.get_focused()
        if old:
            old.is_focused = False
            old.on_blur()
        self._stack.append([])
        self._idx_stack.append(-1)
        for c in components:
            self.add_component(c)

    def pop_group(self):
        """弹出当前焦点组，自动恢复上一组的焦点状态。栈只剩一层时无效。"""
        if len(self._stack) <= 1:
            return
        current = self.get_focused()
        if current:
            current.is_focused = False
            current.on_blur()
        for c in self._components:
            c.is_focused = False
        self._stack.pop()
        self._idx_stack.pop()
        restored = self.get_focused()
        if restored:
            restored.is_focused = True
            restored.on_focus()

    def clear(self):
        """清空当前焦点组（不影响栈中其他层）。"""
        for c in self._components:
            c.is_focused = False
        self._stack[-1] = []
        self._idx_stack[-1] = -1

    def get_focused(self) -> Optional[BaseComponent]:
        if 0 <= self._focused_index < len(self._components):
            return self._components[self._focused_index]
        return None

    def move_focus(self, direction: str):
        if not self._components:
            return
        old = self.get_focused()
        if old:
            old.is_focused = False
            old.on_blur()
        if direction in ["RIGHT", "DOWN"]:
            self._focused_index = (self._focused_index + 1) % len(self._components)
        elif direction in ["LEFT", "UP"]:
            self._focused_index = (self._focused_index - 1) % len(self._components)
        new = self.get_focused()
        if new:
            new.is_focused = True
            new.on_focus()

    def handle_input(self, key: str):
        focused = self.get_focused()
        if not focused:
            return
        if key in ["UP", "DOWN", "LEFT", "RIGHT"]:
            self.move_focus(key)
        elif key == "ENTER":
            focused.on_enter()
        else:
            result = focused.on_key(key)
            if result is not False:
                focused.handle_input(key)
