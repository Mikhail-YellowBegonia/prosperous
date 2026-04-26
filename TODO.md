# Prosperous TODO

## 🟡 [Near-term] 待修复与改进 (Pending Fixes)

- [x] **[engine] 实现 `clear_rect()` 工具方法**
- [x] **[docs] 顶层组件坐标语义文档化**
- [x] **[assets] 资产占位符封装 (assets.py)**
- [x] **[component] Box 自定义边框与填充**

## 🔵 [Architecture] 架构优化 (Architecture Improvements)

- [x] **[live] 优化 `frame()` 持锁机制 (三缓冲架构)**
- **[animation] 实现 `Follower`（弹性跟随）**：
  - 实现无终止时间的弹性跟随算法，适合卡片跟随等交互效果。

## ⚪ [Deferred] 暂缓事项 (Deferred)

- **[layout] 空间焦点导航**：
  - 按方向键时根据屏幕坐标查找最近组件，而非线性循环。
- **[layout] 滚动支持**：
  - 实现 `LogView` 等组件的滚动浏览逻辑。
- **[engine] 区域管理**：
  - `RenderEngine` 对屏幕区域的逻辑划分。

## 🧪 测试增强 (Testing)

- **[test] 完善测试覆盖**：
  - 补充布局数学、输入解析等单元测试。
  - 增加快照测试 (Snapshot Testing)，防止布局回归。
