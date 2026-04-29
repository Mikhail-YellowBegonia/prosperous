from typing import Dict, List, Optional
from .components import BaseComponent


class FocusLayer:
    """由同一裁剪容器管辖的可焦点组件集合，是空间导航的基本单元。

    clip_owner is None  → 全局层（组件没有任何 clipping=True 祖先）
    clip_rect  is None  → 无裁剪边界（全屏可见）
    """

    def __init__(self, clip_owner: Optional[BaseComponent], clip_rect: Optional[tuple]):
        self.clip_owner = clip_owner  # clipping=True 的容器；None 表示全局层
        self.clip_rect = clip_rect    # (y, x, h, w)；None 表示无裁剪
        self.components: List[BaseComponent] = []

    def __repr__(self) -> str:
        owner = type(self.clip_owner).__name__ if self.clip_owner else "Global"
        return f"FocusLayer({owner}, {len(self.components)} comps)"


class FocusSpatialIndex:
    """基于 abs_rect 的分层焦点空间索引。

    将 focusable 组件按其最近 clipping=True 祖先分层，每层构成一个 FocusLayer。
    同层内所有组件均可参与方向键导航（含当前被裁剪在视口外的组件）；
    跨层导航由父层逻辑处理，从根本上消除扁平索引在 ScrollBox
    边界处"无法导航到下一项"的问题。

    用法：
        idx = FocusSpatialIndex()
        idx.build(focus_manager._components)

        layer = idx.get_layer(some_button)
        candidates = [(c, c.get_abs_rect()) for c in layer.components]
    """

    def __init__(self):
        self._layers: List[FocusLayer] = []
        self._comp_to_layer: Dict[BaseComponent, FocusLayer] = {}

    # ── 构建 ──────────────────────────────────────────────────────────────────

    def build(self, components: List[BaseComponent]) -> None:
        """从 focusable 组件列表重建索引。O(n × depth)，n 为组件数。"""
        self._layers.clear()
        self._comp_to_layer.clear()

        owner_to_layer: Dict[Optional[BaseComponent], FocusLayer] = {}

        for comp in components:
            owner = self._find_clip_ancestor(comp)

            if owner not in owner_to_layer:
                clip_rect = self._clip_rect_of(owner) if owner is not None else None
                layer = FocusLayer(clip_owner=owner, clip_rect=clip_rect)
                owner_to_layer[owner] = layer
                self._layers.append(layer)

            layer = owner_to_layer[owner]
            layer.components.append(comp)
            self._comp_to_layer[comp] = layer

    # ── 查询 ──────────────────────────────────────────────────────────────────

    @property
    def layers(self) -> List[FocusLayer]:
        """当前所有层（按 build 时遍历顺序）。"""
        return list(self._layers)

    def get_layer(self, component: BaseComponent) -> Optional[FocusLayer]:
        """返回组件所属的层；不在索引中则返回 None。"""
        return self._comp_to_layer.get(component)

    def find_next(self, current: BaseComponent, direction: str) -> Optional[BaseComponent]:
        """在 current 所在层内，沿 direction 方向查找最近的焦点候选组件。

        算法：
          1. 过滤出严格位于正确半平面的候选（中心点坐标比较）
          2. 以「主轴距离 + 副轴距离 × 2」加权评分，取最小值
        返回最优候选；同层内无候选则返回 None。
        """
        layer = self.get_layer(current)
        if layer is None or len(layer.components) <= 1:
            return None

        cy_r, cx_r, ch, cw = current.get_abs_rect()
        cy = cy_r + ch / 2
        cx = cx_r + cw / 2

        best: Optional[BaseComponent] = None
        best_score = float("inf")

        for comp in layer.components:
            if comp is current:
                continue
            ry, rx, rh, rw = comp.get_abs_rect()
            ey = ry + rh / 2
            ex = rx + rw / 2

            # 严格半平面过滤
            if direction == "DOWN" and ey <= cy:
                continue
            elif direction == "UP" and ey >= cy:
                continue
            elif direction == "RIGHT" and ex <= cx:
                continue
            elif direction == "LEFT" and ex >= cx:
                continue

            # 主轴距离 + 副轴距离加权评分
            if direction in ("DOWN", "UP"):
                primary = abs(ey - cy)
                secondary = abs(ex - cx)
            else:
                primary = abs(ex - cx)
                secondary = abs(ey - cy)

            score = primary + secondary * 2.0
            if score < best_score:
                best_score = score
                best = comp

        return best

    # ── 静态工具 ───────────────────────────────────────────────────────────────

    @staticmethod
    def _find_clip_ancestor(component: BaseComponent) -> Optional[BaseComponent]:
        """向上遍历父链，返回最近的 clipping=True 祖先；无则返回 None。"""
        parent = component.parent
        while parent is not None:
            if getattr(parent, "clipping", False):
                return parent
            parent = parent.parent
        return None

    @staticmethod
    def _clip_rect_of(container: BaseComponent) -> tuple:
        """计算容器的裁剪矩形，与 Box.draw() 中 push_clip 保持一致。
        公式：(ay+1, ax+1, h-2, w-2)，即去掉上下左右各一格边框。
        """
        ay, ax = container.get_absolute_pos()
        return (ay + 1, ax + 1, container.get_height() - 2, container.get_width() - 2)


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
        self._spatial_index: FocusSpatialIndex = FocusSpatialIndex()

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

    def remove_component(self, component: BaseComponent):
        """从当前焦点组移除组件。若该组件持有焦点，自动将焦点移交给后继。"""
        if component not in self._components:
            return
        idx = self._components.index(component)
        was_focused = (idx == self._focused_index)
        if was_focused:
            component.is_focused = False
            component.on_blur()
        self._components.remove(component)
        if not self._components:
            self._focused_index = -1
        elif was_focused:
            self._focused_index = min(idx, len(self._components) - 1)
            new = self.get_focused()
            if new:
                new.is_focused = True
                new.on_focus()
        elif idx < self._focused_index:
            self._focused_index -= 1

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
        """方向键焦点导航。
        优先使用空间索引在同层内查找方向候选；若同层无候选则退回线性循环。
        TAB/SHIFT_TAB 不经此方法，仍走 handle_input 中的线性逻辑。
        """
        if not self._components:
            return

        current = self.get_focused()

        # ── 阶段一：尝试空间导航 ──────────────────────────────────────────────
        if current is not None:
            self._spatial_index.build(self._components)
            next_comp = self._spatial_index.find_next(current, direction)
            if next_comp is not None:
                current.is_focused = False
                current.on_blur()
                self._focused_index = self._components.index(next_comp)
                next_comp.is_focused = True
                next_comp.on_focus()
                self._scroll_to_component(next_comp)
                return

        # ── 阶段二：退回线性循环（无布局信息或边界情况）─────────────────────
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
            self._scroll_to_component(new)

    def _scroll_to_component(self, component: BaseComponent):
        """向上遍历父链，找到最近的 ScrollBox 祖先并要求其将 component 滚入视野。"""
        p = component.parent
        while p is not None:
            if hasattr(p, "scroll_into_view"):
                p.scroll_into_view(component)
                break
            p = p.parent

    def handle_input(self, key: str):
        focused = self.get_focused()
        if not focused:
            return

        # 1. 优先级最高：TAB 键强制切换焦点（不受组件拦截影响）
        if key == "TAB":
            self.move_focus("DOWN")
            return
        if key == "SHIFT_TAB": # 部分终端支持
            self.move_focus("UP")
            return

        # 2. 拦截层：让组件优先处理（包括方向键、ENTER 等）
        if focused.on_key(key):
            return
            
        if focused.handle_input(key):
            return

        # 3. 默认行为层：如果组件没处理，则执行全局行为
        if key in ["UP", "DOWN", "LEFT", "RIGHT"]:
            self.move_focus(key)
        elif key == "ENTER":
            focused.on_enter()
