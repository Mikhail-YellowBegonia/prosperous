这里记载长期规划，无需频繁检查与更新：

## 核心目标

创造轻量、Live 性能良好的终端 UI 库。
直接面向动态渲染循环，不引入复杂的底层滚动逻辑。
语法对齐 Rich，保持 AI 友好性

## 优先级 1：监听循环 (Listening Loop) - [底层逻辑]

[x] **异步输入系统**：实现基于 `threading` 或 `selectors` 的非阻塞键盘输入监听。
[x] **按键映射 (Key Mapping)**：支持方向键、组合键及特殊功能键的标准化解析。
[x] **输入法支持**：针对终端下中文/复杂字符输入的处理，增量 UTF-8 解码。
[x] **事件分发**：`live.poll()` 返回原始事件；组件级 `on_key` / `on_enter` 支持声明式回调，返回 False 可阻断默认行为。

## 优先级 2：组件抽象 (Component Abstraction) - [基础套件]

[x] **基础容器**：`Panel`（边框容器，padding，get_child_origin）。
[x] **布局容器**：`VStack` / `HStack`，子组件按声明顺序自动排列，支持 gap。
[x] **UI 原子**：`Text`（静态/lambda 动态）、`ProgressBar`、`LogView`。
[x] **输入组件**：`InputBox`（CJK 宽度感知、省略号截断、光标闪烁）、`Button`。
[x] **组件特性**：`visible`、`layer`、`focus_style`、声明式 `children=[]`、事件回调构造参数。
[ ] **资产占位符**：图像/字体预加载封装（ImageRenderer / FontManager）。

## 优先级 3：动态布局管理 (Layout & Logic) - [对齐 Rich]

[x] **入口抽象**：`Live` 上下文管理器，封装三线程、限速（fps/logic_fps）、cleanup。
[x] **帧管理**：`live.frame()` 自动 clear/flush，`live.add()` / `live.remove()` 管理场景。
[x] **焦点系统**：`FocusManager` 焦点栈，`push_group()` / `pop_group()` 支持 Modal 隔离。
[x] **Theme 系统**：`DEFAULT_THEME` + `set_theme()`，组件按类型查表获取默认参数。
[ ] **自动焦点注册**：`live.add()` 时递归收集 `focusable=True` 的组件，免去手动 `add_component()`。
[ ] **滚动支持**：LogView 等组件的滚动浏览逻辑。
[ ] **区域管理**：RenderEngine 对屏幕区域的划分（暂缓）。

## 优先级 4：样式与代码质量

[x] **样式对象化**：`Style` 类，支持继承、合并、truecolor / 256色。
[x] **ANSI 优化（初步）**：连续同样式格子跳过 ANSI 输出。
[x] **代码去重**：`push_image` / `push_binmap` 边界检查统一为 `_space_in_bounds()`。
[ ] **ANSI 增量渲染**：维护 RenderContext，仅发送样式变化的增量序列（SSH 环境收益明显）。
[ ] **组件 id / find**：支持按 id 查询组件，解决匿名组件动态引用问题。
