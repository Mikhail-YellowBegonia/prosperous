from .styles import Style, DEFAULT_STYLE
from typing import Callable, List, Optional, Union
from .utils import debug_log, get_visual_width, rect_overlaps
from .markup import parse_markup, wrap_segments


class BaseComponent:
    """所有组件的基类。

    坐标系说明：
        - pos=(row, col)，均从 0 开始。
        - 顶层组件：直接通过 live.add() 添加、没有父组件（parent is None）时，pos 即屏幕绝对坐标。
        - 子组件：pos 是相对于父组件内容原点（get_child_origin()）的偏移量。
          例如 Panel 内子组件 pos=(0,0) 对应边框+padding 内侧的第一格，而非屏幕 (0,0)。
        - 同一个 pos 字段在两种情况下含义不同，分水岭是 parent is None。
          需要在运行时获取屏幕绝对坐标时，请调用 get_absolute_pos()。
        - 自动布局：VStack/HStack 等容器覆盖 get_child_origin(child)，子组件的 pos
          仍然生效但是叠加在容器计算的原点之上，通常保持 (0,0) 即可。

    样式继承：子组件未指定的样式属性自动继承父组件。
    层级排序：layer 值越大越后绘制（越靠上层）。

    事件回调（直接赋值覆盖即可）：
        component.on_focus  = lambda: ...        # 获得焦点时触发
        component.on_blur   = lambda: ...        # 失去焦点时触发
        component.on_enter  = lambda: ...        # ENTER 键触发
        component.on_key    = lambda key: ...    # 其它按键触发，返回 True 可阻断后续行为
    """

    def __init__(
        self,
        pos: tuple = (0, 0),
        style: Optional[Style] = None,
        layer: int = 0,
        focusable: bool = False,
        visible: bool = True,
        clipping: bool = False,
        culling: bool = False,
        id: str = None,
        children: List["BaseComponent"] = None,
        focus_style: Optional[Style] = None,
        on_enter=None,
        on_key=None,
        on_focus=None,
        on_blur=None,
    ):
        self._pos = (0, 0)
        try:
            self._pos = (int(pos[0]), int(pos[1]))
        except (TypeError, IndexError, ValueError):
            debug_log(f"[BaseComponent] Warning: Invalid pos {pos}, defaulting to (0, 0)")
            self._pos = (0, 0)

        self.style = style or Style()
        self.focus_style = focus_style
        self.layer = layer
        self.focusable = focusable
        self.visible = visible
        self.clipping = clipping
        self.culling = culling
        self.id = id
        self.is_focused = False
        self.parent: Optional["BaseComponent"] = None
        self.children: List["BaseComponent"] = []
        
        self._abs_rect = (0, 0, 0, 0) # (y, x, h, w) 缓存
        self._needs_update = True     # 脏标记
        self._root = None             # 指向 Live 实例，用于动态注册焦点

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

    @property
    def pos(self) -> tuple:
        """获取组件相对于父容器内容原点的坐标 (row, col)。"""
        return self._pos

    @pos.setter
    def pos(self, value: tuple):
        """设置坐标并标记自身及子树为脏。"""
        try:
            new_pos = (int(value[0]), int(value[1]))
            if self._pos != new_pos:
                self._pos = new_pos
                self.set_dirty()
        except (TypeError, IndexError, ValueError):
            debug_log(f"[BaseComponent] Error: Invalid pos value {value}")

    def set_dirty(self):
        """标记本组件及其相关组件需要重新计算。
        向下传递：所有子组件的绝对位置都会改变。
        向上传递：父容器的布局（如总高度）可能需要重新计算。
        """
        # 向下传递：必须始终执行，因为即使父组件本身已经是脏的，
        # 如果是 scroll 改变，子组件的绝对坐标依然需要更新。
        for child in self.children:
            if not child._needs_update:
                child.set_dirty()

        if self._needs_update:
            return
            
        self._needs_update = True
        
        # 向上传递
        if self.parent:
            self.parent.set_dirty()

    def on_focus(self):
        """获得焦点时由 FocusManager 调用。可赋值覆盖以添加自定义行为。"""
        pass

    def on_blur(self):
        """失去焦点时由 FocusManager 调用。可赋值覆盖以添加自定义行为。"""
        pass

    def on_enter(self):
        """ENTER 键按下时由 FocusManager 调用。可赋值覆盖。"""
        pass

    def on_key(self, key: str) -> bool:
        """非方向键、非 ENTER 的按键到达组件前触发。返回 True 可阻断后续行为。"""
        return False

    def handle_input(self, key: str) -> bool:
        """处理到达本组件的按键，由子类实现。返回 True 表示该按键已被消费。"""
        return False

    def add_child(self, child: "BaseComponent"):
        """将子组件挂载到本组件，子组件坐标将相对于本组件原点计算。"""
        if not isinstance(child, BaseComponent):
            debug_log("[BaseComponent] Error: child must be an instance of BaseComponent")
            return
        child.parent = self
        self.children.append(child)
        self.children.sort(key=lambda x: x.layer)
        
        # 动态注册：如果父树已挂载到引擎，同步更新子树的 root 并注册焦点
        if self._root:
            self._root._attach_component(child)

    def remove_child(self, child: "BaseComponent"):
        """从本组件移除子组件，并清理其子树的 _root 引用和焦点注册。"""
        try:
            self.children.remove(child)
            child.parent = None
            if self._root:
                self._root._detach_component(child)
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

    def get_abs_rect(self) -> tuple:
        """获取并缓存本组件在屏幕上的绝对矩形区域 (y, x, h, w)。
        采用懒惰更新机制：仅在标记为脏时重新计算。"""
        if self._needs_update:
            try:
                ay, ax = self.get_absolute_pos()
                self._abs_rect = (ay, ax, self.get_height(), self.get_width())
                self._needs_update = False
            except Exception as e:
                debug_log(f"[BaseComponent] Error calculating absolute rect: {e}")
                return (0, 0, 0, 0)
        return self._abs_rect

    def _should_cull(self, engine) -> bool:
        """检查当前组件是否满足剔除条件（开启剔除且在视口外）。"""
        if not self.culling:
            return False
        clip = engine.get_current_clip()
        viewport = clip if clip else (0, 0, engine.cli_height, engine.cli_width)
        return not rect_overlaps(self.get_abs_rect(), viewport)

    def draw(self, engine):
        """标准绘制流程：可见性检查 -> 自动剔除 -> 裁剪开启 -> 绘制子级 -> 裁剪关闭。"""
        if not self.visible or self._should_cull(engine):
            return

        # 1. 开启裁剪 (Clipping)
        if self.clipping:
            # 子类（如 Box）可覆盖此逻辑以精确控制内容区裁剪
            engine.push_clip(*self.get_abs_rect())

        # 2. 绘制子组件
        for child in self.children:
            try:
                if child.visible:
                    child.draw(engine)
            except Exception as e:
                debug_log(f"[BaseComponent] Child component draw failed: {e}")

        # 3. 关闭裁剪
        if self.clipping:
            engine.pop_clip()


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
        from .theme import get_theme

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

    def handle_input(self, key: str) -> bool:
        from .input_handler import InputHandler

        try:
            if key == "BACKSPACE":
                self.text = self.text[:-1]
                return True
            elif key == "SPACE":
                if get_visual_width(self.text) < self.width - 3:
                    self.text += " "
                return True
            elif key not in InputHandler.CONTROL_KEYS and not key.startswith("SEQ("):
                if get_visual_width(self.text) + get_visual_width(key) <= self.width - 3:
                    self.text += key
                return True
        except Exception as e:
            debug_log(f"[InputBox] Input handle failed: {e}")
        return False

    def on_enter(self):
        self.text = ""

    def draw(self, engine):
        if not self.visible or self._should_cull(engine):
            return

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
        from .theme import get_theme

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
        if not self.visible or self._should_cull(engine):
            return

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
        clipping=False,
        culling=False,
        focus_style=None,
        children=None,
        **kwargs,
    ):
        from .styles import BOX_SINGLE

        super().__init__(
            pos=pos, 
            style=style, 
            layer=layer, 
            visible=visible, 
            clipping=clipping,
            culling=culling,
            focus_style=focus_style,
            children=children,
            **kwargs
        )
        self._width = width
        self._height = height
        self._padding = padding
        self.border_style = border_style or BOX_SINGLE
        self.background_char = background_char

    @property
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value: int):
        if self._width != value:
            self._width = value
            self.set_dirty()

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int):
        if self._height != value:
            self._height = value
            self.set_dirty()

    @property
    def padding(self) -> int:
        return self._padding

    @padding.setter
    def padding(self, value: int):
        if self._padding != value:
            self._padding = value
            self.set_dirty()

    def get_height(self) -> int:
        return self.height

    def get_width(self) -> int:
        return self.width

    def get_child_origin(self, child: "BaseComponent") -> tuple:
        py, px = self.get_absolute_pos()
        offset = 1 + self.padding
        return (py + offset, px + offset)

    def draw(self, engine):
        if not self.visible or self._should_cull(engine):
            return

        ay, ax = self.get_absolute_pos()
        eff = self.get_effective_style()
        if self.is_focused and self.focus_style:
            eff = eff.merge(self.focus_style)

        # 1. 清理区域并填充背景（不应受裁剪限制，以清理旧内容）
        try:
            engine.clear_rect(ay, ax, self.height, self.width, style=eff)
            if self.background_char != " ":
                engine.fill_rect(ay + 1, ax + 1, self.height - 2, self.width - 2, self.background_char, eff)
        except Exception as e:
            debug_log(f"[{self.__class__.__name__}] Background draw failed: {e}")

        # 2. 绘制边框
        try:
            engine.draw_box(ay, ax, self.height, self.width, eff, self.border_style)
        except Exception as e:
            debug_log(f"[{self.__class__.__name__}] Border draw failed (check border_style): {e}")

        # 3. 开启裁剪并绘制子组件
        try:
            if self.clipping:
                engine.push_clip(ay + 1, ax + 1, self.height - 2, self.width - 2)

            for child in self.children:
                if child.visible:
                    child.draw(engine)

            if self.clipping:
                engine.pop_clip()
        except Exception as e:
            debug_log(f"[{self.__class__.__name__}] Children draw failed: {e}")


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
        clipping=False,
        culling=False,
        focus_style=None,
        children=None,
        **kwargs,
    ):
        from .theme import get_theme

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
            clipping=clipping,
            culling=culling,
            focus_style=focus_style,
            children=children,
            **kwargs,
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


class ScrollBox(Box):
    """支持滚动的容器。
    内部通过修改子组件的坐标系原点实现偏移，配合 clipping 自动裁剪溢出部分。

    建议用法：
        ScrollBox -> VStack -> 多个子组件
    """

    def __init__(
        self,
        pos=(0, 0),
        width=40,
        height=10,
        scroll_x=0,
        scroll_y=0,
        border_style: str = None,
        background_char: str = " ",
        style=None,
        layer=0,
        padding=0,
        visible=True,
        clipping=True,  # 默认开启裁剪
        culling=True,
        focus_style=None,
        children=None,
        **kwargs,
    ):
        super().__init__(
            pos=pos,
            width=width,
            height=height,
            border_style=border_style,
            background_char=background_char,
            style=style,
            layer=layer,
            padding=padding,
            visible=visible,
            clipping=clipping,
            culling=culling,
            focus_style=focus_style,
            children=children,
            **kwargs,
        )
        self._scroll_x = scroll_x
        self._scroll_y = scroll_y
        self._scroll_anim_y = None  # Optional[Kinetic]
        self._scroll_anim_x = None  # Optional[Kinetic]

    @property
    def scroll_x(self) -> int:
        return self._scroll_x

    @scroll_x.setter
    def scroll_x(self, value: int):
        content_w = self._get_content_width()
        viewport_w = self.width - 2 - 2 * self.padding
        max_scroll = max(0, content_w - viewport_w)
        new_val = max(0, min(value, max_scroll))
        if self._scroll_x != new_val:
            self._scroll_x = new_val
            self.set_dirty()

    @property
    def scroll_y(self) -> int:
        return self._scroll_y

    @scroll_y.setter
    def scroll_y(self, value: int):
        content_h = self._get_content_height()
        viewport_h = self.height - 2 - 2 * self.padding
        max_scroll = max(0, content_h - viewport_h)
        new_val = max(0, min(value, max_scroll))
        if self._scroll_y != new_val:
            self._scroll_y = new_val
            self.set_dirty()

    def _get_content_height(self) -> int:
        """计算子组件总高度。"""
        if not self.children:
            return 0
        # 如果有多个子组件，取最大的底部边界
        return max((c.pos[0] + c.get_height() for c in self.children), default=0)

    def _get_content_width(self) -> int:
        """计算子组件总宽度。"""
        if not self.children:
            return 0
        return max((c.pos[1] + c.get_width() for c in self.children), default=0)

    def get_child_origin(self, child: "BaseComponent") -> tuple:
        """核心逻辑：覆写子组件坐标系，注入滚动偏移。"""
        py, px = self.get_absolute_pos()
        # 容器内容区起点 = ay + 1 + padding
        offset = 1 + self.padding
        return (py + offset - self.scroll_y, px + offset - self.scroll_x)

    def scroll(self, dy: int = 0, dx: int = 0):
        """立即移动视点。若有运行中的动画，取消之以保证按键响应优先。"""
        if dy != 0:
            self._scroll_anim_y = None
            self.scroll_y += dy
        if dx != 0:
            self._scroll_anim_x = None
            self.scroll_x += dx

    def scroll_into_view(self, component: "BaseComponent"):
        """调整 scroll_y 使 component 完整出现在可视区域内（动画版）。"""
        box_ay, _ = self.get_absolute_pos()
        content_top = box_ay + 1 + self.padding
        viewport_h = self.height - 2 - 2 * self.padding

        comp_abs_y = component.get_absolute_pos()[0]
        comp_h = component.get_height()

        # 还原为内容坐标系（消除当前 scroll_y 的影响）
        content_y = comp_abs_y - content_top + self.scroll_y

        if content_y < self.scroll_y:
            self.animate_scroll_to(target_y=content_y)
        elif content_y + comp_h > self.scroll_y + viewport_h:
            self.animate_scroll_to(target_y=content_y + comp_h - viewport_h)

    def animate_scroll_to(self, target_y: int = None, target_x: int = None):
        """以动画方式滚动到目标位置。需在主循环中调用 update(dt) 才会推进。
        若动画已在运行，直接更新目标（保留当前速度，平滑重定向）。
        """
        from .animation import Kinetic
        if target_y is not None:
            clamped = max(0, min(target_y, max(0, self._get_content_height() - (self.height - 2 - 2 * self.padding))))
            if self._scroll_anim_y is None:
                self._scroll_anim_y = Kinetic(float(self._scroll_y), stiffness=250, damping=25)
            self._scroll_anim_y.set_target(float(clamped))
        if target_x is not None:
            clamped = max(0, min(target_x, max(0, self._get_content_width() - (self.width - 2 - 2 * self.padding))))
            if self._scroll_anim_x is None:
                self._scroll_anim_x = Kinetic(float(self._scroll_x), stiffness=250, damping=25)
            self._scroll_anim_x.set_target(float(clamped))

    def update(self, dt: float):
        """推进滚动动画，应在主循环每帧调用。动画结束后自动清理。"""
        if self._scroll_anim_y is not None:
            self._scroll_anim_y.update(dt)
            self.scroll_y = self._scroll_anim_y.int_value
            if self._scroll_anim_y.done:
                self._scroll_anim_y = None
        if self._scroll_anim_x is not None:
            self._scroll_anim_x.update(dt)
            self.scroll_x = self._scroll_anim_x.int_value
            if self._scroll_anim_x.done:
                self._scroll_anim_x = None

    def handle_input(self, key: str) -> bool:
        """支持方向键滚动。"""
        if key == "UP":
            self.scroll(dy=-1)
            return True
        elif key == "DOWN":
            self.scroll(dy=1)
            return True
        elif key == "LEFT":
            self.scroll(dx=-1)
            return True
        elif key == "RIGHT":
            self.scroll(dx=1)
            return True
        return False

    def draw(self, engine):
        if not self.visible or self._should_cull(engine):
            return

        ay, ax = self.get_absolute_pos()
        eff = self.get_effective_style()
        if self.is_focused and self.focus_style:
            eff = eff.merge(self.focus_style)

        # 1. 清理区域并填充背景
        try:
            engine.clear_rect(ay, ax, self.height, self.width, style=eff)
            if self.background_char != " ":
                engine.fill_rect(ay + 1, ax + 1, self.height - 2, self.width - 2, self.background_char, eff)
        except Exception as e:
            debug_log(f"[{self.__class__.__name__}] Background draw failed: {e}")

        # 2. 绘制边框
        try:
            engine.draw_box(ay, ax, self.height, self.width, eff, self.border_style)
        except Exception as e:
            debug_log(f"[{self.__class__.__name__}] Border draw failed: {e}")

        # 3. 绘制简单滚动条指示器 (垂直)
        try:
            content_h = self._get_content_height()
            viewport_h = self.height - 2 - 2 * self.padding
            if content_h > viewport_h:
                # 计算滑块位置
                max_scroll = content_h - viewport_h
                ratio = self.scroll_y / max_scroll
                # 可用移动空间是 height - 2 (减去上下边框)
                bar_y = round(ratio * (self.height - 3))
                engine.push(ay + 1 + bar_y, ax + self.width - 1, "┃", eff)
        except Exception as e:
            debug_log(f"[ScrollBox] Scrollbar draw failed: {e}")

        # 4. 开启裁剪并绘制子组件
        try:
            if self.clipping:
                engine.push_clip(ay + 1, ax + 1, self.height - 2, self.width - 2)

            for child in self.children:
                if child.visible:
                    child.draw(engine)

            if self.clipping:
                engine.pop_clip()
        except Exception as e:
            debug_log(f"[{self.__class__.__name__}] Children draw failed: {e}")


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
        if not self.visible or self._should_cull(engine):
            return

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
        from .markup import parse_markup
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
        if not self.visible or self._should_cull(engine):
            return

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
        from .theme import get_theme

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
        if not self.visible or self._should_cull(engine):
            return

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
    """高性能、支持滚动和富文本折行的日志/文本视口。
    写入内容即固定，内部管理视觉行缓冲。

    属性：
        max_lines (int): 缓冲区最大保留行数。
        auto_scroll (bool): 收到新内容时是否自动滚动到底部。
        markup (bool): 是否解析 markup 标签。
    """

    def __init__(
        self,
        pos=(0, 0),
        width=40,
        height=10,
        max_lines=1000,
        markup=True,
        style=None,
        layer=0,
        focusable=True,
        auto_scroll=True,
    ):
        super().__init__(pos=pos, style=style, layer=layer, focusable=focusable)
        self._width = width
        self._height = height
        self.max_lines = max_lines
        self.markup = markup
        self.auto_scroll = auto_scroll
        
        self._buffer: List[List[Tuple[str, Style]]] = []  # 扁平化的视觉行缓冲
        self.scroll_offset = 0  # 0 表示在最顶端

    @property
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value: int):
        if self._width != value:
            self._width = value
            # 宽度改变需要重新折行（此处暂不实现全量重新折行，由于是 Append-only 容器）
            # 后续若有需求可在此添加重计算逻辑
            self.set_dirty()

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int):
        if self._height != value:
            self._height = value
            self.set_dirty()

    def get_height(self) -> int:
        return self.height

    def get_width(self) -> int:
        return self.width

    def append(self, text: str):
        """追加内容。支持多行字符串。自动进行折行处理。"""
        eff_style = self.get_effective_style()
        
        if self.markup:
            # 1. 解析 Markup (返回 List[List[Tuple]])
            parsed_raw_lines = parse_markup(text, eff_style)
        else:
            # 1. 简单分行
            parsed_raw_lines = [[(line, eff_style)] for line in text.split('\n')]

        # 2. 对每一原始行进行视觉折行
        for segments in parsed_raw_lines:
            wrapped = wrap_segments(segments, self.width)
            self._buffer.extend(wrapped)

        # 3. 维护缓冲区大小
        if len(self._buffer) > self.max_lines:
            overflow = len(self._buffer) - self.max_lines
            self._buffer = self._buffer[overflow:]

        # 4. 自动滚动逻辑
        if self.auto_scroll:
            self.scroll_to_end()

    def scroll(self, delta: int):
        """滚动视图。负数向上，正数向下。"""
        if not self._buffer:
            return
            
        max_offset = max(0, len(self._buffer) - self.height)
        new_offset = self.scroll_offset + delta
        self.scroll_offset = max(0, min(new_offset, max_offset))
        
        # 如果用户向上滚动，暂时关闭自动滚动
        if delta < 0:
            self.auto_scroll = False
        # 如果用户滚到了最底部，重新开启自动滚动
        elif self.scroll_offset >= max_offset:
            self.auto_scroll = True

    def scroll_to_end(self):
        """立即滚动到缓冲区末尾并恢复自动滚动。"""
        self.scroll_offset = max(0, len(self._buffer) - self.height)
        self.auto_scroll = True

    def handle_input(self, key: str) -> bool:
        """处理滚动按键。"""
        if key == "UP":
            self.scroll(-1)
            return True
        elif key == "DOWN":
            self.scroll(1)
            return True
        elif key == "PAGE_UP":
            self.scroll(-(self.height - 1))
            return True
        elif key == "PAGE_DOWN":
            self.scroll(self.height - 1)
            return True
        elif key == "HOME":
            self.scroll_offset = 0
            self.auto_scroll = False
            return True
        elif key == "END":
            self.scroll_to_end()
            return True
        return False

    def draw(self, engine):
        if not self.visible or self._should_cull(engine):
            return

        try:
            ay, ax = self.get_absolute_pos()
            eff = self.get_effective_style()
            
            # 1. 清理背景
            engine.clear_rect(ay, ax, self.height, self.width, style=eff)
            
            # 2. 获取可见切片
            visible_lines = self._buffer[self.scroll_offset : self.scroll_offset + self.height]
            
            # 3. 逐行渲染
            for i, line in enumerate(visible_lines):
                curr_x = ax
                for txt, style in line:
                    engine.push(ay + i, curr_x, txt, style)
                    curr_x += get_visual_width(txt)
            
            # 4. 绘制滚动条指示器（可选，为了轻量暂不实现复杂滑块）
            # 可以在此处简单 push 一个字符表示状态
            
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
        clipping=False,
        culling=False,
        focus_style=None,
        children=None,
        **kwargs,
    ):
        super().__init__(
            pos=pos, 
            style=style, 
            layer=layer, 
            visible=visible, 
            clipping=clipping,
            culling=culling,
            focus_style=focus_style,
            children=children,
            **kwargs
        )
        self._gap = gap
        self._align = align
        self._reverse = reverse

    @property
    def gap(self) -> int:
        return self._gap

    @gap.setter
    def gap(self, value: int):
        if self._gap != value:
            self._gap = value
            self.set_dirty()

    @property
    def align(self) -> str:
        return self._align

    @align.setter
    def align(self, value: str):
        if self._align != value:
            self._align = value
            self.set_dirty()

    @property
    def reverse(self) -> bool:
        return self._reverse

    @reverse.setter
    def reverse(self, value: bool):
        if self._reverse != value:
            self._reverse = value
            self.set_dirty()

    def get_child_origin(self, child: "BaseComponent") -> tuple:
        py, px = self.get_absolute_pos()
        ordered = list(reversed(self.children)) if self.reverse else self.children
        try:
            idx = ordered.index(child)
        except ValueError:
            return (py, px)
            
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
        clipping=False,
        culling=False,
        focus_style=None,
        children=None,
        **kwargs,
    ):
        super().__init__(
            pos=pos, 
            style=style, 
            layer=layer, 
            visible=visible, 
            clipping=clipping,
            culling=culling,
            focus_style=focus_style,
            children=children,
            **kwargs
        )
        self._gap = gap
        self._align = align
        self._reverse = reverse

    @property
    def gap(self) -> int:
        return self._gap

    @gap.setter
    def gap(self, value: int):
        if self._gap != value:
            self._gap = value
            self.set_dirty()

    @property
    def align(self) -> str:
        return self._align

    @align.setter
    def align(self, value: str):
        if self._align != value:
            self._align = value
            self.set_dirty()

    @property
    def reverse(self) -> bool:
        return self._reverse

    @reverse.setter
    def reverse(self, value: bool):
        if self._reverse != value:
            self._reverse = value
            self.set_dirty()

    def get_child_origin(self, child: "BaseComponent") -> tuple:
        py, px = self.get_absolute_pos()
        ordered = list(reversed(self.children)) if self.reverse else self.children
        try:
            idx = ordered.index(child)
        except ValueError:
            return (py, px)
            
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
