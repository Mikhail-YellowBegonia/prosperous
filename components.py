from styles import Style, DEFAULT_STYLE
from typing import List, Optional
from utils import debug_log

class BaseComponent:
    def __init__(self, pos: tuple = (0, 0), style: Optional[Style] = None, layer: int = 0, focusable: bool = False):
        # 鲁棒性：校验 pos 合法性，不合法则强制归位至 (1, 1)
        if not isinstance(pos, tuple) or len(pos) != 2 or not all(isinstance(i, int) for i in pos):
            debug_log(f"[BaseComponent] Warning: Invalid pos {pos}, resetting to (1, 1)")
            self.pos = (1, 1)
        else:
            self.pos = pos
            
        self.style = style or Style()
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
        pass

    def handle_input(self, key: str):
        pass

    def add_child(self, child: 'BaseComponent'):
        if not isinstance(child, BaseComponent):
            debug_log("[BaseComponent] Error: child must be an instance of BaseComponent")
            return
        child.parent = self
        self.children.append(child)
        self.children.sort(key=lambda x: x.layer)

    def get_absolute_pos(self) -> tuple:
        try:
            if self.parent:
                py, px = self.parent.get_absolute_pos()
                return (py + self.pos[0], px + self.pos[1])
            return self.pos
        except Exception as e:
            debug_log(f"[BaseComponent] Error in coordinate resolution: {e}")
            return (1, 1)

    def get_effective_style(self) -> Style:
        try:
            if self.parent:
                return self.parent.get_effective_style().merge(self.style)
            return DEFAULT_STYLE.merge(self.style)
        except Exception as e:
            debug_log(f"[BaseComponent] Error in style resolution: {e}")
            return DEFAULT_STYLE

    def draw(self, engine):
        """递归渲染，具备异常隔离"""
        for child in self.children:
            try:
                child.draw(engine)
            except Exception as e:
                # 鲁棒性：单个子组件崩溃不影响全局
                debug_log(f"[BaseComponent] Child component draw failed: {e}")

class InputBox(BaseComponent):
    def __init__(self, pos=(0, 0), width=40, label="INPUT", style=None):
        super().__init__(pos=pos, style=style, focusable=True)
        self.width = width
        self.label = label
        self.text = ""
        self.cursor_visible = True
        self._last_blink = 0

    def handle_input(self, key):
        try:
            if key == "BACKSPACE":
                self.text = self.text[:-1]
            elif key == "SPACE":
                self.text += " "
            elif len(key) >= 1: 
                # 支持多字符 (针对 IME 最终输出的完整字符)
                # 排除我们定义的特殊控制键名（全大写）
                if not (key.isupper() and len(key) > 1):
                    # 限制长度 (考虑宽字符占位，这里简单按字符数算，后续可优化)
                    if len(self.text) < self.width - 4:
                        self.text += key
        except Exception as e:
            debug_log(f"[InputBox] Input handle failed: {e}")

    def on_enter(self):
        self.text = "" 

    def draw(self, engine):
        import time
        try:
            if self.is_focused and time.time() - self._last_blink > 0.5:
                self.cursor_visible = not self.cursor_visible
                self._last_blink = time.time()
            
            if not self.is_focused:
                self.cursor_visible = False

            ay, ax = self.get_absolute_pos()
            eff_style = self.get_effective_style()
            
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
        except Exception as e:
            debug_log(f"[InputBox] Draw failed: {e}")

class Panel(BaseComponent):
    def __init__(self, pos=(0, 0), width=50, height=10, title="PANEL", style=None):
        super().__init__(pos=pos, style=style)
        self.width = width
        self.height = height
        self.title = title

    def draw(self, engine):
        try:
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
        except Exception as e:
            debug_log(f"[Panel] Draw failed: {e}")
