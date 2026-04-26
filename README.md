# Prosperous - 终端 UI 库

## 简介

Prosperous 是一个轻量的终端 UI 库，专为**动态高频刷新**场景设计，是 Rich.Live 的轻量替代方向。它不引入文档流或约束布局，直接面向帧循环画布，帮助开发者快速搭建高性能、交互灵敏的终端应用。

唯一的外部依赖是 Pillow（仅图像渲染需要）。

## 底层架构

### 渲染引擎

采用**双缓冲差分渲染**，由三个线程协同驱动：

- **Logic 线程**：用户的主循环，通过 `live.poll()` 限速，在 `live.frame()` 上下文内调用组件 `draw()`，结果写入 `screen_prepare` 缓冲区
- **Render 线程**：以目标 fps 运行，通过 O(1) 指针交换将 `screen_prepare` 与 `screen_buffer` 互换，然后对比 `screen_dump` 计算差分，只向终端发送变化的格子
- **Input 线程**：字节流状态机，实时解析原始输入并入队，Logic 线程通过 `live.poll()` 取出

ANSI 输出采用**增量状态机**（`_RenderContext`）：追踪终端当前样式状态，只发送变化的属性码，不发全量 reset。对 SSH 等高延迟环境友好。

### 坐标系

`pos=(row, col)`，从 0 开始。子组件坐标相对于父容器的**内容区原点**（`get_child_origin()`），而非屏幕绝对坐标。顶层组件（直接 `live.add()` 的）`pos` 等于屏幕坐标。

`VStack` / `HStack` 通过覆盖 `get_child_origin(child)` 实现自动排列，这也是自定义布局容器的扩展点。

### 焦点系统

`FocusManager` 内置**焦点栈**。`live.add()` 时自动按声明顺序注册所有 `focusable=True` 的组件（跳过 `visible=False` 子树）。Modal 等场景通过 `push_group()` / `pop_group()` 临时接管焦点，关闭后自动恢复。

## 快速上手

```python
from live import Live
from components import Panel, InputBox, Button, Text
from styles import Style

with Live(fps=30, logic_fps=60) as live:
    cmd = InputBox(id="cmd", width=30, label="INPUT",
                   on_enter=lambda: handle(cmd.text))

    panel = Panel(pos=(1, 2), width=50, height=5, title="DEMO",
                  children=[cmd, Button(label="OK", on_enter=lambda: handle(cmd.text))])

    live.add(panel)  # focusable 子组件自动注册焦点

    while live.running:
        for key in live.poll():
            if key == "ESC": live.stop()
            live.focus.handle_input(key)
        with live.frame():
            pass
```

## 功能一览

**组件**：`Panel`、`Box`（无标题边框）、`VStack`、`HStack`、`Text`、`Button`、`InputBox`、`ProgressBar`、`LogView`

**布局**：`padding`、`gap`、`align`（cross-axis 对齐）、`reverse`、`layer`（绘制层级）

**交互**：声明式回调（`on_enter`、`on_key`、`on_focus`、`on_blur`）、焦点栈（Modal 隔离）、CJK 输入

**样式**：`Style` 对象、truecolor / 256色、样式继承、`Theme` 系统（按组件类型设默认值）

**动画**：`Tween(start, end, duration, easing)` 插值器，内置 `linear` / `ease_in` / `ease_out` / `ease_in_out`，easing 完全可自定义

**查询**：`component.find(id)` / `live.find(id)` 深度优先查找

## Theme 系统

```python
from theme import set_theme, DEFAULT_THEME
from styles import Style

set_theme({
    **DEFAULT_THEME,
    "Panel": {"padding": 2, "style": Style(fg=240)},
})
```

不传样式参数时自动使用 Theme 默认值，全局覆盖在进入 `with Live(...)` 前调用一次即可。

## 代码风格

使用 `ruff format --line-length 100`。

顶层容器建议用命名变量声明，`live.add()` 只传引用，避免整个组件树内联在函数调用里导致缩进过深：

```python
# 推荐
panel = Panel(pos=(1, 2), width=76, height=7, title="METRICS", children=[...])
live.add(panel)

# 不推荐
live.add(Panel(pos=(1, 2), width=76, height=7, title="METRICS", children=[...]))
```

## 邀请与致谢

由于作者水平有限，目前的 Prosperous 肯定还存在许多幼稚的设计或潜在的 Bug。

非常欢迎您指正代码中的错误，或者参与到共同开发中。如果您有兴趣尝试用这个小工具开发一个简单的终端应用，那将是对本项目最大的支持。
