# Prosperous - CLI Toolkit

## 简介
这是一个终端工具箱，主要提升终端输出的美观度，并预期提供一些辅助功能，帮助CLI应用的搭建。
本项目为练习性项目，模仿Rich库，并加入拓展功能。

### 预期
- 提供与Rich库的API兼容性
- 在动态图形场景上获得优于Rich.Live + Rich-Pixels的性能
- 搭建一个可用的终端App作为成果
- 语法符合Rich，保持简洁和AI友好性

## 开发计划（不分先后）
- 方向键导航
- 文本输入与输入法支持
- 高度抽象组件（文本框等）
- 简易的动态页面
- 重做样式
- 易用性改进
- 对齐Rich语法习惯

## 程序结构

### 循环
三个循环通过`threading`库多线程运行。
- 逻辑循环`logic_loop`：负责处理逻辑
- 渲染循环`render_loop`：负责渲染画面
- 监听循环（WIP）
- 循环外内容：程序默认对所有美术资产（彩图、单色图、字体）采用预加载。

### 缓冲
程序使用多个缓冲区避免重复绘制和错误渲染，其默认行为在`engine.py`中定义。
图片通过unicode字符进行现实，故分辨率异于终端字符，按彩色“half_block”和单色“quarter_block”区分，并拥有独立的缓冲区和渲染方法。

- 屏幕缓冲区（只读）`screen_buffer`
- 准备缓冲区（可写）`screen_prepare`
- 彩图缓冲区`image_space`
- 单色图缓冲区`binmap_space`

程序运行时，两个图片缓冲区被合并推入`screen_prepare`。结合其它输出后，推入`screen_buffer`，并通过差分方法选择性重绘至终端。



### 渲染器
特殊方法：
- 图片渲染器`ImageRenderer`：负责渲染图片，并存储为矩阵，供渲染时使用。
- 二进制映射渲染器`BinmapRenderer`：负责渲染二值图像，并映射至屏幕空间。
- 字体渲染器`FontManager`：负责渲染字体，并存储为矩阵，供`BigTextRenderer`使用。
- 大文本渲染器`BigTextRenderer`：负责渲染大文本为二值图像，渲染过程依赖`BinmapRenderer`。
- 二值图直接渲染`BinmapImageRenderer`：绕过矩阵传递，有自己的渲染方法。
一般方法：
- 底层一般文本渲染`push`：负责渲染一般文本，包括文本缩放、颜色处理等。
- 底层特殊对象渲染`push_xxx`：负责渲染特殊方法产生的对象，包括图片、二值图、字体等（暂无统一方法）。

### 小工具
- 颜色处理工具`ansilookup`：对 24bit色/8bit色/16色 进行兼容性处理，整理ANSI转义序列。