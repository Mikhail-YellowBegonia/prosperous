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

---

## 🟡 [Near-term] 集成测试发现的新问题

### [engine] 缺少 clear_rect() 工具方法
- **现象**：自定义组件在 `draw()` 里必须手动用空格字符填满自身背景，防止移动后残留旧像素（见 music_player.py SongCard 的 "OPAQUE BACKGROUND" 注释）。
- **原因**：diff 渲染只更新变化的格子，不知道组件的"旧位置"。库没有提供工具方法缓解这个负担。
- **方案**：在 `RenderEngine` 上提供 `clear_rect(y, x, height, width)` 方法，组件在 `draw()` 开始时调用以清理上一帧区域。

### [docs] 顶层组件坐标语义未文档化
- **现象**：顶层组件（无父节点）的 `pos` 直接等于屏幕坐标，但文档未明说。作为子组件时 `pos` 是相对父原点的偏移。两种语义合并在同一个字段，容易踩坑。
- **方案**：在 `BaseComponent` docstring 和 CLAUDE.md 中补充说明；或提供语义更清晰的 `set_screen_pos()` 方法供顶层动画使用。

---

## 🔵 [Architecture] 架构待议

### [animation] 缺少基础 Tween 工具类
- **现象**：music_player.py 中 LERP 动画全部内联在主循环，缓动系数硬编码，逻辑重复。每个需要动画的属性都要重写一遍。
- **性质**：不是"重"功能，核心是一个 ~20 行的 `Tween(start, end, duration, easing)` 类，主循环里按帧查询当前值即可。与 Prosperous 帧循环模型完全契合，不依赖 asyncio 或 reactive。
- **方案**：见下文动画支持分析。

### [live] frame() 持锁导致渲染线程串行化
- **现状**：draw 阶段持有 `engine.lock`，`swap_buffers()` 阻塞等待，多线程优势受限。
- **方向**：分离 prepare 写入阶段与 buffer 交换阶段，缩短主锁持有时间。

---

## 🔵 [Architecture] 架构待议

### [live] frame() 持锁导致渲染线程串行化
- **现状**：draw 阶段持有 `engine.lock`，`swap_buffers()` 阻塞等待，多线程优势受限。
- **方向**：分离 prepare 写入阶段与 buffer 交换阶段，缩短主锁持有时间。依赖指针交换完成后再评估。

---

## ⚪ [Deferred] 暂缓

### [layout] 空间焦点导航
按方向键时按屏幕坐标查找最近组件，而非线性循环。依赖坐标缓存机制，优先级低。

### [layout] 滚动支持
LogView 等组件的滚动浏览逻辑，单独立项。
