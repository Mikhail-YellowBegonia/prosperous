# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
source .venv/bin/activate && python -m pytest tests/ -q

# Run a single test file
source .venv/bin/activate && python -m pytest tests/unit/test_layout.py -v

# Run a single test by name
source .venv/bin/activate && python -m pytest tests/unit/test_layout.py::TestAbsolutePos::test_root_component -v

# Format code (project standard)
source .venv/bin/activate && ruff format --line-length 100 .

# Run the demo app
source .venv/bin/activate && python main.py

# Run the kinetic focus demo
source .venv/bin/activate && python examples/kinetic_focus_demo.py

# Build package
source .venv/bin/activate && python -m build

# Check built package
source .venv/bin/activate && twine check dist/*
```

## Architecture

Prosperous is a terminal UI library built on a **frame-loop + double-buffer diff rendering** model. It follows a standard **`src/` layout** for PyPI distribution.

### Source Layout

Core library code is located in `src/prosperous/`.
Internal modules use **relative imports** (e.g., `from .engine import ...`) for compatibility with package installation.

### Threading model

`Live` (`live.py`) manages three threads:
- **Logic thread** — user's `while live.running` loop; rate-limited by `live.poll()`
- **Render thread** — `_render_loop()` calls `swap_buffers()` + `render()` at target fps
- **Input thread** — `InputHandler.listen()` reads raw bytes, emits key names into `engine.input_events`

The logic thread holds `engine.lock` during `live.frame()`. The render thread acquires the same lock in `swap_buffers()`. This is the intentional serialisation point.

### Rendering pipeline

```
draw() calls → screen_prepare (write)
               ↓ swap_buffers() [O(1) pointer swap]
               screen_buffer (read-only)
               ↓ find_diff() vs screen_dump
               screen_diff (changed cells only)
               ↓ render() with _RenderContext
               stdout (incremental ANSI sequences)
               ↓ copy to screen_dump
```

`_RenderContext` (`engine.py`) tracks the terminal's current style state and emits only the changed ANSI attributes. It resets on `clear_screen()` (terminal resize).

### Coordinate system

`pos=(row, col)` everywhere, 0-indexed. Children of a container use `parent.get_child_origin(child)` as their base, which panels offset by `1 + padding`. This is the extension point for custom layout logic.

- `Panel.get_child_origin()` → adds border (1) + padding
- `VStack.get_child_origin(child)` → accumulates row offsets by `get_height()`
- `HStack.get_child_origin(child)` → accumulates col offsets by `get_width()`

All components must implement `get_height()` and `get_width()` for stack layout.

### Focus system

`FocusManager` (`interaction.py`) maintains a **stack of focus groups** (`_stack`). `push_group([...])` freezes the current group and activates a new one (used for modals). `pop_group()` restores. `live.add()` auto-registers `focusable=True` components in declaration order, skipping `visible=False` subtrees.

### Theme system

`get_theme("ComponentName")` (`theme.py`) is called in each component's `__init__` to provide parameter defaults. `set_theme(dict)` replaces the global theme before entering `with Live(...)`. Component-level explicit params always override theme values.

### Testing conventions

- `tests/unit/` — pure logic, no engine needed (layout math, style system, component state)
- `tests/buffer/` — draws into a mocked `RenderEngine` and asserts `screen_prepare` cell contents
- `tests/unit/test_engine.py` — buffer swap and clear correctness
- `tests/unit/test_render_context.py` — `_RenderContext.diff()` ANSI sequence correctness
- The `engine` fixture in `conftest.py` patches `os.get_terminal_size` and `signal.signal`; do not replace `sys.stdout` (breaks pytest's own terminal detection)
- Test files use `sys.path.insert(0, ...)` to ensure `src/` is in the path.

## Animation

`animation.py` 提供 `Tween` 和四个内置 easing 函数（`linear` / `ease_in` / `ease_out` / `ease_in_out`）。

`Tween` 是一个无副作用的数值插值器，每帧通过 `.value` 查询：

```python
from prosperous import Tween, ease_in_out

anim = Tween(start=0, end=10, duration=0.4, easing=ease_in_out)

# 主循环每帧
card.pos = (round(anim.value), x)
if anim.done:
    card.pos = (10, x)   # snap 到终值
```

easing 函数签名：`(t: float) -> float`，`t ∈ [0, 1]`，可传入任意符合此签名的函数。

## Key design constraints

- **No external dependencies** except Pillow (image rendering only)
- **No layout solver** — absolute coordinates are intentional; `VStack`/`HStack` provide relative convenience, not constraint-based layout
- **No lifecycle hooks** — component construction is pure Python; resource cleanup belongs in the `with Live(...) as live:` exit
- **Formatter**: `ruff format --line-length 100`; top-level `Panel` declarations should be assigned to named variables before `live.add()` to avoid excessive nesting depth
