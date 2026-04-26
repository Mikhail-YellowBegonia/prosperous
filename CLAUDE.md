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
```

## Architecture

Prosperous is a terminal UI library built on a **frame-loop + double-buffer diff rendering** model. It is explicitly NOT a document-flow/layout-solver framework — all coordinates are absolute (row, col) with layout containers providing relative positioning.

### Threading model

`Live` (live.py) manages three threads:
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

`_RenderContext` (engine.py) tracks the terminal's current style state and emits only the changed ANSI attributes. It resets on `clear_screen()` (terminal resize).

### Coordinate system

`pos=(row, col)` everywhere, 0-indexed. Children of a container use `parent.get_child_origin(child)` as their base, which panels offset by `1 + padding`. This is the extension point for custom layout logic.

- `Panel.get_child_origin()` → adds border (1) + padding
- `VStack.get_child_origin(child)` → accumulates row offsets by `get_height()`
- `HStack.get_child_origin(child)` → accumulates col offsets by `get_width()`

All components must implement `get_height()` and `get_width()` for stack layout.

### Focus system

`FocusManager` (interaction.py) maintains a **stack of focus groups** (`_stack`). `push_group([...])` freezes the current group and activates a new one (used for modals). `pop_group()` restores. `live.add()` auto-registers `focusable=True` components in declaration order, skipping `visible=False` subtrees.

### Theme system

`get_theme("ComponentName")` (theme.py) is called in each component's `__init__` to provide parameter defaults. `set_theme(dict)` replaces the global theme before entering `with Live(...)`. Component-level explicit params always override theme values.

### Testing conventions

- `tests/unit/` — pure logic, no engine needed (layout math, style system, component state)
- `tests/buffer/` — draws into a mocked `RenderEngine` and asserts `screen_prepare` cell contents
- `tests/unit/test_engine.py` — buffer swap and clear correctness
- `tests/unit/test_render_context.py` — `_RenderContext.diff()` ANSI sequence correctness
- The `engine` fixture in `conftest.py` patches `os.get_terminal_size` and `signal.signal`; do not replace `sys.stdout` (breaks pytest's own terminal detection)

## Key design constraints

- **No external dependencies** except Pillow (image rendering only)
- **No layout solver** — absolute coordinates are intentional; `VStack`/`HStack` provide relative convenience, not constraint-based layout
- **No lifecycle hooks** — component construction is pure Python; resource cleanup belongs in the `with Live(...) as live:` exit
- **Formatter**: `ruff format --line-length 100`; top-level `Panel` declarations should be assigned to named variables before `live.add()` to avoid excessive nesting depth
