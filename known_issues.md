# Known Issues & Roadmap

## ✅ 已修复

- **SIGWINCH 死锁**：信号处理器改为只设 flag，resize 推迟到 `poll()` 执行。
- **焦点隔离**：`FocusManager` 内置焦点栈，`push_group()` / `pop_group()` 支持 Modal。
- **坐标语义混乱**：`Panel` 加入 `padding` + `get_child_origin(child)`，`pos=(0,0)` 即内容区左上角。
- **组件 visible / focus_style / remove_child / live.stop()**：均已实现。
- lambda引起的HStack宽度问题：允许用户手动覆盖宽度，用`Text(text=lambda: f"...", width=20)`来定义。
- 组件自动注册：Live 内置一个 focus: FocusManager，遍历组件树，将所有将所有`focusable`且`visible`的组件按声明顺序加入默认焦点组。

---

## 🟡 [Near-term] 近期待做

### [layout] 组件匿名，动态引用依赖外部变量或下标

- **现象**：嵌进声明块的组件只能靠 `panel.children[0]` 引用，脆弱且不可读。
- **方案**：`BaseComponent` 支持可选 `id` 参数，`live.find(id)` 深度查询。

---

## 🔵 [Mid-term] 中期架构

### [render] ANSI 增量渲染

- **现状**：连续同样式格子已跳过 ANSI 输出；样式变化时仍发完整 reset + 重声明。
- **方案**：维护 `RenderContext` 记录当前终端样式状态，仅发送变化属性的最小序列。SSH 高延迟环境收益明显。

### [live] frame() 持锁导致渲染线程串行化

- **现状**：draw 阶段持有 `engine.lock`，`swap_buffers()` 阻塞等待。
- **方案**：分离 prepare 写入阶段与 buffer 交换阶段，缩短主锁持有时间。待性能优化节点统一处理。

---

## ⚪ [Deferred] 暂缓

### [layout] 空间焦点导航

按方向键时按屏幕坐标查找最近组件，而非线性循环。依赖坐标缓存（dirty flag），优先级低于自动焦点注册。

### [engine] 缓冲区交换全量拷贝

`swap_buffers()` 全量 `[:]` 拷贝，高分屏高频刷新下有内存压力。当前规模可忽略，性能节点统一处理。

### [component] 坐标/样式递归无缓存

`get_absolute_pos()` 和 `get_effective_style()` 每帧递归。当前树浅，性能节点统一处理（引入 dirty flag）。