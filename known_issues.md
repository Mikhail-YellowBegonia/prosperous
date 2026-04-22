# Known Issues - Prosperous Audit Report

## 🔴 [Critical] 稳定性与正确性

### [engine] SIGWINCH 信号处理死锁
- **位置**：`engine.py` → `__init__` 信号注册 / `listen_size()`
- **现象**：若 SIGWINCH 在主线程持有 `engine.lock`（即 `frame()` 上下文内）期间触发，信号处理器直接调用 `listen_size()`，后者尝试获取同一把不可重入锁，导致主线程死锁。
- **状态**：✅ 已修复。信号处理器改为仅设置 `_resize_pending = True`，实际 resize 推迟到 `poll()` 调用 `listen_size()` 时执行（此时主线程不持锁）。

### [render] 伪差分渲染：ANSI 协议状态机低效
- **位置**：`utils.py` → `ansilookup()`，`engine.py` → `render()`
- **现象**：每个差分格子前均发送 `\033[0m` reset 再重新声明样式，抵消了差分渲染的传输优化。
- **后果**：SSH 等高延迟环境下画面撕裂感明显，终端解析压力大。
- **修复方向**：`render()` 内维护 `prev_style`，仅在样式变化时发送最小增量 ANSI 序列，无变化时不发任何控制字符。

## 🟡 [Performance] 性能瓶颈

### [component] 样式与坐标解析递归无缓存
- **位置**：`BaseComponent` → `get_absolute_pos()` & `get_effective_style()`
- **现象**：每帧每组件从根节点递归累加坐标和合并样式，深树下 CPU 浪费明显。
- **当前影响**：树浅，暂无感知。
- **修复方向**：引入脏标记（Dirty Flag），仅在父节点位置或样式变化时更新子节点缓存值。

### [engine] 缓冲区交换全量拷贝
- **位置**：`engine.py` → `swap_buffers()`
- **现象**：`[:]` 全量行切片拷贝，高分屏（200×60）高频刷新下内存压力显著。
- **当前影响**：80×24 下可忽略。
- **修复方向**：三指针引用交换（Triple Buffering Pointer Swap），交换引用而非拷贝数据。

## 🔵 [Architecture] 架构缺陷

### [live] frame() 持锁时间长，渲染线程实际串行化
- **位置**：`live.py` → `frame()` / `_render_loop()`
- **现象**：`frame()` 持 `engine.lock` 期间，`swap_buffers()` 阻塞等待，多线程优势基本丧失。
- **修复方向**：分离"组件 → screen_prepare"写入阶段与"screen_prepare → screen_buffer"交换阶段，缩短主锁持有时间。

### [InputBox] draw() 中直接修改状态
- **位置**：`components.py` → `InputBox.draw()`
- **现象**：光标闪烁逻辑（`cursor_visible` 翻转）写在渲染路径中，违反渲染函数纯函数原则，闪烁频率受帧率约束。
- **修复方向**：光标状态由独立定时器或 `on_focus` 触发的后台逻辑驱动，`draw()` 只读状态。
