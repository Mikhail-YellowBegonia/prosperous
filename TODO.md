# Prosperous TODO

## 🚀 当前优先级 (Immediate Priority)

- **🟢 裁剪与剔除系统 (Clipping & Culling)**：
  - [ ] **[component] 位置缓存 (AABB Caching)**：在 `BaseComponent` 中实现绝对矩形边界缓存（数据基础）。
  - [ ] **[engine] 传递性裁剪栈 (Transitive Clip Stack)**：在 `RenderEngine` 中实现 `push_clip/pop_clip` 及交集计算。
  - [ ] **[engine] 渲染拦截**：修改 `RenderEngine.push` 使其尊重当前裁剪区（正确性保障）。
  - [ ] **[live] 自动剔除 (Auto Culling)**：在 `Live` 帧循环中根据 AABB 自动跳过完全不可见组件的 `draw`（性能优化）。
  - [ ] **[component] 容器控制**：为 `Box/Panel` 增加 `clipping` 属性支持。

## 🔵 架构与组件扩展 (Architecture & Components)

- **[layout] 滚动支持**：
  - 基于裁剪机制实现 `ScrollBox` 容器。
  - 实现 `LogView` 的滚动浏览逻辑。
- **[interaction] 空间焦点导航**：
  - 允许使用方向键根据屏幕坐标查找最近组件，而非线性循环。
- **[packaging] 自动化**：
  - [ ] **CI/CD 工作流**：配置 GitHub Actions 自动发布。
- **[test] 提高测试覆盖率**：
  - `renderers.py` 目前覆盖率低，需要 mock PIL 进行图像渲染逻辑测试。

## 📦 已完成事项 (Completed Archive)

- [x] **[packaging] 完善发布流程**：已完成项目结构调整（src layout）并成功发布到 PyPI。
- [x] **[animation] 实现 `Kinetic` (动力学/物理) 动画系统**。
- [x] **[engine] 三缓冲架构 (Triple-Buffering)**：彻底解决 `frame()` 持锁导致的渲染阻塞。
- [x] **[engine] 底层绘图工具链**：实现 `fill_rect`, `vline`, `hline`, `draw_box`, `write` 等原语。
- [x] **[engine] PPrint 模仿尝试 (Markup & RichText)**。
- [x] **[engine] 实现 `clear_rect()` 工具方法**。
- [x] **[component] Box/Panel 自定义边框与填充**。
- [x] **[assets] 资产占位符封装 (assets.py)**。
- [x] **[dist] PyPI 发布准备**。
- [x] **[docs] 核心文档润色**（中英双语 README）。
