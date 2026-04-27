from styles import Style, DEFAULT_STYLE
from typing import Callable, List, Optional, Union
from utils import debug_log, get_visual_width


class BaseComponent:
    """所有组件的基类。

    坐标系说明：
        - pos=(row, col)，均从 0 开始。
        - 顶层组件：若组件没有父组件（直接通过 live.add() 添加），则 pos 为屏幕绝对坐标。
        - 子组件：pos 相对于父组件的内容原点。例如 Panel 内的子组件 (0,0) 对应边框内部的第一格。
        - 自动布局：VStack/HStack 等容器会根据子组件顺序自动计算其有效原点，通常忽略子组件自身的 pos。

    样式继承：子组件未指定的样式属性自动继承父组件。
    层级排序：layer 值越大越后绘制（越靠上层）。

    事件回调（直接赋值覆盖即可）：
        component.on_focus  = lambda: ...        # 获得焦点时触发
        component.on_blur   = lambda: ...        # 失去焦点时触发
        component.on_enter  = lambda: ...        # ENTER 键触发
        component.on_key    = lambda key: ...    # 其它按键触发，返回 False 可阻断默认行为
    """

    def __init__(
        self,
        pos: tuple = (0, 0),
        style: Optional[Style] = None,
        layer: int = 0,
        focusable: bool = False,
        visible: bool = True,
        id: str = None,
        children: List["BaseComponent"] = None,
        on_enter=None,
        on_key=None,
        on_focus=None,
        on_blur=None,
    ):
        try:
            self.pos = (int(pos[0]), int(pos[1]))
        except (TypeError, IndexError, ValueError):
            debug_log(f"[BaseComponent] Warning: Invalid pos {pos}, defaulting to (1, 1)")
            self.pos = (1, 1)

        self.style = style or Style()
        self.layer = layer
        self.focusable = focusable
        self.visible = visible
        self.id = id
        self.is_focused = False
        self.parent: Optional["BaseComponent"] = None
        self.children: List["BaseComponent"] = []

        if on_enter is not None:
            self.on_enter = on_enter
        if on_key is not None:
            self.on_key = on_key
        if on_focus is not None:
            self.on_focus = on_focus
        if on_blur is not None:
            self.on_blur = on_blur

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

    def add_child(self, child: "BaseComponent"):
        """将子组件挂载到本组件，子组件坐标将相对于本组件原点计算。"""
        if not isinstance(child, BaseComponent):
            debug_log("[BaseComponent] Error: child must be an instance of BaseComponent")
            return
        child.parent = self
        self.children.append(child)
        self.children.sort(key=lambda x: x.layer)

    def remove_child(self, child: "BaseComponent"):
        """从本组件移除子组件。"""
        try:
            self.children.remove(child)
            child.parent = None
        except ValueError:
            pass

    def find(self, id: str) -> Optional["BaseComponent"]:
        """在本组件的子树中深度优先查找第一个 id 匹配的组件，未找到返回 None。"""
        if self.id == id:
            return self
        for child in self.children:
            result = child.find(id)
            if result is not None:
                return result
        return None

    def get_absolute_pos(self) -> tuple:
        """递归计算本组件在屏幕上的绝对坐标 (row, col)。
        以父组件的 get_child_origin(self) 为基准，再加上自身 pos 偏移。"""
        try:
            if self.parent:
                py, px = self.parent.get_child_origin(self)
                return (py + self.pos[0], px + self.pos[1])
            return self.pos
        except Exception as e:
            debug_log(f"[BaseComponent] Error in coordinate resolution: {e}")
            return (1, 1)

    def get_child_origin(self, child: "BaseComponent") -> tuple:
        """返回指定子组件的坐标基准（绝对坐标）。
        默认等于自身绝对坐标；Panel 加入边框+padding；VStack/HStack 按子组件顺序累积偏移。"""
        return self.get_absolute_pos()

    def get_height(self) -> int:
        """返回本组件的视觉行高，供布局容器计算子组件位置使用。"""
        return 1

    def get_width(self) -> int:
        """返回本组件的视觉列宽，供布局容器计算子组件位置使用。"""
        return 1

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
        """递归绘制所有子组件，单个子组件异常不影响其余组件。visible=False 时跳过自身及所有子组件。"""
        if not self.visible:
            return
        for child in self.children:
            try:
                if child.visible:
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

    def __init__(
        self,
        pos=(0, 0),
        width=40,
        label="INPUT",
        style=None,
        layer=0,
        focus_style=None,
        on_enter=None,
        on_key=None,
    ):
        from theme import get_theme

        t = get_theme("InputBox")
        super().__init__(
            pos=pos, style=style, layer=layer, focusable=True, on_enter=on_enter, on_key=on_key
        )
        self.width = width
        self.label = label
        self.text = ""
        self.cursor_visible = True
        self._last_blink = 0
        self.focus_style = (
            focus_style if focus_style is not None else t.get("focus_style", Style(fg=220))
        )

    def get_height(self) -> int:
        return 3

    def get_width(self) -> int:
        return self.width

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
            border_style = eff_style.merge(self.focus_style) if self.is_focused else eff_style

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

            engine.push(ay, ax, top, border_style)
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

    def __init__(
        self,
        pos=(0, 0),
        label="BUTTON",
        width=None,
        style=None,
        layer=0,
        focus_style=None,
        on_enter=None,
        on_key=None,
    ):
        from theme import get_theme

        t = get_theme("Button")
        super().__init__(
            pos=pos, style=style, layer=layer, focusable=True, on_enter=on_enter, on_key=on_key
        )
        self.label = label
        self.width = width if width is not None else get_visual_width(label) + 4
        self.focus_style = (
            focus_style
            if focus_style is not None
            else t.get("focus_style", Style(fg=220, bold=True))
        )

    def get_height(self) -> int:
        return 1

    def get_width(self) -> int:
        return self.width

    def draw(self, engine):
        try:
            ay, ax = self.get_absolute_pos()
            eff_style = self.get_effective_style()
            inner = self.width - 4
            text = self.label[:inner].center(inner)
            if self.is_focused:
                display = f"[ {text} ]"
                btn_style = eff_style.merge(self.focus_style)
            else:
                display = f"  {text}  "
                btn_style = eff_style
            engine.push(ay, ax, display, btn_style)
            super().draw(engine)
        except Exception as e:
            debug_log(f"[Button] Draw failed: {e}")


class Box(BaseComponent):
    """矩形容器基类，支持自定义边框样式和背景填充。
    子组件 pos=(0,0) 为内容区左上角（边框内壁 + padding）。

    参数：
        border_style: 8个字符的字符串，索引对应关系为：
                      0:TL(左上), 1:TR(右上), 2:BL(左下), 3:BR(右下)
                      4:Top(上边), 5:Bottom(下边), 6:Left(左边), 7:Right(右边)
                      默认为 BOX_SINGLE。
        background_char: 填充背景的字符，默认为 " " (空格)。
    """

    def __init__(
        self,
        pos=(0, 0),
        width=20,
        height=5,
        border_style: str = None,
        background_char: str = " ",
        style=None,
        layer=0,
        padding=0,
        visible=True,
        children=None,
    ):
        from styles import BOX_SINGLE

        super().__init__(pos=pos, style=style, layer=layer, visible=visible, children=children)
        self.width = width
        self.height = height
        self.border_style = border_style or BOX_SINGLE
        self.background_char = background_char
        self.padding = padding

    def get_height(self) -> int:
        return self.height

    def get_width(self) -> int:
        return self.width

    def get_child_origin(self, child: "BaseComponent") -> tuple:
        py, px = self.get_absolute_pos()
        offset = 1 + self.padding
        return (py + offset, px + offset)

    def draw(self, engine):
        try:
            ay, ax = self.get_absolute_pos()
            eff = self.get_effective_style()

            # 1. 清理区域（含合成层）并填充背景
            engine.clear_rect(ay, ax, self.height, self.width, style=eff)
            if self.background_char != " ":
                engine.fill_rect(ay + 1, ax + 1, self.height - 2, self.width - 2, self.background_char, eff)

            # 2. 绘制边框
            engine.draw_box(ay, ax, self.height, self.width, eff, self.border_style)

            super().draw(engine)
        except Exception as e:
            debug_log(f"[{self.__class__.__name__}] Draw failed: {e}")


class Panel(Box):
    """带标题的 Box。

    示例：
        panel = Panel(pos=(1, 1), width=40, height=8, title="INFO",
                      border_style=BOX_DOUBLE, children=[...])
    """

    def __init__(
        self,
        pos=(0, 0),
        width=50,
        height=10,
        title="PANEL",
        border_style: str = None,
        background_char: str = " ",
        style=None,
        layer=0,
        padding=None,
        visible=True,
        children=None,
    ):
        from theme import get_theme

        t = get_theme("Panel")
        resolved_style = style if style is not None else t.get("style")
        res_padding = padding if padding is not None else t.get("padding", 0)

        super().__init__(

            pos=pos,
            width=width,
            height=height,
            border_style=border_style,
            background_char=background_char,
            style=resolved_style,
            layer=layer,
            padding=res_padding,
            visible=visible,
            children=children,
        )
        self.title = title

    def draw(self, engine):
        # 先利用 Box 的逻辑绘制背景和边框
        super().draw(engine)

        # 叠印标题
        try:
            ay, ax = self.get_absolute_pos()
            eff = self.get_effective_style()

            # 标题渲染逻辑：嵌入顶部边框
            title_txt = f" {self.title} "
            title_w = get_visual_width(title_txt)
            if title_w <= self.width - 4:
                # 居中对齐
                start_x = (self.width - title_w) // 2
                engine.push(ay, ax + start_x, title_txt, eff)
        except Exception as e:
            debug_log(f"[Panel] Title draw failed: {e}")


class Label(BaseComponent):
    """单行文本标签（轻量版）。支持静态字符串或 lambda，无标记解析。
    
    性能友好，适用于大量简单文本显示的场景。
    """

    def __init__(
        self,
        pos=(0, 0),
        text: Union[str, Callable[[], str]] = "",
        style=None,
        layer=0,
        width: int = None,
        align: str = "left",
    ):
        super().__init__(pos=pos, style=style, layer=layer)
        self._text = text
        self._width = width
        self.align = align

    def get_width(self) -> int:
        if self._width is not None:
            return self._width
        content = self._text() if callable(self._text) else self._text
        return get_visual_width(content)

    def draw(self, engine):
        try:
            content = self._text() if callable(self._text) else self._text
            if self._width is not None and self.align != "left":
                cw = get_visual_width(content)
                pad = max(0, self._width - cw)
                if self.align == "right":
                    content = " " * pad + content
                elif self.align == "center":
                    left = pad // 2
                    content = " " * left + content + " " * (pad - left)
            ay, ax = self.get_absolute_pos()
            engine.push(ay, ax, content, self.get_effective_style())
            super().draw(engine)
        except Exception as e:
            debug_log(f"[Label] Draw failed: {e}")


class Text(BaseComponent):
    """富文本组件。支持多行、对齐、以及类似 HTML 的标记解析。
    
    语法示例: 
        "<#highlight>重点</> 普通文本 <red bold>警告</>"
        支持换行符 `\n` 进行强制换行。

    特性：
        - 宽度感知：正确处理 CJK 字符。
        - 懒惰计算：仅在内容变化时重新解析。
    """

    def __init__(
        self,
        pos=(0, 0),
        text: Union[str, Callable[[], str]] = "",
        style=None,
        layer=0,
        width: int = None,
        align: str = "left",
        markup: bool = True,
    ):
        super().__init__(pos=pos, style=style, layer=layer)
        self._raw_text = text
        self._width = width
        self.align = align
        self.markup = markup
        
        # 缓存
        self._last_input = None
        self._line_segments = [] # List[List[Tuple[str, Style]]]
        self._visual_lines = []   # List[int] 每行视觉宽度

    def _update_cache(self):
        content = self._raw_text() if callable(self._raw_text) else self._raw_text
        if content == self._last_input:
            return content
            
        # 内容发生变化，重新解析
        from markup import parse_markup
        eff_style = self.get_effective_style()
        
        if self.markup:
            self._line_segments = parse_markup(content, eff_style)
        else:
            # 非标记模式，视为普通多行文本
            self._line_segments = [[(line, eff_style)] for line in content.split('\n')]
            
        # 计算每一行的总视觉宽度
        self._visual_lines = []
        for line in self._line_segments:
            w = sum(get_visual_width(txt) for txt, _ in line)
            self._visual_lines.append(w)
            
        self._last_input = content
        return content

    def get_height(self) -> int:
        self._update_cache()
        return len(self._line_segments)

    def get_width(self) -> int:
        if self._width is not None:
            return self._width
        self._update_cache()
        return max(self._visual_lines) if self._visual_lines else 0

    def draw(self, engine):
        try:
            self._update_cache()
            ay, ax = self.get_absolute_pos()
            target_w = self.get_width()
            
            for i, line in enumerate(self._line_segments):
                line_w = self._visual_lines[i]
                
                # 计算对齐偏移
                col_offset = 0
                if target_w > line_w:
                    if self.align == "right":
                        col_offset = target_w - line_w
                    elif self.align == "center":
                        col_offset = (target_w - line_w) // 2
                
                # 逐段渲染
                curr_x = ax + col_offset
                for txt, style in line:
                    engine.push(ay + i, curr_x, txt, style)
                    curr_x += get_visual_width(txt)
                    
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

    def __init__(
        self,
        pos=(0, 0),
        width=20,
        value: Union[float, Callable[[], float]] = 0.0,
        filled_style=None,
        empty_style=None,
        style=None,
        layer=0,
    ):
        from theme import get_theme

        t = get_theme("ProgressBar")
        super().__init__(pos=pos, style=style, layer=layer)
        self._value = value
        self.width = width
        self.filled_style = (
            filled_style
            if filled_style is not None
            else t.get("filled_style", Style(fg=(80, 200, 120)))
        )
        self.empty_style = (
            empty_style if empty_style is not None else t.get("empty_style", Style(fg=(60, 60, 60)))
        )

    def get_height(self) -> int:
        return 1

    def get_width(self) -> int:
        return self.width

    def draw(self, engine):
        try:
            v = max(0.0, min(1.0, self._value() if callable(self._value) else self._value))
            ay, ax = self.get_absolute_pos()
            inner = self.width - 5
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

    def get_height(self) -> int:
        return self.height

    def get_width(self) -> int:
        return self.width

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


class VStack(BaseComponent):
    """纵向堆叠容器。子组件按声明顺序从上到下排列，无需手写 pos。
    子组件的 pos 仍会叠加，可用于微调单个组件的位置。

    参数：
        gap: 子组件之间的行间距，默认 0。

    示例：
        VStack(pos=(1, 2), gap=1, children=[
            Text(text="标题"),
            InputBox(width=30, label="输入"),
            Button(label="提交"),
        ])
    """

    def __init__(
        self,
        pos=(0, 0),
        gap: int = 0,
        align: str = "left",
        reverse: bool = False,
        style=None,
        layer=0,
        visible=True,
        children=None,
    ):
        super().__init__(pos=pos, style=style, layer=layer, visible=visible, children=children)
        self.gap = gap
        self.align = align
        self.reverse = reverse

    def get_child_origin(self, child: "BaseComponent") -> tuple:
        py, px = self.get_absolute_pos()
        ordered = list(reversed(self.children)) if self.reverse else self.children
        idx = ordered.index(child)
        row = sum(c.get_height() + self.gap for c in ordered[:idx])
        col_offset = 0
        if self.align != "left":
            max_w = max((c.get_width() for c in self.children), default=0)
            cw = child.get_width()
            col_offset = (max_w - cw) // 2 if self.align == "center" else (max_w - cw)
        return (py + row, px + col_offset)

    def get_height(self) -> int:
        if not self.children:
            return 0
        return sum(c.get_height() for c in self.children) + self.gap * max(
            0, len(self.children) - 1
        )

    def get_width(self) -> int:
        return max((c.get_width() for c in self.children), default=0)


class HStack(BaseComponent):
    """横向堆叠容器。子组件按声明顺序从左到右排列，无需手写 pos。
    子组件的 pos 仍会叠加，可用于微调单个组件的位置。

    参数：
        gap: 子组件之间的列间距，默认 0。

    示例：
        HStack(pos=(1, 2), gap=2, children=[
            Button(label="确认", width=10),
            Button(label="取消", width=10),
        ])
    """

    def __init__(
        self,
        pos=(0, 0),
        gap: int = 0,
        align: str = "top",
        reverse: bool = False,
        style=None,
        layer=0,
        visible=True,
        children=None,
    ):
        super().__init__(pos=pos, style=style, layer=layer, visible=visible, children=children)
        self.gap = gap
        self.align = align
        self.reverse = reverse

    def get_child_origin(self, child: "BaseComponent") -> tuple:
        py, px = self.get_absolute_pos()
        ordered = list(reversed(self.children)) if self.reverse else self.children
        idx = ordered.index(child)
        col = sum(c.get_width() + self.gap for c in ordered[:idx])
        row_offset = 0
        if self.align != "top":
            max_h = max((c.get_height() for c in self.children), default=0)
            ch = child.get_height()
            row_offset = (max_h - ch) // 2 if self.align == "center" else (max_h - ch)
        return (py + row_offset, px + col)

    def get_height(self) -> int:
        return max((c.get_height() for c in self.children), default=0)

    def get_width(self) -> int:
        if not self.children:
            return 0
        return sum(c.get_width() for c in self.children) + self.gap * max(0, len(self.children) - 1)
