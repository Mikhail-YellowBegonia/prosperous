from typing import List, Optional
from components import BaseComponent

class FocusManager:
    def __init__(self):
        self.focusable_components: List[BaseComponent] = []
        self.focused_index: int = -1

    def add_component(self, component: BaseComponent):
        if component not in self.focusable_components:
            self.focusable_components.append(component)
            if self.focused_index == -1:
                self.focused_index = 0
                component.on_focus()

    def get_focused(self) -> Optional[BaseComponent]:
        if 0 <= self.focused_index < len(self.focusable_components):
            return self.focusable_components[self.focused_index]
        return None

    def move_focus(self, direction: str):
        """简单的线性焦点切换，后续可升级为空间坐标计算"""
        if not self.focusable_components: return
        
        old_focused = self.get_focused()
        if old_focused:
            old_focused.on_blur()

        if direction in ["RIGHT", "DOWN"]:
            self.focused_index = (self.focused_index + 1) % len(self.focusable_components)
        elif direction in ["LEFT", "UP"]:
            self.focused_index = (self.focused_index - 1) % len(self.focusable_components)

        new_focused = self.get_focused()
        if new_focused:
            new_focused.on_focus()

    def handle_input(self, key: str):
        focused = self.get_focused()
        if not focused: return

        if key in ["UP", "DOWN", "LEFT", "RIGHT"]:
            self.move_focus(key)
        elif key == "ENTER":
            focused.on_enter()
        else:
            result = focused.on_key(key)
            if result is not False:
                focused.handle_input(key)
