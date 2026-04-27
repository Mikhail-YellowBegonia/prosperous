# Prosperous TODO

## 🚀 当前优先级 (Immediate Priority)

- **[animation] 实现 `Kinetic` (动力学/物理) 动画系统**：
  - [x] **接口设计**：已建立 `animation.py` 中的 `Kinetic` 类接口及 docstring。
  - [ ] **物理内核**：实现基于 `dt` 的临界阻尼弹簧数值积分算法。
  - 核心：基于状态（位置、速度、目标）而非单纯时间的模拟。
- **[packaging] 完善发布流程**：
  - [ ] **README 润色**：增加安装说明、快速开始示例。
  - [ ] **构建校验**：运行 `python -m build` 并使用 `twine check` 验证。

## 🔵 架构与组件扩展 (Architecture & Components)

- **[layout] 滚动支持**：
  - 实现 `LogView` 或 `ScrollBox` 的滚动浏览逻辑（偏移量管理）。
- **[interaction] 空间焦点导航**：
  - 允许使用方向键根据屏幕坐标查找最近组件，而非线性循环。
- **[engine] 区域管理**：
  - `RenderEngine` 对屏幕区域的逻辑划分（子裁剪区）。
- [x] **[engine] PPrint 模仿尝试 (Markup & RichText)**：
  - 引入 `markup.py` 支持 `<tag>` 语义化标记。
  - 重构为 `Label` (轻量单行) 和 `Text` (多行/对齐/标记) 两个组件。
## 📦 已完成事项 (Completed)

- [x] **[engine] 三缓冲架构 (Triple-Buffering)**：彻底解决 `frame()` 持锁导致的渲染阻塞。
- [x] **[engine] 实现 `clear_rect()` 工具方法**：支持区域清理。
- [x] **[component] Box/Panel 自定义边框与填充**：支持 8 位边框字符。
- [x] **[assets] 资产占位符封装 (assets.py)**：字体/图像预加载。
- [x] **[dist] PyPI 发布准备**：创建 `pyproject.toml` 和 `LICENSE`。
- [x] **[docs] 核心文档润色**：docstring 补全及 `GEMINI.md` 生成。
