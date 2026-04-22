# Known Issues

## 渲染层

### [render] 缺少 ANSI reset，颜色样式会向后泄漏
- **位置**：`utils.py` → `ansilookup()`，`engine.py` → `render()`
- **现象**：diff 渲染时，前一个格子的颜色属性（fg/bg/bold 等）不会被重置，后续没有显式声明样式的格子会继承前格样式，导致颜色污染。
- **原因**：`ansilookup` 只输出激活样式的 escape code，从不发 `\033[0m`。
- **修复方向**：在每个差分格子写入前先发 `\033[0m`，或在 `ansilookup` 中始终前缀 reset。

### [render] 渲染期间光标未隐藏，导致光标闪烁
- **位置**：`engine.py` → `render()`
- **现象**：每帧刷新时光标在屏幕上跳动，视觉噪声明显。
- **修复方向**：`render()` 开始前写 `\033[?25l`，结束后写 `\033[?25h`。

## 引擎层

### [engine] 终端 resize 不自动响应
- **位置**：`engine.py` → `listen_size()`
- **现象**：`listen_size()` 仅在 `__init__` 中调用一次，之后终端窗口大小改变不会触发缓冲区重分配，导致渲染越界或内容错位。
- **修复方向**：注册 `signal.SIGWINCH` 信号处理器，在收到信号时调用 `listen_size()`。

## 组件层

### [InputBox] 控制键过滤启发式不可靠
- **位置**：`components.py` → `InputBox.handle_input()`
- **现象**：用 `key.isupper() and len(key) > 1` 来判断是否为控制键名（如 `"UP"`、`"DOWN"`），但单字符大写字母（`"A"`、`"B"` 等）`len == 1`，会被误判为普通字符写入文本框。
- **修复方向**：维护一个明确的控制键名白名单集合（`{"UP", "DOWN", "LEFT", "RIGHT", "TAB", "ESC", ...}`），用 `key in CONTROL_KEYS` 替代启发式判断。
