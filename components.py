from styles import Style, DEFAULT_STYLE
from typing import Callable, List, Optional, Union
from utils import debug_log, get_visual_width

class BaseComponent:
    def __init__(self, pos: tuple = (0, 0), style: Optional[Style] = None, layer: int = 0,
                 focusable: bool = False, children: List['BaseComponent'] = None):
        try:
            self.pos = (int(pos[0]), int(pos[1]))
        except (TypeError, IndexError, ValueError):
            debug_log(f"[BaseComponent] Warning: Invalid pos {pos}, defaulting to (0, 0)")
            self.pos = (1, 1)

        self.style = style or Style()
        self.layer = layer
        self.focusable = focusable
        self.is_focused = False
        self.parent: Optional['BaseComponent'] = None
        self.children: List['BaseComponent'] = []

        if children:
            for child in children:
                self.add_child(child)

    def on_focus(self):
        self.is_focused = True

    def on_blur(self):
        self.is_focused = False

    def on_enter(self):
        pass

    def on_key(self, key: str):
        """按键到达组件前触发。返回 False 可阻止默认的 handle_input 行为。"""
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
        from input_handler import InputHandler
        try:
            if key == "BACKSPACE":
                self.text = self.text[:-1]
            elif key == "SPACE":
                if get_visual_width(self.text) < self.width - 3:
                    self.text += " "
            elif key not in InputHandler.CONTROL_KEYS and not key.startswith("SEQ("):
                if get_visual_width(self.text) + get_visual_width(key) <= self.width - 3:
                    self.text += key
        except Exception as e:
            debug_log(f"[InputBox] Input handle failed: {e}")

    def on_enter(self):
        self.text = "" 

    def draw(self, engine):
        from utils import get_visual_width
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
            
            # 使用 get_visual_width 计算内容的视觉长度
            # 注意：这里需要确保总宽度 w - 2 保持一致
            # 我们根据视觉宽度进行填充，而不是字符个数
            content_text = self.text + cursor
            inner_w = w - 2

            content_width = get_visual_width(content_text)
            if content_width > inner_w:
                # 按视觉宽度截断，为省略号留出 1 列
                budget = inner_w - 1
                acc, cut = 0, 0
                for i, ch in enumerate(content_text):
                    cw = get_visual_width(ch)
                    if acc + cw > budget:
                        cut = i
                        break
                    acc += cw
                else:
                    cut = len(content_text)
                content = content_text[:cut] + "…" + " " * (inner_w - acc - 1)
            else:
                content = content_text + " " * (inner_w - content_width)
            
            mid = "│" + content + "│"
            bot = "└" + "─" * (w - 2) + "┘"

            engine.push(ay, ax, top, border_style)
            engine.push(ay + 1, ax, mid, eff_style)
            engine.push(ay + 2, ax, bot, border_style)
            
            super().draw(engine)
        except Exception as e:
            debug_log(f"[InputBox] Draw failed: {e}")

class Panel(BaseComponent):
    def __init__(self, pos=(0, 0), width=50, height=10, title="PANEL", style=None, children=None):
        super().__init__(pos=pos, style=style, children=children)
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

class Text(BaseComponent):
    def __init__(self, pos=(0, 0), text: Union[str, Callable[[], str]] = "", style=None):
        super().__init__(pos=pos, style=style)
        self._text = text

    def draw(self, engine):
        try:
            content = self._text() if callable(self._text) else self._text
            ay, ax = self.get_absolute_pos()
            engine.push(ay, ax, content, self.get_effective_style())
            super().draw(engine)
        except Exception as e:
            debug_log(f"[Text] Draw failed: {e}")

class ProgressBar(BaseComponent):
    def __init__(self, pos=(0, 0), width=20, value: Union[float, Callable[[], float]] = 0.0,
                 filled_style=None, empty_style=None, style=None):
        super().__init__(pos=pos, style=style)
        self._value = value
        self.width = width
        self.filled_style = filled_style or Style(fg=(80, 200, 120))
        self.empty_style = empty_style or Style(fg=(60, 60, 60))

    def draw(self, engine):
        try:
            v = max(0.0, min(1.0, self._value() if callable(self._value) else self._value))
            ay, ax = self.get_absolute_pos()
            inner = self.width - 5          # 留给 " XX%" 后缀
            filled = round(inner * v)
            empty = inner - filled
            pct = f"{round(v * 100):>3}%"
            engine.push(ay, ax, "█" * filled, self.filled_style)
            engine.push(ay, ax + filled, "░" * empty, self.empty_style)
            engine.push(ay, ax + inner, pct, self.get_effective_style())
            super().draw(engine)
        except Exception as e:
            debug_log(f"[ProgressBar] Draw failed: {e}")

class LogView(BaseComponent):
    """固定行数的日志视图，滚动逻辑留空待后续实现。"""
    def __init__(self, pos=(0, 0), width=40, height=5, style=None):
        super().__init__(pos=pos, style=style)
        self.width = width
        self.height = height
        self._lines: List[str] = []

    def append(self, msg: str):
        self._lines.append(msg)
        if len(self._lines) > self.height:
            self._lines.pop(0)

    def draw(self, engine):
        try:
            ay, ax = self.get_absolute_pos()
            eff = self.get_effective_style()
            for i in range(self.height):
                line = self._lines[i] if i < len(self._lines) else ""
                # 截断超宽行
                if get_visual_width(line) > self.width:
                    budget, cut = 0, 0
                    for j, ch in enumerate(line):
                        if budget + get_visual_width(ch) > self.width - 1:
                            cut = j
                            break
                        budget += get_visual_width(ch)
                    else:
                        cut = len(line)
                    line = line[:cut] + "…"
                engine.push(ay + i, ax, line.ljust(self.width), eff)
            super().draw(engine)
        except Exception as e:
            debug_log(f"[LogView] Draw failed: {e}")
