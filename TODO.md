# Prosperous TODO

## 🟡 [Near-term] 待修复与改进 (Pending Fixes)

- [x] **[engine] 实现 `clear_rect()` 工具方法**
- [x] **[docs] 顶层组件坐标语义文档化**
- [x] **[assets] 资产占位符封装 (assets.py)**
- [x] **[component] Box 自定义边框与填充**

## 🔵 [Architecture] 架构优化 (Architecture Improvements)

- [x] **[live] 优化 `frame()` 持锁机制 (三缓冲架构)**
- **[animation] 实现 `Kinetic` (动力学/物理) 动画系统**：
  - 核心：基于状态（位置、速度、目标）而非单纯时间的模拟。
  - 场景：支持动画中断无缝衔接、焦点迁移时的逻辑变色与形变、模拟投影跟随等复杂交互。
  - *注：99% 场景仍推荐使用 Tween，Kinetic 仅用于逻辑高度耦合的特殊动效。*

## ⚪ [Deferred] 暂缓事项 (Deferred)

- **[layout] 空间焦点导航**：
  - 按方向键时根据屏幕坐标查找最近组件，而非线性循环。
- **[layout] 滚动支持**：
  - 实现 `LogView` 等组件的滚动浏览逻辑。
- **[engine] 区域管理**：
  - `RenderEngine` 对屏幕区域的逻辑划分。

## 📦 发布准备 (Packaging & Release)

- [x] **创建 `pyproject.toml`**：定义项目元数据、依赖和构建系统。
- [x] **创建 `LICENSE`**：采用 MIT 协议。
- [ ] **构建与校验**：本地测试 `python -m build` 和 `twine check`。
- [ ] **README 润色**：增加安装说明和示例。
- [ ] **发布到 TestPyPI**：在正式发布前进行上传验证。

