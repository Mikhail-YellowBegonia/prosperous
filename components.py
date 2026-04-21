from styles import Style, DEFAULT_STYLE
from typing import List, Optional

class BaseComponent:
    def __init__(self, pos: tuple = (0, 0), style: Optional[Style] = None, layer: int = 0, focusable: bool = False):
        self.pos = pos # (y, x) 相对坐标
        self.style = style or Style() # 自身样式
        self.layer = layer
        self.focusable = focusable
        self.is_focused = False
        self.parent: Optional['BaseComponent'] = None
        self.children: List['BaseComponent'] = []

    def on_focus(self):
        self.is_focused = True

    def on_blur(self):
        self.is_focused = False

    def on_enter(self):
        """按下 ENTER 时的回调"""
        pass

    def handle_input(self, key: str):
        """接收并处理输入事件"""
        pass

    def add_child(self, child: 'BaseComponent'):
        child.parent = self
        self.children.append(child)
        self.children.sort(key=lambda x: x.layer)

    def get_absolute_pos(self) -> tuple:
        """递归计算绝对坐标"""
        if self.parent:
            py, px = self.parent.get_absolute_pos()
            return (py + self.pos[0], px + self.pos[1])
        return self.pos

    def get_effective_style(self) -> Style:
        """递归合并父组件样式"""
        if self.parent:
            return self.parent.get_effective_style().merge(self.style)
        return DEFAULT_STYLE.merge(self.style)

    def draw(self, engine):
        """组件渲染逻辑，由子类实现"""
        for child in self.children:
            child.draw(engine)

class InputBox(BaseComponent):
    def __init__(self, pos=(0, 0), width=40, label="INPUT", style=None):
        super().__init__(pos=pos, style=style, focusable=True)
        self.width = width
        self.label = label
        self.text = ""
        self.cursor_visible = True
        self._last_blink = 0

    def handle_input(self, key):
        if key == "BACKSPACE":
            self.text = self.text[:-1]
        elif key == "SPACE":
            self.text += " "
        elif len(key) == 1: 
            if len(self.text) < self.width - 4:
                self.text += key

    def on_enter(self):
        self.text = "" # 按回车清空

    def draw(self, engine):
        import time
        if self.is_focused and time.time() - self._last_blink > 0.5:
            self.cursor_visible = not self.cursor_visible
            self._last_blink = time.time()
        
        if not self.is_focused:
            self.cursor_visible = False

        ay, ax = self.get_absolute_pos()
        eff_style = self.get_effective_style()
        
        # 焦点视觉反馈：黄色边框
        border_style = eff_style.merge(Style(fg=220)) if self.is_focused else eff_style
        
        cursor = " " if not self.cursor_visible else "█"
        w = self.width
        label_txt = f" {self.label} "
        top = "┌" + label_txt.center(w - 2, "─") + "┐"
        
        display_text = self.text + cursor
        content = display_text.ljust(w - 2)[:w - 2]
        mid = "│" + content + "│"
        bot = "└" + "─" * (w - 2) + "┘"

        engine.push(ay, ax, top, border_style)
        engine.push(ay + 1, ax, mid, eff_style)
        engine.push(ay + 2, ax, bot, border_style)
        
        super().draw(engine)

class Panel(BaseComponent):
    def __init__(self, pos=(0, 0), width=50, height=10, title="PANEL", style=None):
        super().__init__(pos=pos, style=style)
        self.width = width
        self.height = height
        self.title = title

    def draw(self, engine):
        ay, ax = self.get_absolute_pos()
        eff_style = self.get_effective_style()
        
        title_txt = f" {self.title} "
        top = "┌" + title_txt.center(self.width - 2, "─") + "┐"
        engine.push(ay, ax, top, eff_style)
        
        for i in range(1, self.height - 1):
            mid = "│" + " " * (self.width - 2) + "│"
            engine.push(ay + i, ax, mid, eff_style)
            
        bot = "└" + "─" * (self.width - 2) + "┘"
        engine.push(ay + self.height - 1, ax, bot, eff_style)
        
        super().draw(engine)
