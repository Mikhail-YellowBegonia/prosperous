# Known Issues & Roadmap

## ✅ 已修复

- **SIGWINCH 死锁**：信号处理器改为只设 flag，resize 推迟到 `poll()` 执行。
- **焦点隔离**：`FocusManager` 内置焦点栈，`push_group()` / `pop_group()` 支持 Modal。
- **坐标语义混乱**：`Panel` 加入 `padding` + `get_child_origin(child)`，`pos=(0,0)` 即内容区左上角。
- **组件 visible / focus_style / remove_child / live.stop()**：均已实现。
- **自动焦点注册**：`live.add()` 递归收集 `focusable=True` 组件，跳过 `visible=False` 子树。
- **Text 在 HStack 宽度不准**：`Text(width=n)` 参数作为布局宽度提示。
- **组件匿名引用**：`BaseComponent(id=...)` + `component.find(id)` + `live.find(id)` DFS 查询。
- **顶层 layer 排序无效**：`frame()` 现在按 `layer` 排序 `_scene` 后再绘制。
- **缓冲区指针交换 + clear_prepare 加速 + ANSI 增量渲染**：第一轮优化已完成。
- **缺少 clear_rect() 工具方法**：已在 `RenderEngine` 实现，组件在 `draw()` 开始时调用以清理上一帧区域。
- **自定义组件绘图工具缺失**：已在 `RenderEngine` 新增 `fill_rect()` / `draw_vline()` / `draw_box()`。
- **图像渲染接口不统一**：所有 `*ImageRenderer.draw()` 改为接受 `engine` 参数，调用方无需知道底层 push 方法。
- **binmap_color 彩色模式透明像素污染 bg**：透明像素（alpha=0）不再参与 bg 均值计算，避免背景被黑色拉偏。
- **图像渲染畸变**：引入 `cell_aspect` 参数，各渲染方法均按 `2 × cell_aspect / rows_per_cell` 正确压缩图像高度，并缩减为一次 resize。默认值 `cell_aspect=2.0`（行业惯例），终端格子更高的用户可手动传参。
- **frame() 持锁范围过宽**：三缓冲架构彻底解决。draw 阶段全程写入逻辑线程私有缓冲区 `screen_logic`（无锁），仅 `commit_logic()` 的 O(1) 指针交换处短暂持锁。
- **合成层优先级隐式**：三个 space 各保持独立缓冲区，`flush_spaces` 单次遍历 `dirty_cells`，按 `(layer, type_priority)` 选出胜者后统一 push。`*ImageRenderer.draw()` 新增 `layer=0` 参数供调用方显式控制；相同 layer 时类型优先级 braille > image > binmap。
- **顶层组件坐标语义**：已在 `BaseComponent` docstring 中明确说明 `pos` 的双重语义及 `get_absolute_pos()` 用法。
- **底层绘图工具链不完整**：已补齐 `draw_hline()` 和支持对齐/截断/Markup 的高级 `write()` 方法。

---

## 📌 [By Design] 已知限制，不计划修复

### [renderer] ImageRenderer（half-block）存在轻微畸变
- half-block 的 `ImageRenderer` 内部不做 cell_aspect 修正，以 1:1 像素比渲染。修正需非整数倍缩放，代价不划算。其他四种渲染方法（binmap/binmap_color/braille6/braille6_color）均已修正。

### [renderer] Braille 字符视觉连续性取决于字体
- 盲文字符的圆点在部分字体下呈离散点状，而非连续填充块。这是字体渲染行为，库层面无法干预。开发者可根据字体效果自行选择是否使用盲文方法。

### [renderer] cell_aspect 无法自动检测
- 终端格子高宽比因字体而异，库无法可靠地从运行时环境中推断（`os.get_terminal_size()` 只返回格子数，不含像素尺寸）。默认值 `2.0` 适合大多数终端；需要精确补偿的开发者请在 `register()` 时手动传入 `cell_aspect`。

---

## 🟡 [Near-term] 待解决

---

## 🔵 [Architecture] 架构待议

### [test] renderers.py 覆盖率低（≈16%）
- **原因**：`*ImageRenderer.__init__()` 依赖 PIL 图像加载，现有单元测试未 mock PIL，覆盖不到图像读取与缩放逻辑。
- **方案**：引入 fixture 提供最小合成图像（纯色 RGBA），或对 PIL 调用进行 mock。

---

## ⚪ [Deferred] 暂缓

### [animation] Follower（弹性跟随）
`Tween` 已实现。`Follower` 是无终止时间的弹性跟随（每帧向目标靠近固定比例），暂缓，有需要时再加。

### [layout] 空间焦点导航
按方向键时按屏幕坐标查找最近组件，而非线性循环。依赖坐标缓存机制，优先级低。

### [layout] 滚动支持
`LogView` 等组件的滚动浏览逻辑，单独立项。

### [engine] 区域管理
`RenderEngine` 对屏幕区域的逻辑划分（子裁剪区），用于限制组件绘制范围，防止越界污染。
