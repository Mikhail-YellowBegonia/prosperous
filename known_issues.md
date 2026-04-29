# Known Issues & Roadmap

## ✅ 已修复

- **SIGWINCH 死锁**：信号处理器改为只设 flag，resize 推迟到 `poll()` 执行。
- **焦点隔离**：`FocusManager` 内置焦点栈，`push_group()` / `pop_group()` 支持 Modal。
- **坐标语义混乱**：`Panel` 加入 `padding` + `get_child_origin(child)`，`pos=(0,0)` 即内容区左上角。
- **组件 visible / focus_style / remove_child / live.stop()**：均已实现。
- **自动焦点注册**：`live.add()` 递归收集 `focusable=True` 组件，跳过 `visible=False` 子树。
- **三缓冲架构 + ANSI 增量渲染**：彻底解决渲染阻塞与高延迟下的性能问题。
- **底层绘图工具链**：实现 `fill_rect`, `vline`, `hline`, `draw_box`, `write` (对齐/截断/Markup) 等原子化绘图原语。
- **区域管理 (Clipping)**：`RenderEngine` 引入传递性裁剪栈，支持嵌套视口。
- **高性能滚动 (Scrolling)**：
  - **Part A**：`LogView` 实现视觉行缓冲与富文本折行。
  - **Part B**：`ScrollBox` 实现坐标平移视口。

---

## 📌 [By Design] 已知限制，不计划修复

### [layout] LogView/Text 动态宽度响应
- 文本在 `append` 或 `draw` 时锁定折行，若组件在运行时发生宽度剧烈变化，已生成的行缓冲不会自动重排。

### [renderer] ImageRenderer（half-block）存在轻微畸变
- half-block 方法不做 cell_aspect 修正。

---

## 🟡 [Near-term] 待解决（轻量化修复）

### [layout] ScrollBox 滚动约束与反馈
- 目前 `scroll_y/x` 允许无限滚动，且缺少滚动条视觉反馈。

### [interaction] 动态组件焦点注册
- `add_child()` 动态添加的组件无法自动进入 `FocusManager`，目前需手动调用 `live.focus.add_component()`。

---

## 🔵 [Architecture] 架构缺陷（待重构）

### [interaction] 扁平化焦点管理
- **现状**：`FocusManager` 只有一层栈。父组件（ScrollBox）与子组件（Button）在焦点序列中是平等的。
- **问题**：`TAB` 切换时，焦点可能在容器和容器内部件之间产生逻辑混乱。
- **理想方案**：实现层级焦点系统（Tree-based Focus）。

### [interaction] 焦点与可见性脱节
- **问题**：处于焦点的组件可能被 `ScrollBox` 滚出视口。
- **理想方案**：`ScrollBox` 应拦截子组件焦点事件并自动修正 `scroll_pos`。

### [test] renderers.py 覆盖率低（≈16%）
- 现有单元测试未 mock PIL，覆盖不到图像读取逻辑。
