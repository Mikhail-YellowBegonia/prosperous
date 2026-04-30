from typing import Dict, List, Optional
from .components import BaseComponent


class FocusNode:
    __slots__ = ("component", "children", "parent")

    def __init__(self, component: Optional[BaseComponent], parent: Optional["FocusNode"] = None):
        self.component = component
        self.children: List[FocusNode] = []
        self.parent = parent
        if parent is not None:
            parent.children.append(self)


class FocusLayer:
    clip_owner: Optional[BaseComponent]
    clip_rect: Optional[tuple]
    components: List[BaseComponent]

    def __init__(self, clip_owner: Optional[BaseComponent], clip_rect: Optional[tuple]):
        self.clip_owner = clip_owner
        self.clip_rect = clip_rect
        self.components: List[BaseComponent] = []

    def __repr__(self) -> str:
        owner = type(self.clip_owner).__name__ if self.clip_owner else "Global"
        return f"FocusLayer({owner}, {len(self.components)} comps)"


class FocusSpatialIndex:
    def __init__(self):
        self._layers: List[FocusLayer] = []
        self._comp_to_layer: Dict[BaseComponent, FocusLayer] = {}

    def build(self, components: List[BaseComponent]) -> None:
        self._layers.clear()
        self._comp_to_layer.clear()

        owner_to_layer: Dict[Optional[BaseComponent], FocusLayer] = {}

        for comp in components:
            owner = self._find_clip_ancestor(comp)

            if owner not in owner_to_layer:
                clip_rect = owner.get_clip_rect() if owner is not None else None
                layer = FocusLayer(clip_owner=owner, clip_rect=clip_rect)
                owner_to_layer[owner] = layer
                self._layers.append(layer)

            layer = owner_to_layer[owner]
            layer.components.append(comp)
            self._comp_to_layer[comp] = layer

    @property
    def layers(self) -> List[FocusLayer]:
        return list(self._layers)

    def get_layer(self, component: BaseComponent) -> Optional[FocusLayer]:
        return self._comp_to_layer.get(component)

    def find_next(self, current: BaseComponent, direction: str) -> Optional[BaseComponent]:
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

            if direction == "DOWN" and ey <= cy:
                continue
            elif direction == "UP" and ey >= cy:
                continue
            elif direction == "RIGHT" and ex <= cx:
                continue
            elif direction == "LEFT" and ex >= cx:
                continue

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

    @staticmethod
    def _find_clip_ancestor(component: BaseComponent) -> Optional[BaseComponent]:
        parent = component.parent
        while parent is not None:
            if getattr(parent, "clipping", False):
                return parent
            parent = parent.parent
        return None


class FocusManager:
    def __init__(self):
        self._tree_root = FocusNode(None)
        self._focused: Optional[FocusNode] = None
        self._node_map: Dict[BaseComponent, FocusNode] = {}
        self._modal_stack: List[tuple] = []
        self._spatial_index = FocusSpatialIndex()
        self._spatial_dirty = False

    @property
    def _components(self) -> List[BaseComponent]:
        result = []

        def _walk(node):
            if node.component is not None:
                result.append(node.component)
            for child in node.children:
                _walk(child)

        _walk(self._tree_root)
        return result

    @property
    def _stack(self):
        return self._modal_stack

    def _ensure_spatial_index(self):
        if self._spatial_dirty:
            self._spatial_index.build(self._components)
            self._spatial_dirty = False

    def _focus_node(self, node: FocusNode):
        old = self._focused
        if old is old and old is not None and old.component is not None:
            old.component.is_focused = False
        self._focused = node
        if node.component is not None:
            node.component.is_focused = True

    def _insert_node(self, component: BaseComponent) -> FocusNode:
        parent_comp = component.parent
        while parent_comp is not None:
            parent_node = self._node_map.get(parent_comp)
            if parent_node is not None:
                node = FocusNode(component, parent_node)
                self._node_map[component] = node
                self._spatial_dirty = True
                return node
            parent_comp = parent_comp.parent

        node = FocusNode(component, self._tree_root)
        self._node_map[component] = node
        self._spatial_dirty = True
        return node

    @staticmethod
    def _dfs_first(root: FocusNode) -> Optional[FocusNode]:
        if root.children:
            return root.children[0]
        return None

    @staticmethod
    def _dfs_last(root: FocusNode) -> Optional[FocusNode]:
        if root.children:
            return root.children[-1]
        return None

    def _dfs_next(self, node: FocusNode) -> Optional[FocusNode]:
        if node.children:
            return node.children[0]
        current = node
        while current.parent is not None:
            siblings = current.parent.children
            idx = siblings.index(current)
            if idx + 1 < len(siblings):
                return siblings[idx + 1]
            current = current.parent
        if self._tree_root.children:
            return self._tree_root.children[0]
        return None

    def _dfs_prev(self, node: FocusNode) -> Optional[FocusNode]:
        if node.parent is not None:
            siblings = node.parent.children
            idx = siblings.index(node)
            if idx > 0:
                prev = siblings[idx - 1]
                while prev.children:
                    prev = prev.children[-1]
                return prev
            if node.parent is not self._tree_root:
                return node.parent
        if self._tree_root.children:
            last = self._tree_root.children[-1]
            while last.children:
                last = last.children[-1]
            return last
        return None

    def _dfs_all_visible(self) -> List[FocusNode]:
        result = []

        def _walk(node):
            if node.component is not None and node.component.visible:
                result.append(node)
            for child in node.children:
                _walk(child)

        _walk(self._tree_root)
        return result

    def _find_first_leaf_child(self, node: FocusNode) -> Optional[FocusNode]:
        if not node.children:
            return node
        return self._find_first_leaf_child(node.children[0])

    def _find_node_by_component(self, comp: BaseComponent) -> Optional[FocusNode]:
        return self._node_map.get(comp)

    def _remove_tree(self, root: FocusNode):
        for child in root.children:
            self._remove_tree(child)
        if root.component is not None:
            self._node_map.pop(root.component, None)
        root.children.clear()
        root.parent = None

    def _rebuild_node_map(self, root: FocusNode):
        if root.component is not None:
            self._node_map[root.component] = root
        for child in root.children:
            self._rebuild_node_map(child)

    def add_component(self, component: BaseComponent):
        if component in self._node_map:
            return
        node = self._insert_node(component)
        if self._focused is None:
            self._focus_node(node)

    def push_group(self, components: List[BaseComponent]):
        old_root = self._tree_root
        old_focused = self._focused

        if self._focused is not None and self._focused.component is not None:
            self._focused.component.is_focused = False

        self._tree_root = FocusNode(None)
        self._node_map.clear()
        self._focused = None
        self._spatial_dirty = True

        for c in components:
            self.add_component(c)

        self._modal_stack.append((old_root, old_focused))

    def pop_group(self):
        if not self._modal_stack:
            return

        if self._focused is not None and self._focused.component is not None:
            self._focused.component.is_focused = False

        self._remove_tree(self._tree_root)
        self._tree_root, prev_focused = self._modal_stack.pop()
        self._node_map.clear()
        self._rebuild_node_map(self._tree_root)
        self._spatial_dirty = True

        if prev_focused is not None and prev_focused.component is not None:
            self._focused = prev_focused
            prev_focused.component.is_focused = True
        else:
            self._focused = None
            first = self._dfs_first(self._tree_root)
            if first is not None:
                self._focus_node(first)

    def remove_component(self, component: BaseComponent):
        node = self._node_map.pop(component, None)
        if node is None:
            return

        was_focused = node is self._focused
        if was_focused:
            if node.component is not None:
                node.component.is_focused = False
            self._focused = None

        if node.parent is not None:
            siblings = node.parent.children
            idx = siblings.index(node)

            if was_focused:
                if idx + 1 < len(siblings):
                    self._focus_node(siblings[idx + 1])
                elif idx > 0:
                    self._focus_node(siblings[idx - 1])
                elif node.parent is not self._tree_root and node.parent.component is not None:
                    self._focus_node(node.parent)
                else:
                    self._focused = None

            siblings.remove(node)

        self._remove_tree(node)
        self._spatial_dirty = True

    def clear(self):
        if self._focused is not None and self._focused.component is not None:
            self._focused.component.is_focused = False
        self._focused = None
        for child in list(self._tree_root.children):
            self._remove_tree(child)
        self._tree_root.children.clear()
        self._node_map.clear()
        self._spatial_dirty = True

    def get_focused(self) -> Optional[BaseComponent]:
        if self._focused is not None:
            return self._focused.component
        return None

    def move_focus(self, direction: str):
        if not self._tree_root.children:
            return

        current = self.get_focused()

        if current is not None:
            self._ensure_spatial_index()
            next_comp = self._spatial_index.find_next(current, direction)
            if next_comp is not None:
                node = self._node_map.get(next_comp)
                if node is not None:
                    self._focus_node(node)
                    self._scroll_to_component(next_comp)
                    return

        if direction in ("RIGHT", "DOWN"):
            if self._focused is not None:
                next_node = self._dfs_next(self._focused)
            else:
                next_node = self._dfs_first(self._tree_root)
        else:
            if self._focused is not None:
                next_node = self._dfs_prev(self._focused)
            else:
                next_node = self._dfs_last(self._tree_root)

        if next_node is not None and next_node.component is not None:
            self._focus_node(next_node)
            self._scroll_to_component(next_node.component)

    def _scroll_to_component(self, component: BaseComponent):
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

        if key == "TAB":
            if self._focused is not None:
                next_node = self._dfs_next(self._focused)
            else:
                next_node = self._dfs_first(self._tree_root)
            if next_node is not None and next_node.component is not None:
                self._focus_node(next_node)
                self._scroll_to_component(next_node.component)
            return

        if key == "SHIFT_TAB":
            if self._focused is not None:
                next_node = self._dfs_prev(self._focused)
            else:
                next_node = self._dfs_last(self._tree_root)
            if next_node is not None and next_node.component is not None:
                self._focus_node(next_node)
                self._scroll_to_component(next_node.component)
            return

        if focused.on_key(key):
            return

        if focused.handle_input(key):
            return

        if key in ("UP", "DOWN", "LEFT", "RIGHT"):
            self.move_focus(key)
        elif key == "ENTER":
            focused.on_enter()
