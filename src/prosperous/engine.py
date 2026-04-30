import os
import sys
import time
import threading
import signal
from .utils import clear_screen, debug_log, get_visual_width
from .markup import parse_markup
from .styles import Style, DEFAULT_STYLE, BOX_SINGLE


class _RenderContext:
    """终端样式状态追踪器，用于计算最小 ANSI 增量序列。"""

    __slots__ = (
        "fg",
        "bg",
        "bold",
        "dim",
        "italic",
        "underline",
        "blink",
        "reverse",
        "hidden",
        "strike",
    )

    _ATTRS = ("bold", "dim", "italic", "underline", "blink", "reverse", "hidden", "strike")
    _ON = {
        "bold": "1",
        "dim": "2",
        "italic": "3",
        "underline": "4",
        "blink": "5",
        "reverse": "7",
        "hidden": "8",
        "strike": "9",
    }
    _OFF = {
        "italic": "23",
        "underline": "24",
        "blink": "25",
        "reverse": "27",
        "hidden": "28",
        "strike": "29",
    }

    def __init__(self):
        self.reset()

    def reset(self):
        self.fg = self.bg = None
        self.bold = self.dim = self.italic = self.underline = False
        self.blink = self.reverse = self.hidden = self.strike = False

    def diff(self, style: Style) -> str:
        """返回从当前终端状态过渡到 style 所需的最小 ANSI 序列。无变化返回空字符串。"""
        parts = []

        # bold/dim 共用关闭码 22；任一需要关闭时发一次 22，再补回应保持开启的那个
        bold_dim_off = (self.bold and not style.bold) or (self.dim and not style.dim)
        if bold_dim_off:
            parts.append("22")
            if style.bold:
                parts.append(self._ON["bold"])
            if style.dim:
                parts.append(self._ON["dim"])

        # 其余布尔属性
        for a in ("italic", "underline", "blink", "reverse", "hidden", "strike"):
            was, want = getattr(self, a), getattr(style, a)
            if was and not want:
                parts.append(self._OFF[a])
            elif not was and want:
                parts.append(self._ON[a])

        # bold/dim 开启（尚未被上面 bold_dim_off 分支处理的情况）
        if not bold_dim_off:
            if not self.bold and style.bold:
                parts.append(self._ON["bold"])
            if not self.dim and style.dim:
                parts.append(self._ON["dim"])

        # fg
        if style.fg != self.fg:
            parts.append(self._color_seq(style.fg, fg=True))

        # bg
        if style.bg != self.bg:
            parts.append(self._color_seq(style.bg, fg=False))

        # 更新状态
        self.fg, self.bg = style.fg, style.bg
        for a in self._ATTRS:
            setattr(self, a, getattr(style, a))

        return ("\033[" + ";".join(parts) + "m") if parts else ""

    @staticmethod
    def _color_seq(color, fg: bool) -> str:
        base_fg, base_bg, bright_fg, bright_bg = 30, 40, 90, 100
        if color is None:
            return "39" if fg else "49"
        if isinstance(color, int):
            if color < 8:
                return str((base_fg if fg else base_bg) + color)
            if color < 16:
                return str((bright_fg if fg else bright_bg) + (color - 8))
            return f"{'38' if fg else '48'};5;{color}"
        return f"{'38' if fg else '48'};2;{color[0]};{color[1]};{color[2]}"


class RenderEngine:
    QUAD_CHAR_MAP = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"
    QUAD_TO_BITS = {c: i for i, c in enumerate(QUAD_CHAR_MAP)}

    def __init__(self):
        self.lock = threading.Lock()
        self.is_running = True
        self.cli_width = 80
        self.cli_height = 24

        # Primary Buffers
        self.screen_logic = []  # Logic 线程私有缓冲区 (无锁写入)
        self.screen_prepare = []  # 待交换缓冲区 (持锁提交)
        self.screen_buffer = []  # 渲染线程读取缓冲区
        self.screen_dump = []  # 差分对比缓冲区
        self.screen_diff = []

        # Compositing Spaces
        self.image_space = []
        self.binmap_space = []
        self.braille_space = []
        self.dirty_cells = set()

        # Clipping
        self._clip_stack = []
        self._current_clip = None  # (y, x, h, w)

        # Input State
        self.last_key = None
        self.input_events = []

        self.last_cursor_pos = (-1, -1)
        self.size_dump = (0, 0)
        self._resize_pending = False
        self._render_ctx = _RenderContext()

        # SIGWINCH 只设 flag，实际 resize 在 poll() 调用 listen_size() 时执行，避免持锁期间死锁
        try:
            signal.signal(
                signal.SIGWINCH, lambda signum, frame: setattr(self, "_resize_pending", True)
            )
        except AttributeError:
            pass

        self.listen_size()
        # 隐藏硬件光标 + 开启 SGR 鼠标按键上报（含滚轮）
        sys.stdout.write("\033[?25l\033[?1000h\033[?1006h")
        sys.stdout.flush()

    def push_clip(self, y, x, h, w):
        """推送一个新的裁剪区域，新区域会与当前区域取交集。"""
        if self._current_clip is None:
            new_clip = (y, x, h, w)
        else:
            cy, cx, ch, cw = self._current_clip
            # 计算交集
            ny = max(y, cy)
            nx = max(x, cx)
            ny_end = min(y + h, cy + ch)
            nx_end = min(x + w, cx + cw)
            nh = max(0, ny_end - ny)
            nw = max(0, nx_end - nx)
            new_clip = (ny, nx, nh, nw)

        self._clip_stack.append(self._current_clip)
        self._current_clip = new_clip

    def pop_clip(self):
        """恢复上一个裁剪区域。"""
        if self._clip_stack:
            self._current_clip = self._clip_stack.pop()
        else:
            self._current_clip = None

    def get_current_clip(self) -> Optional[tuple]:
        """获取当前生效的裁剪区域 (y, x, h, w)。None 表示不限制（全屏）。"""
        return self._current_clip

    def listen_size(self):
        if not self._resize_pending and self.size_dump != (0, 0):
            return
        try:
            size = os.get_terminal_size()
        except OSError:
            return

        if size != self.size_dump:
            with self.lock:
                self.cli_width = size.columns
                self.cli_height = size.lines

                self.screen_logic = [
                    [(" ", DEFAULT_STYLE) for _ in range(self.cli_width)]
                    for _ in range(self.cli_height)
                ]
                self.screen_prepare = [
                    [(" ", DEFAULT_STYLE) for _ in range(self.cli_width)]
                    for _ in range(self.cli_height)
                ]
                self.screen_buffer = [
                    [(" ", DEFAULT_STYLE) for _ in range(self.cli_width)]
                    for _ in range(self.cli_height)
                ]
                self.screen_dump = [
                    [("A", DEFAULT_STYLE) for _ in range(self.cli_width)]
                    for _ in range(self.cli_height)
                ]

                self.image_space = [
                    [None for _ in range(self.cli_width)] for _ in range(self.cli_height)
                ]
                self.binmap_space = [
                    [None for _ in range(self.cli_width)] for _ in range(self.cli_height)
                ]
                self.braille_space = [
                    [None for _ in range(self.cli_width)] for _ in range(self.cli_height)
                ]
                self.dirty_cells.clear()
                self.screen_diff = []

                clear_screen()
                self._render_ctx.reset()
            self.size_dump = size
        self._resize_pending = False

    def clear_prepare(self):
        """清空 Logic 线程私有缓冲区。"""
        blank = (" ", DEFAULT_STYLE)
        for y in range(self.cli_height):
            self.screen_logic[y] = [blank] * self.cli_width

    def clear_rect(self, y, x, height, width, style=None):
        """清理屏幕指定区域。

        该操作会同时填充私有缓冲区 (screen_logic) 和重置高分辨率层 (image_space)。
        建议组件在 draw() 开始时调用，以实现类似“层级刷新”的效果。
        """
        if style is None:
            style = DEFAULT_STYLE
        blank = (" ", style)

        max_y = min(y + height, self.cli_height)
        max_x = min(x + width, self.cli_width)

        for iy in range(max(0, y), max_y):
            start_ix = max(0, x)
            if start_ix < max_x:
                # 填充私有缓冲区
                self.screen_logic[iy][start_ix:max_x] = [blank] * (max_x - start_ix)
                # 清理高像素/位图空间（如果存在）
                if self.image_space:
                    for ix in range(start_ix, max_x):
                        self.image_space[iy][ix] = None
                        self.binmap_space[iy][ix] = None
                        self.braille_space[iy][ix] = None

    def commit_logic(self):
        """将 Logic 线程私有缓冲区提交到准备区。仅此处需短时间持锁。"""
        with self.lock:
            # 执行指针交换 (O(1))
            self.screen_logic, self.screen_prepare = self.screen_prepare, self.screen_logic

    def clear_spaces(self):
        for y, x in self.dirty_cells:
            if y < len(self.image_space) and x < len(self.image_space[0]):
                self.image_space[y][x] = None
                self.binmap_space[y][x] = None
                self.braille_space[y][x] = None
        self.dirty_cells.clear()

    def push(self, y, x, content, style=None):
        """将字符串写入私有渲染缓冲区 (screen_logic)。支持裁剪。"""
        if style is None:
            style = DEFAULT_STYLE
        if not self.screen_logic or y < 0 or y >= len(self.screen_logic):
            return

        if self._current_clip:
            cy, cx, ch, cw = self._current_clip
            if y < cy or y >= cy + ch:
                return
            limit_x = min(len(self.screen_logic[0]), cx + cw)
            start_x = cx
        else:
            limit_x = len(self.screen_logic[0])
            start_x = 0

        curr_x = x
        for char in content:
            if curr_x >= limit_x:
                break
            width = 2 if ord(char) > 128 and not (0x2500 <= ord(char) <= 0x259F) else 1

            if curr_x >= start_x:
                self.screen_logic[y][curr_x] = (char, style)
                if width == 2:
                    if curr_x + 1 < limit_x:
                        self.screen_logic[y][curr_x + 1] = ("", style)
                    curr_x += 2
                else:
                    curr_x += 1
            else:
                curr_x += width

    def fill_rect(self, y, x, height, width, char=" ", style=None):
        """用 char+style 填充矩形区域，不影响 image_space 合成层。"""
        if style is None:
            style = DEFAULT_STYLE
        row = char * width
        for i in range(height):
            self.push(y + i, x, row, style)

    def draw_vline(self, y, x, length, char, style=None):
        """在 (y, x) 向下绘制长度为 length 的垂直线。"""
        for i in range(length):
            self.push(y + i, x, char, style)

    def draw_hline(self, y, x, width, char, style=None):
        """在 (y, x) 向右绘制长度为 width 的水平线。"""
        self.push(y, x, char * width, style)

    def write(self, y, x, text, style=None, width=None, align="left", markup=True):
        """增强型文本写入，支持富文本、对齐和截断。

        参数：
            y, x:   起始坐标。
            text:   文本内容（支持 markup 标签）。
            style:  基础样式，markup 会在此基础上合并。
            width:  显示宽度限制，提供对齐参考及溢出截断。
            align:  对齐方式 ("left", "center", "right")，仅在提供 width 时生效。
            markup: 是否解析 markup 标签，默认为 True。
        """
        # 1. 解析 Markup 或 简单文本
        if markup:
            # parse_markup 返回格式：[ [(text, style), ...], ... ] (多行列表)
            # write 定位为单行增强写入，我们只取第一行
            parsed_lines = parse_markup(text, style)
            segments = parsed_lines[0] if parsed_lines else []
        else:
            segments = [(text, style or DEFAULT_STYLE)]

        # 2. 计算视觉总宽度
        total_visual_width = sum(get_visual_width(txt) for txt, _ in segments)

        # 3. 计算对齐偏移
        offset_x = 0
        if width is not None:
            if align == "center":
                offset_x = max(0, (width - total_visual_width) // 2)
            elif align == "right":
                offset_x = max(0, width - total_visual_width)

        # 4. 执行写入与视觉截断
        curr_rel_x = 0
        remaining_budget = width if width is not None else float("inf")

        for txt, segment_style in segments:
            if remaining_budget <= 0:
                break

            # 检查该段文本是否会超出剩余预算
            seg_width = get_visual_width(txt)
            if seg_width <= remaining_budget:
                # 整段写入
                self.push(y, x + offset_x + curr_rel_x, txt, segment_style)
                curr_rel_x += seg_width
                remaining_budget -= seg_width
            else:
                # 溢出截断：逐字符计算剩余预算
                truncated_txt = ""
                acc = 0
                for char in txt:
                    cw = get_visual_width(char)
                    if acc + cw > remaining_budget:
                        break
                    truncated_txt += char
                    acc += cw
                self.push(y, x + offset_x + curr_rel_x, truncated_txt, segment_style)
                break  # 已达宽度上限，停止处理后续片段

    def draw_box(self, y, x, height, width, style=None, border=None):
        """绘制带边框的矩形轮廓（不填充内部）。

        border: 8字符字符串，索引约定与 Box 组件一致：
                0:TL 1:TR 2:BL 3:BR 4:上横 5:下横 6:左竖 7:右竖
        """
        b = border if border is not None else BOX_SINGLE
        inner = width - 2
        self.push(y, x, b[0] + b[4] * inner + b[1], style)
        self.push(y + height - 1, x, b[2] + b[5] * inner + b[3], style)
        self.draw_vline(y + 1, x, height - 2, b[6], style)
        self.draw_vline(y + 1, x + width - 1, height - 2, b[7], style)

    def _space_in_bounds(self, y, x) -> bool:
        if not (
            bool(self.image_space)
            and 0 <= y < len(self.image_space)
            and 0 <= x < len(self.image_space[0])
        ):
            return False

        if self._current_clip:
            cy, cx, ch, cw = self._current_clip
            return cy <= y < cy + ch and cx <= x < cx + cw
        return True

    def push_image(self, y, x, char, fg, bg, layer=0):
        if not self._space_in_bounds(y, x):
            return
        if self.image_space[y][x] is None:
            self.image_space[y][x] = [None, None, layer]
        if char == "▀":
            self.image_space[y][x][0] = fg
            if bg is not None:
                self.image_space[y][x][1] = bg
        elif char == "▄":
            self.image_space[y][x][1] = fg
        elif char == "█":
            self.image_space[y][x][0] = fg
            self.image_space[y][x][1] = bg
        self.dirty_cells.add((y, x))

    def push_binmap(self, y, x, char, fg, bg=None, layer=0):
        if not self._space_in_bounds(y, x):
            return
        bits = self.QUAD_TO_BITS.get(char, 0)
        if bits == 0:
            return
        if self.binmap_space[y][x] is None:
            self.binmap_space[y][x] = [0, fg, bg, layer]
        self.binmap_space[y][x][0] |= bits
        if fg is not None:
            self.binmap_space[y][x][1] = fg
        if bg is not None:
            self.binmap_space[y][x][2] = bg
        self.dirty_cells.add((y, x))

    def push_braille(self, y, x, bits, fg, layer=0):
        """将盲文点阵写入合成层。bits 为 8 位掩码（6-dot 只用低6位），fg 为前景色。"""
        if not self._space_in_bounds(y, x):
            return
        if self.braille_space[y][x] is None:
            self.braille_space[y][x] = [0, fg, layer]
        self.braille_space[y][x][0] |= bits
        if fg is not None:
            self.braille_space[y][x][1] = fg
        self.dirty_cells.add((y, x))

    # layer 优先级常量：相同 layer 时 braille > image > binmap
    _SPACE_PRIO = {"binmap": 0, "image": 1, "braille": 2}

    def flush_spaces(self):
        if not self.screen_prepare or not self.image_space:
            return
        limit_y, limit_x = len(self.screen_prepare), len(self.screen_prepare[0])

        for y, x in self.dirty_cells:
            if y >= limit_y or x >= limit_x:
                continue

            bm = self.binmap_space[y][x]
            img = self.image_space[y][x]
            br = self.braille_space[y][x]

            bm_valid = bm is not None and bm[0] > 0
            img_valid = img is not None and (img[0] is not None or img[1] is not None)
            br_valid = br is not None and br[0] > 0

            # 无冲突快路径（绝大多数情况）
            n = bm_valid + img_valid + br_valid
            if n == 0:
                continue
            if n == 1:
                if bm_valid:
                    self.push(y, x, self.QUAD_CHAR_MAP[bm[0]], Style(fg=bm[1], bg=bm[2]))
                elif img_valid:
                    self._flush_image_cell(y, x, img)
                else:
                    self.push(y, x, chr(0x2800 | br[0]), Style(fg=br[1]))
                continue

            # 冲突：按 (layer, type_priority) 取最高者
            best_key = (-1, -1)
            winner = None
            if bm_valid:
                k = (bm[3], self._SPACE_PRIO["binmap"])
                if k > best_key:
                    best_key, winner = k, ("binmap", bm)
            if img_valid:
                k = (img[2], self._SPACE_PRIO["image"])
                if k > best_key:
                    best_key, winner = k, ("image", img)
            if br_valid:
                k = (br[2], self._SPACE_PRIO["braille"])
                if k > best_key:
                    best_key, winner = k, ("braille", br)

            wtype, wdata = winner
            if wtype == "binmap":
                self.push(y, x, self.QUAD_CHAR_MAP[wdata[0]], Style(fg=wdata[1], bg=wdata[2]))
            elif wtype == "image":
                self._flush_image_cell(y, x, wdata)
            else:
                self.push(y, x, chr(0x2800 | wdata[0]), Style(fg=wdata[1]))

    def _flush_image_cell(self, y, x, img):
        if img[0] is not None and img[1] is not None:
            self.push(y, x, "▀", Style(fg=img[0], bg=img[1]))
        elif img[0] is not None:
            self.push(y, x, "▀", Style(fg=img[0]))
        else:
            self.push(y, x, "▄", Style(fg=img[1]))

    def swap_buffers(self):
        with self.lock:
            self.screen_prepare, self.screen_buffer = self.screen_buffer, self.screen_prepare

    def find_diff(self):
        self.screen_diff.clear()
        for y in range(len(self.screen_buffer)):
            for x in range(len(self.screen_buffer[y])):
                if self.screen_buffer[y][x] != self.screen_dump[y][x]:
                    char, style = self.screen_buffer[y][x]
                    self.screen_diff.append((y, x, char, style))

    def render(self):
        self.find_diff()
        if not self.screen_diff:
            return

        ctx = self._render_ctx
        for y, x, char, style in self.screen_diff:
            if y != self.last_cursor_pos[0] or x != self.last_cursor_pos[1] + 1:
                sys.stdout.write(f"\033[{y + 1};{x + 1}H")
            ansi = ctx.diff(style)
            if ansi:
                sys.stdout.write(ansi)
            sys.stdout.write(char)
            self.last_cursor_pos = (y, x)

        sys.stdout.flush()
        self.screen_dump = [row[:] for row in self.screen_buffer]
