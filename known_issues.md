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

---

## 🔥 [Optimization] 第一轮全面优化（当前重点）

### [engine] 缓冲区交换全量拷贝 → 指针交换
- **现状**：`swap_buffers()` 用 `[:]` 全量拷贝，80×24 下每帧拷贝 1920 个 tuple。
- **修复**：`screen_prepare` 与 `screen_buffer` 直接交换引用，O(1)，与终端尺寸无关。

### [render] ANSI 状态机低效：每次样式变化发送完整 reset
- **现状**：样式变化时发送 `\033[0m` + 完整重声明。同样式连续格子已优化（跳过），但变化时仍重置全部属性。
- **影响**：SSH 等高延迟环境画面撕裂感明显，终端解析压力大。
- **修复**：引入 `_RenderContext` 记录终端当前样式状态，仅发送变化属性的最小增量序列。属性单独关闭（`\033[22m` 关 bold 等）而非全量 reset。

### [engine] clear_prepare 嵌套循环效率低
- **现状**：双层 for 循环逐格赋值，O(width × height) 次 Python 对象创建。
- **修复**：结合指针交换，直接重建整行列表，减少 Python 层循环开销。

### [component] 坐标/样式递归无缓存
- **现状**：`get_absolute_pos()` 和 `get_effective_style()` 每帧每组件从根节点递归。树浅时可接受，复杂 UI 下浪费。
- **修复**：引入 `_pos_dirty` / `_style_dirty` 标志，tree mutation（add_child / pos 变更）时失效，命中缓存时直接返回。

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
