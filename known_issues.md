# Known Issues & Roadmap

## 🔴 [Critical] 稳定性与正确性

### [engine] SIGWINCH 信号处理死锁 ✅ 已修复
信号处理器改为只设 `_resize_pending` flag，`listen_size()` 推迟到 `poll()` 中执行，
避免在持锁期间触发死锁。

---

## 🟡 [Near-term] 近期待做

### [interaction] 焦点系统缺乏隔离机制
- **现象**：打开 Modal 时底层组件仍可被 TAB 选中并触发，无法安全实现多层交互。
- **方案**：`FocusManager` 内置焦点栈，`push_group([...])` 压栈隔离，`pop_group()` 自动恢复，无需用户手动 clear/add。
- **备注**：空间导航（按方向键做坐标查找）是独立问题，依赖坐标缓存机制，暂缓。

### [layout] 绝对坐标系人体工程学差
- **现象**：子组件 `pos` 语义不清（相对边框还是内容区？），开发者必须硬编码大量 `+1` 偏移。
- **近期方案**：`Panel` 支持 `padding` 参数，子组件 `pos=(0,0)` 即为内容区左上角。
- **中期方案**：`VStack` / `HStack` 容器，子组件无需写 `pos`，自动顺序排列。两者递进，`padding` 先做。

### [component] 缺少 `visible` 属性
- **现象**：隐藏组件只能靠修改坐标或从 scene 移除，前者留有渲染负担，后者重新显示时需重新注册。
- **方案**：`BaseComponent` 添加 `visible: bool = True`，`draw()` 开头检查，为 False 时直接返回。

### [api] 小型 API 完善
- `live.stop()` 封装 `live.engine.is_running = False`，屏蔽底层细节。
- `Panel.remove_child(child)` 补全容器 API。
- `InputBox` 聚焦颜色硬编码为 `fg=220`，应改为 `focus_style` 参数支持自定义。

---

## 🔵 [Mid-term] 中期架构

### [render] ANSI 增量渲染仍可优化
- **现状**：样式相同的连续格子已不重复发送 ANSI 码（按 `last_style` 跳过）。
- **剩余问题**：样式变化时仍发送完整 `\033[0m` + 重声明，未做真正的增量 diff。
- **方案**：维护 `RenderContext` 记录各属性当前状态，仅发送变化的属性码。SSH 高延迟环境收益明显。

### [layout] 组件匿名，动态引用依赖外部变量
- **现象**：组件在树里没有 id/key，调试和运行时查找只能靠用户自己保留引用。
- **方案**：`BaseComponent` 支持可选 `id` 参数，`live.find(id)` 或 `panel.find(id)` 查询。

### [live] frame() 持锁时间长，渲染线程实际串行化
- **现状**：draw 阶段持有 `engine.lock`，`swap_buffers()` 阻塞等待，多线程优势受限。
- **方案**：分离 prepare 写入阶段与 buffer 交换阶段，缩短主锁持有时间。待性能优化节点统一处理。

---

## ⚪ [Deferred] 暂缓

### [layout] 空间焦点导航
- 按方向键时按实际坐标查找最近组件，而非线性循环。
- 依赖坐标缓存机制（需 dirty flag），与焦点栈独立，优先级低于焦点栈。

### [engine] 缓冲区交换全量拷贝
- `swap_buffers()` 用 `[:]` 全量拷贝，高分屏高频刷新下有内存压力。
- 当前规模（80×24）可忽略，性能优化节点统一处理。

### [component] 坐标/样式递归无缓存
- `get_absolute_pos()` 和 `get_effective_style()` 每帧递归，深树下浪费。
- 当前树浅，性能优化节点统一处理（引入 dirty flag）。
