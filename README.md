# Prosperous - 终端工具箱

## 简介
Prosperous 是一个处于早期开发阶段的终端 UI 库。它的诞生深受 Rich 库的启发，在 API 风格上尽量向其靠拢，同时针对"动态高频刷新"场景做了专门设计，是 Rich.Live 的轻量替代方向。

## 最终预期
创造一个比 Rich 更轻量、在动态渲染场景下性能更好的终端 UI 工具。Prosperous 不引入复杂的文档流或滚动逻辑，直接面向帧循环画布，帮助开发者快速搭建高性能、交互灵敏的终端应用。

## 程序结构
Prosperous 采用多线程驱动的三层架构：

1. **引擎层 (Engine)**：双缓冲差分渲染。每帧仅向终端发送发生变化的格子（ANSI 序列），在 30FPS 下数据传输量极小。支持图像合成层（半块字符真彩色）和二值位图层。

2. **组件层 (Component Tree)**：类 HTML 树状结构。组件通过相对坐标定位，子组件自动继承父组件样式。`Panel` 支持 `padding`，子组件 `pos=(0,0)` 即内容区左上角，无需手算边框偏移。单个组件崩溃不影响整体渲染。

3. **交互层 (Input & Focus)**：字节流状态机解析按键，支持方向键、组合键及多字节 UTF-8 / CJK 输入。`FocusManager` 内置焦点栈，`push_group()` / `pop_group()` 支持 Modal 等多层焦点隔离场景。

## 快速上手

```python
from live import Live
from components import Panel, InputBox, Button, Text
from interaction import FocusManager
from styles import Style

with Live(fps=30, logic_fps=60) as live:
    focus = FocusManager()

    box = InputBox(pos=(0, 0), width=30, label="INPUT", on_enter=lambda: handle(box.text))
    btn = Button(pos=(0, 32), label="Submit", on_enter=lambda: handle(box.text))

    panel = Panel(pos=(1, 2), width=60, height=5, title="DEMO", children=[box, btn])

    live.add(panel)
    focus.add_component(box)
    focus.add_component(btn)

    while live.running:
        for key in live.poll():
            if key == "ESC": live.stop()
            focus.handle_input(key)
        with live.frame():
            pass
```

## Theme 系统

Prosperous 内置 `DEFAULT_THEME`，定义各组件的默认样式与 padding。不传样式参数时自动生效，也可全局覆盖：

```python
from theme import set_theme, DEFAULT_THEME
from styles import Style

set_theme({
    **DEFAULT_THEME,
    "Panel": {"padding": 2, "style": Style(fg=240)},
})
```

## 代码风格与 Formatter

Prosperous 的声明式语法（`children=[...]` 嵌套）与 Black / Ruff 等 formatter 兼容，但有一个需要注意的权衡：

**Formatter 的效果**：自动将内联的嵌套结构展开为多行，层级结构清晰，类似 JSON 的视觉感。

**Formatter 的代价**：Python 以缩进表达层级，每套一层嵌套就多 4 格。`children=[]` 参数风格在深层嵌套时（如 Panel → VStack → HStack → 子组件）会推高缩进，代码向右漂移明显。

**建议的写法**：顶层容器用命名变量声明，`live.add()` 只传引用，避免把整个组件树内联在函数调用里。

```python
# 推荐：命名变量 + 独立 add
panel_metrics = Panel(pos=(1, 2), width=76, height=7, title="METRICS",
    children=[...])

live.add(panel_metrics)

# 不推荐：内联声明，白白多 2 层缩进
live.add(Panel(pos=(1, 2), width=76, height=7, title="METRICS",
    children=[...]))
```

项目使用 `ruff format --line-length 100` 作为标准 formatter。

## 开发计划 (活跃中)
- **布局辅助**：`VStack` / `HStack` 容器，子组件无需手写 `pos`。
- **滚动支持**：`LogView` 等组件的滚动浏览功能。
- **性能优化**：ANSI 增量渲染、坐标缓存、缓冲区指针交换。

## 邀请与致谢
由于作者水平有限，目前的 Prosperous 肯定还存在许多幼稚的设计或潜在的 Bug。

非常欢迎您指正代码中的错误，或者参与到共同开发中。如果您有兴趣尝试用这个小工具开发一个简单的终端应用，那将是对本项目最大的支持。
