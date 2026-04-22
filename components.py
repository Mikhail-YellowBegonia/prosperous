from styles import Style, DEFAULT_STYLE
from typing import Callable, List, Optional, Union
from utils import debug_log, get_visual_width


class BaseComponent:
    """所有组件的基类。

    坐标系说明：pos=(row, col)，均从 0 开始，子组件坐标相对于父组件原点（含边框）。
    样式继承：子组件未指定的样式属性自动继承父组件。
    层级排序：layer 值越大越后绘制（越靠上层）。

    事件回调（直接赋值覆盖即可）：
        component.on_focus  = lambda: ...        # 获得焦点时触发
        component.on_blur   = lambda: ...        # 失去焦点时触发
        component.on_enter  = lambda: ...        # ENTER 键触发
        component.on_key    = lambda key: ...    # 其它按键触发，返回 False 可阻断默认行为
    """

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
        """获得焦点时由 FocusManager 调用。可赋值覆盖以添加自定义行为。"""
        pass

    def on_blur(self):
        """失去焦点时由 FocusManager 调用。可赋值覆盖以添加自定义行为。"""
        pass

    def on_enter(self):
        """ENTER 键按下时由 FocusManager 调用。可赋值覆盖。"""
        pass

    def on_key(self, key: str):
        """非方向键、非 ENTER 的按键到达组件前触发。返回 False 可阻止后续 handle_input。"""
        pass

    def handle_input(self, key: str):
        """处理到达本组件的按键，由子类实现。"""
        pass

    def add_child(self, child: 'BaseComponent'):
        """将子组件挂载到本组件，子组件坐标将相对于本组件原点计算。"""
        if not isinstance(child, BaseComponent):
            debug_log("[BaseComponent] Error: child must be an instance of BaseComponent")
            return
        child.parent = self
        self.children.append(child)
        self.children.sort(key=lambda x: x.layer)

    def get_absolute_pos(self) -> tuple:
        """递归计算本组件在屏幕上的绝对坐标 (row, col)。"""
        try:
            if self.parent:
                py, px = self.parent.get_absolute_pos()
                return (py + self.pos[0], px + self.pos[1])
            return self.pos
        except Exception as e:
            debug_log(f"[BaseComponent] Error in coordinate resolution: {e}")
            return (1, 1)

    def get_effective_style(self) -> Style:
        """递归合并祖先样式，返回本组件实际生效的样式。"""
        try:
            if self.parent:
                return self.parent.get_effective_style().merge(self.style)
            return DEFAULT_STYLE.merge(self.style)
        except Exception as e:
            debug_log(f"[BaseComponent] Error in style resolution: {e}")
            return DEFAULT_STYLE

    def draw(self, engine):
        """递归绘制所有子组件，单个子组件异常不影响其余组件。"""
        for child in self.children:
            try:
                child.draw(engine)
            except Exception as e:
                debug_log(f"[BaseComponent] Child component draw failed: {e}")


class InputBox(BaseComponent):
    """单行文本输入框，支持 CJK 字符，超长内容自动截断并显示省略号。

    属性：
        text (str): 当前输入内容，可直接读写。

    回调：
        on_enter: ENTER 键触发，默认清空输入框。
        on_key:   其它按键触发，返回 False 可完全接管输入。

    示例：
        box = InputBox(pos=(1, 1), width=30, label="NAME")
        box.on_enter = lambda: submit(box.text)
    """

    def __init__(self, pos=(0, 0), width=40, label="INPUT", style=None, layer=0):
        super().__init__(pos=pos, style=style, layer=layer, focusable=True)
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

            cursor = "█" if self.cursor_visible else " "
            w = self.width
            inner_w = w - 2
            label_txt = f" {self.label} "
            top = "┌" + label_txt.center(w - 2, "─") + "┐"

            content_text = self.text + cursor
            content_width = get_visual_width(content_text)
            if content_width > inner_w:
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

            engine.push(ay,     ax, top,             border_style)
            engine.push(ay + 1, ax, "│" + content + "│", eff_style)
            engine.push(ay + 2, ax, "└" + "─" * (w - 2) + "┘", border_style)

            super().draw(engine)
        except Exception as e:
            debug_log(f"[InputBox] Draw failed: {e}")


class Button(BaseComponent):
    """可聚焦的按钮，聚焦时高亮，ENTER 触发动作。

    回调：
        on_enter: 按下 ENTER 时触发，无默认行为，需用户赋值。

    示例：
        btn = Button(pos=(1, 1), label="确认", width=12)
        btn.on_enter = lambda: do_something()
    """

    def __init__(self, pos=(0, 0), label="BUTTON", width=None, style=None, layer=0):
        super().__init__(pos=pos, style=style, layer=layer, focusable=True)
        self.label = label
        self.width = width if width is not None else get_visual_width(label) + 4

    def draw(self, engine):
        try:
            ay, ax = self.get_absolute_pos()
            eff_style = self.get_effective_style()
            inner = self.width - 4
            text = self.label[:inner].center(inner)
            if self.is_focused:
                display = f"[ {text} ]"
                btn_style = eff_style.merge(Style(fg=220, bold=True))
            else:
                display = f"  {text}  "
                btn_style = eff_style
            engine.push(ay, ax, display, btn_style)
            super().draw(engine)
        except Exception as e:
            debug_log(f"[Button] Draw failed: {e}")


class Panel(BaseComponent):
    """带标题边框的容器，子组件坐标相对于 Panel 左上角（含边框字符）。

    示例：
        panel = Panel(pos=(1, 1), width=40, height=8, title="INFO", children=[
            Text(pos=(1, 1), text="hello"),
        ])
    """

    def __init__(self, pos=(0, 0), width=50, height=10, title="PANEL", style=None, layer=0, children=None):
        super().__init__(pos=pos, style=style, layer=layer, children=children)
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
                engine.push(ay + i, ax, "│" + " " * (self.width - 2) + "│", eff_style)

            engine.push(ay + self.height - 1, ax, "└" + "─" * (self.width - 2) + "┘", eff_style)

            super().draw(engine)
        except Exception as e:
            debug_log(f"[Panel] Draw failed: {e}")


class Text(BaseComponent):
    """单行文本，支持静态字符串或每帧求值的 lambda。

    示例：
        Text(pos=(0, 0), text="固定内容")
        Text(pos=(1, 0), text=lambda: f"计数: {counter}", style=Style(fg=46))
    """

    def __init__(self, pos=(0, 0), text: Union[str, Callable[[], str]] = "", style=None, layer=0):
        super().__init__(pos=pos, style=style, layer=layer)
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
    """水平进度条，值范围 0.0～1.0，支持静态值或 lambda。

    尾部自动附加百分比文字，总宽度 = 进度槽宽 + 4（" XX%"）。

    示例：
        ProgressBar(pos=(0, 0), width=25, value=0.72)
        ProgressBar(pos=(1, 0), width=25, value=lambda: cpu_usage,
                    filled_style=Style(fg=(255, 100, 100)))
    """

    def __init__(self, pos=(0, 0), width=20, value: Union[float, Callable[[], float]] = 0.0,
                 filled_style=None, empty_style=None, style=None, layer=0):
        super().__init__(pos=pos, style=style, layer=layer)
        self._value = value
        self.width = width
        self.filled_style = filled_style or Style(fg=(80, 200, 120))
        self.empty_style = empty_style or Style(fg=(60, 60, 60))

    def draw(self, engine):
        try:
            v = max(0.0, min(1.0, self._value() if callable(self._value) else self._value))
            ay, ax = self.get_absolute_pos()
            inner = self.width - 5
            filled = round(inner * v)
            empty = inner - filled
            pct = f"{round(v * 100):>3}%"
            engine.push(ay, ax,          "█" * filled, self.filled_style)
            engine.push(ay, ax + filled, "░" * empty,  self.empty_style)
            engine.push(ay, ax + inner,  pct,           self.get_effective_style())
            super().draw(engine)
        except Exception as e:
            debug_log(f"[ProgressBar] Draw failed: {e}")


class LogView(BaseComponent):
    """固定行数的日志视图，新条目追加到末尾，超出行数时顶部滚出。
    滚动浏览功能待后续实现。

    方法：
        append(msg): 追加一条日志，超宽内容自动截断。

    示例：
        log = LogView(pos=(1, 1), width=50, height=5)
        log.append("[INFO] 应用启动")
    """

    def __init__(self, pos=(0, 0), width=40, height=5, style=None, layer=0):
        super().__init__(pos=pos, style=style, layer=layer)
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
                padding = max(0, self.width - get_visual_width(line))
                engine.push(ay + i, ax, line + " " * padding, eff)
            super().draw(engine)
        except Exception as e:
            debug_log(f"[LogView] Draw failed: {e}")
