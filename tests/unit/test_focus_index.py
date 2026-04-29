"""
Unit tests for FocusSpatialIndex and FocusLayer.

覆盖：
  FocusSpatialIndex.build()
    - 空列表 → 无层
    - 无裁剪祖先的组件 → 全局层（clip_owner=None）
    - ScrollBox 内组件 → ScrollBox 层
    - 同一 ScrollBox 内的多个组件 → 同一层
    - 不同 ScrollBox 内的组件 → 不同层
    - 全局组件与 ScrollBox 内组件同时存在 → 两层
    - 嵌套 ScrollBox → 组件归属最近祖先
    - clipping=False 的 Box 不构成层边界
    - clipping=True 的 Box 构成层边界
    - rebuild 完全替换旧索引

  FocusLayer.clip_rect
    - 全局层 clip_rect 为 None
    - ScrollBox 裁剪矩形与 Box.draw() push_clip 公式一致
    - 原点 ScrollBox 的裁剪矩形
    - 偏移 ScrollBox 的裁剪矩形

  FocusSpatialIndex.get_layer()
    - 返回正确的层对象
    - 不在索引中的组件返回 None
    - 全局组件与容器内组件各归其层

  abs_rect 可达性
    - 层内每个组件均可调用 get_abs_rect() 并返回合法四元组
    - 位于 ScrollBox 内的组件 abs_rect 坐标正确（border offset）
"""

import sys
import os
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from prosperous import BaseComponent, Box, ScrollBox, VStack
from prosperous.interaction import FocusSpatialIndex, FocusLayer, FocusManager


# ── 测试辅助 ─────────────────────────────────────────────────────────────────


def _fc(pos=(0, 0), h=1, w=5) -> BaseComponent:
    """创建一个最简可焦点组件。"""
    c = BaseComponent(pos=pos, focusable=True)
    c.get_height = lambda: h
    c.get_width = lambda: w
    return c


# ── build() ──────────────────────────────────────────────────────────────────


class TestBuild:
    def test_empty_input_produces_no_layers(self):
        idx = FocusSpatialIndex()
        idx.build([])
        assert idx.layers == []

    def test_single_global_component(self):
        c = _fc()
        idx = FocusSpatialIndex()
        idx.build([c])
        assert len(idx.layers) == 1
        layer = idx.layers[0]
        assert layer.clip_owner is None
        assert c in layer.components

    def test_component_inside_scrollbox(self):
        sb = ScrollBox(pos=(0, 0), width=20, height=10)
        c = _fc()
        sb.add_child(c)

        idx = FocusSpatialIndex()
        idx.build([c])
        assert len(idx.layers) == 1
        assert idx.layers[0].clip_owner is sb

    def test_multiple_components_same_scrollbox_share_layer(self):
        sb = ScrollBox(pos=(0, 0), width=20, height=10)
        cs = [_fc() for _ in range(4)]
        for c in cs:
            sb.add_child(c)

        idx = FocusSpatialIndex()
        idx.build(cs)
        assert len(idx.layers) == 1
        assert set(idx.layers[0].components) == set(cs)

    def test_different_scrollboxes_produce_different_layers(self):
        sb1 = ScrollBox(pos=(0, 0), width=20, height=10)
        sb2 = ScrollBox(pos=(20, 0), width=20, height=10)
        c1 = _fc(); sb1.add_child(c1)
        c2 = _fc(); sb2.add_child(c2)

        idx = FocusSpatialIndex()
        idx.build([c1, c2])
        assert len(idx.layers) == 2
        assert idx.get_layer(c1) is not idx.get_layer(c2)
        assert idx.get_layer(c1).clip_owner is sb1
        assert idx.get_layer(c2).clip_owner is sb2

    def test_global_and_scrollbox_components_produce_two_layers(self):
        sb = ScrollBox(pos=(0, 0), width=20, height=10)
        c_in = _fc(); sb.add_child(c_in)
        c_out = _fc()

        idx = FocusSpatialIndex()
        idx.build([c_out, c_in])
        assert len(idx.layers) == 2
        assert idx.get_layer(c_out).clip_owner is None
        assert idx.get_layer(c_in).clip_owner is sb

    def test_nested_scrollboxes_use_nearest_ancestor(self):
        outer = ScrollBox(pos=(0, 0), width=40, height=20)
        inner = ScrollBox(pos=(0, 0), width=20, height=10)
        outer.add_child(inner)
        c = _fc(); inner.add_child(c)

        idx = FocusSpatialIndex()
        idx.build([c])
        assert idx.get_layer(c).clip_owner is inner   # 最近祖先，非 outer

    def test_clipping_false_box_does_not_create_boundary(self):
        box = Box(pos=(0, 0), width=20, height=10, clipping=False)
        c = _fc(); box.add_child(c)

        idx = FocusSpatialIndex()
        idx.build([c])
        assert idx.get_layer(c).clip_owner is None    # Box 不裁剪 → 全局层

    def test_clipping_true_box_creates_boundary(self):
        box = Box(pos=(0, 0), width=20, height=10, clipping=True)
        c = _fc(); box.add_child(c)

        idx = FocusSpatialIndex()
        idx.build([c])
        assert idx.get_layer(c).clip_owner is box

    def test_rebuild_replaces_previous_index(self):
        sb = ScrollBox(pos=(0, 0), width=20, height=10)
        c1 = _fc(); sb.add_child(c1)
        c2 = _fc()   # 全局，不在任何容器内

        idx = FocusSpatialIndex()
        idx.build([c1])
        assert idx.get_layer(c1) is not None

        idx.build([c2])   # 重建，c1 不再在索引中
        assert idx.get_layer(c2) is not None
        assert idx.get_layer(c1) is None

    def test_layer_components_order_matches_input_order(self):
        sb = ScrollBox(pos=(0, 0), width=20, height=10)
        cs = [_fc() for _ in range(3)]
        for c in cs:
            sb.add_child(c)

        idx = FocusSpatialIndex()
        idx.build(cs)
        assert idx.layers[0].components == cs


# ── clip_rect ─────────────────────────────────────────────────────────────────


class TestClipRect:
    def test_global_layer_clip_rect_is_none(self):
        c = _fc()
        idx = FocusSpatialIndex()
        idx.build([c])
        assert idx.get_layer(c).clip_rect is None

    def test_scrollbox_at_origin(self):
        # ScrollBox at (0,0), w=10, h=6
        # push_clip: (0+1, 0+1, 6-2, 10-2) = (1, 1, 4, 8)
        sb = ScrollBox(pos=(0, 0), width=10, height=6)
        c = _fc(); sb.add_child(c)

        idx = FocusSpatialIndex()
        idx.build([c])
        assert idx.get_layer(c).clip_rect == (1, 1, 4, 8)

    def test_scrollbox_at_offset(self):
        # ScrollBox at (5, 10), w=40, h=20
        # push_clip: (6, 11, 18, 38)
        sb = ScrollBox(pos=(5, 10), width=40, height=20)
        c = _fc(); sb.add_child(c)

        idx = FocusSpatialIndex()
        idx.build([c])
        assert idx.get_layer(c).clip_rect == (6, 11, 18, 38)

    def test_clipping_box_clip_rect(self):
        # Box (clipping=True) at (2, 3), w=14, h=8
        # push_clip: (3, 4, 6, 12)
        box = Box(pos=(2, 3), width=14, height=8, clipping=True)
        c = _fc(); box.add_child(c)

        idx = FocusSpatialIndex()
        idx.build([c])
        assert idx.get_layer(c).clip_rect == (3, 4, 6, 12)

    def test_nested_scrollboxes_clip_rect_belongs_to_inner(self):
        outer = ScrollBox(pos=(0, 0), width=40, height=20)
        inner = ScrollBox(pos=(0, 0), width=20, height=10)
        outer.add_child(inner)
        c = _fc(); inner.add_child(c)

        idx = FocusSpatialIndex()
        idx.build([c])
        layer = idx.get_layer(c)
        # inner 是 outer 的子组件，绝对位置 = outer.get_child_origin(inner) = (1, 1)
        # clip_rect = (inner_ay+1, inner_ax+1, h-2, w-2) = (2, 2, 8, 18)
        assert layer.clip_rect == (2, 2, 8, 18)


# ── get_layer() ───────────────────────────────────────────────────────────────


class TestGetLayer:
    def test_returns_none_for_unknown_component(self):
        idx = FocusSpatialIndex()
        idx.build([])
        assert idx.get_layer(_fc()) is None

    def test_returns_correct_layer_for_global_component(self):
        c = _fc()
        idx = FocusSpatialIndex()
        idx.build([c])
        layer = idx.get_layer(c)
        assert layer is not None
        assert layer.clip_owner is None

    def test_returns_correct_layer_for_container_component(self):
        sb = ScrollBox(pos=(0, 0), width=20, height=10)
        c = _fc(); sb.add_child(c)
        idx = FocusSpatialIndex()
        idx.build([c])
        assert idx.get_layer(c).clip_owner is sb

    def test_two_components_in_different_layers_get_different_objects(self):
        sb = ScrollBox(pos=(0, 0), width=20, height=10)
        c_in = _fc(); sb.add_child(c_in)
        c_out = _fc()
        idx = FocusSpatialIndex()
        idx.build([c_in, c_out])
        assert idx.get_layer(c_in) is not idx.get_layer(c_out)

    def test_two_components_in_same_layer_get_same_object(self):
        sb = ScrollBox(pos=(0, 0), width=20, height=10)
        c1, c2 = _fc(), _fc()
        sb.add_child(c1); sb.add_child(c2)
        idx = FocusSpatialIndex()
        idx.build([c1, c2])
        assert idx.get_layer(c1) is idx.get_layer(c2)


# ── abs_rect 可达性 ────────────────────────────────────────────────────────────


class TestAbsRectAccessibility:
    def test_global_component_abs_rect_is_valid(self):
        c = _fc(pos=(3, 7))
        idx = FocusSpatialIndex()
        idx.build([c])

        y, x, h, w = c.get_abs_rect()
        assert (y, x) == (3, 7)
        assert h == 1
        assert w == 5

    def test_scrollbox_component_abs_rect_offset_by_border(self):
        # ScrollBox at (0,0), padding=0 → content origin (1,1)
        sb = ScrollBox(pos=(0, 0), width=20, height=10, padding=0)
        c = _fc(pos=(0, 0)); sb.add_child(c)
        idx = FocusSpatialIndex()
        idx.build([c])

        y, x, h, w = c.get_abs_rect()
        assert y == 1   # border offset
        assert x == 1
        assert h == 1
        assert w == 5

    def test_scrollbox_with_padding_offsets_correctly(self):
        # ScrollBox at (0,0), padding=2 → content origin (1+2, 1+2) = (3, 3)
        sb = ScrollBox(pos=(0, 0), width=20, height=10, padding=2)
        c = _fc(pos=(0, 0)); sb.add_child(c)
        idx = FocusSpatialIndex()
        idx.build([c])

        y, x, h, w = c.get_abs_rect()
        assert y == 3
        assert x == 3

    def test_all_layer_components_have_positive_dimensions(self):
        sb = ScrollBox(pos=(2, 3), width=30, height=15, padding=0)
        cs = [_fc() for _ in range(5)]
        for c in cs:
            sb.add_child(c)

        idx = FocusSpatialIndex()
        idx.build(cs)
        layer = idx.get_layer(cs[0])

        for comp in layer.components:
            y, x, h, w = comp.get_abs_rect()
            assert h > 0
            assert w > 0

    def test_vstack_children_abs_rect_accessible_via_index(self):  # noqa: E501
        # ScrollBox → VStack → [c0, c1, c2]，各高 1，间距 0
        sb = ScrollBox(pos=(0, 0), width=20, height=15, padding=0)
        vs = VStack(gap=0)
        sb.add_child(vs)
        cs = [_fc() for _ in range(3)]
        for c in cs:
            vs.add_child(c)

        # 先暖缓存，避免 dirty 传播的边界情况影响测试结果
        sb.get_abs_rect()
        vs.get_abs_rect()
        for c in cs:
            c.get_abs_rect()

        idx = FocusSpatialIndex()
        idx.build(cs)

        # content origin = (1, 1)；VStack 各项紧密堆叠
        rects = [c.get_abs_rect() for c in cs]
        assert rects[0][0] == 1   # c0 at row 1
        assert rects[1][0] == 2   # c1 at row 2
        assert rects[2][0] == 3   # c2 at row 3


# ── find_next() ───────────────────────────────────────────────────────────────


def _vstack_in_scrollbox(n, *, row=0, col=0, sb_h=30, sb_w=20):
    """构造 ScrollBox → VStack → n 个组件（各高 1，暖缓存后返回）。"""
    sb = ScrollBox(pos=(row, col), width=sb_w, height=sb_h, padding=0)
    vs = VStack(gap=0)
    sb.add_child(vs)
    items = [_fc() for _ in range(n)]
    for item in items:
        vs.add_child(item)
    # 暖缓存：确保 dirty 传播正确
    sb.get_abs_rect(); vs.get_abs_rect()
    for item in items:
        item.get_abs_rect()
    return sb, items


class TestFindNext:
    def test_down_returns_next_item_below(self):
        _, items = _vstack_in_scrollbox(4)
        idx = FocusSpatialIndex()
        idx.build(items)
        assert idx.find_next(items[0], "DOWN") is items[1]
        assert idx.find_next(items[1], "DOWN") is items[2]
        assert idx.find_next(items[2], "DOWN") is items[3]

    def test_up_returns_next_item_above(self):
        _, items = _vstack_in_scrollbox(4)
        idx = FocusSpatialIndex()
        idx.build(items)
        assert idx.find_next(items[3], "UP") is items[2]
        assert idx.find_next(items[2], "UP") is items[1]
        assert idx.find_next(items[1], "UP") is items[0]

    def test_down_at_last_returns_none(self):
        _, items = _vstack_in_scrollbox(3)
        idx = FocusSpatialIndex()
        idx.build(items)
        assert idx.find_next(items[2], "DOWN") is None

    def test_up_at_first_returns_none(self):
        _, items = _vstack_in_scrollbox(3)
        idx = FocusSpatialIndex()
        idx.build(items)
        assert idx.find_next(items[0], "UP") is None

    def test_right_finds_component_to_the_right(self):
        # 三个组件横向排列（pos 手动设置）
        c1 = _fc(pos=(0, 0))
        c2 = _fc(pos=(0, 8))
        c3 = _fc(pos=(0, 16))
        idx = FocusSpatialIndex()
        idx.build([c1, c2, c3])
        assert idx.find_next(c1, "RIGHT") is c2
        assert idx.find_next(c2, "RIGHT") is c3

    def test_left_finds_component_to_the_left(self):
        c1 = _fc(pos=(0, 0))
        c2 = _fc(pos=(0, 8))
        c3 = _fc(pos=(0, 16))
        idx = FocusSpatialIndex()
        idx.build([c1, c2, c3])
        assert idx.find_next(c3, "LEFT") is c2
        assert idx.find_next(c2, "LEFT") is c1

    def test_prefers_aligned_candidate_over_diagonal(self):
        # c_target 正下方，c_diag 斜下方较近——应选 c_target
        c_cur    = _fc(pos=(0,  5))
        c_target = _fc(pos=(4,  5))   # 正下方 4 格，副轴距离 0
        c_diag   = _fc(pos=(2,  0))   # 斜下方，主轴 2，副轴 5 → score=12
        # c_target: primary=4, secondary=0 → score=4
        idx = FocusSpatialIndex()
        idx.build([c_cur, c_target, c_diag])
        assert idx.find_next(c_cur, "DOWN") is c_target

    def test_single_component_layer_returns_none(self):
        c = _fc()
        idx = FocusSpatialIndex()
        idx.build([c])
        assert idx.find_next(c, "DOWN") is None

    def test_component_not_in_index_returns_none(self):
        c1, c2 = _fc(), _fc()
        idx = FocusSpatialIndex()
        idx.build([c1])
        assert idx.find_next(c2, "DOWN") is None

    def test_cross_layer_components_not_candidates(self):
        # c_in 在 ScrollBox 内，c_out 在全局层
        # 从 c_in 向下导航，不应选到跨层的 c_out
        sb = ScrollBox(pos=(0, 0), width=20, height=30, padding=0)
        c_in = _fc(pos=(0, 0)); sb.add_child(c_in)
        c_out = _fc(pos=(5, 0))   # 全局层，位置更低
        sb.get_abs_rect(); c_in.get_abs_rect()

        idx = FocusSpatialIndex()
        idx.build([c_in, c_out])
        # c_in 的层只含 c_in 自己
        assert idx.find_next(c_in, "DOWN") is None


# ── FocusManager 集成 ─────────────────────────────────────────────────────────


class TestFocusManagerSpatialIntegration:
    def _make_fm_with_vstack(self, n):
        """在 ScrollBox VStack 中创建 n 个组件并注册到 FocusManager。"""
        sb, items = _vstack_in_scrollbox(n)
        fm = FocusManager()
        for item in items:
            fm.add_component(item)
        return fm, items

    def test_arrow_down_moves_spatially(self):
        fm, items = self._make_fm_with_vstack(4)
        # 初始焦点在 items[0]
        fm.handle_input("DOWN")
        assert fm.get_focused() is items[1]
        fm.handle_input("DOWN")
        assert fm.get_focused() is items[2]

    def test_arrow_up_moves_spatially(self):
        fm, items = self._make_fm_with_vstack(4)
        fm.handle_input("DOWN")
        fm.handle_input("DOWN")   # 到 items[2]
        fm.handle_input("UP")
        assert fm.get_focused() is items[1]

    def test_arrow_down_at_last_stays(self):
        fm, items = self._make_fm_with_vstack(3)
        fm.handle_input("DOWN")
        fm.handle_input("DOWN")   # 到 items[2]（最后一项）
        fm.handle_input("DOWN")   # 无候选，退回线性循环 → wrap 到 items[0]
        # 退回线性：(2+1) % 3 = 0
        assert fm.get_focused() is items[0]

    def test_tab_still_cycles_linearly(self):
        fm, items = self._make_fm_with_vstack(3)
        fm.handle_input("TAB")
        assert fm.get_focused() is items[1]
        fm.handle_input("TAB")
        assert fm.get_focused() is items[2]
        fm.handle_input("TAB")   # 线性 wrap
        assert fm.get_focused() is items[0]
