from PIL import Image
from .styles import Style

# 盲文点位到 bit 的映射（标准 Unicode 盲文编码）
# 排列：左列从上到下 bit0/1/2，右列从上到下 bit3/4/5，第4行左右 bit6/7（仅8点）
_BRAILLE_DOT_MAP_6 = [
    (0, 0, 1), (1, 0, 2), (2, 0, 4),
    (0, 1, 8), (1, 1, 16), (2, 1, 32),
]
_BRAILLE_DOT_MAP_8 = _BRAILLE_DOT_MAP_6 + [(3, 0, 64), (3, 1, 128)]


class BinmapRenderer:
    def __init__(self, binmap, fg=(255, 255, 255), bg=None, skip_empty=True):
        self.binmap = binmap
        self.height = len(binmap)
        self.width = len(binmap[0]) if self.height > 0 else 0
        self.fg = fg
        self.bg = bg
        self.skip_empty = skip_empty
        self.char_map = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"

    def draw(self, start_y, start_x, push_binmap_func):
        for y in range(0, self.height, 2):
            for x in range(0, self.width, 2):
                tl = self.binmap[y][x] if y < self.height and x < self.width else 0
                tr = self.binmap[y][x + 1] if y < self.height and x + 1 < self.width else 0
                bl = self.binmap[y + 1][x] if (y + 1) < self.height and x < self.width else 0
                br = (
                    self.binmap[y + 1][x + 1]
                    if (y + 1) < self.height and (x + 1) < self.width
                    else 0
                )
                index = (1 if tl else 0) + (2 if tr else 0) + (4 if bl else 0) + (8 if br else 0)
                if self.skip_empty and index == 0:
                    continue
                push_binmap_func(
                    start_y + (y // 2), start_x + (x // 2), self.char_map[index], self.fg
                )


class BinmapImageRenderer:
    def __init__(self, path, target_width, fg=(255, 255, 255), cell_aspect=2.0):
        self.path = path
        self.fg = fg
        img = Image.open(path).convert("RGBA")
        w, h = img.size
        pixel_w = target_width * 2
        # rows_per_cell=2, denominator = 2 * cell_aspect
        terminal_rows = max(1, round(pixel_w * h / (w * 2 * cell_aspect)))
        pixel_h = terminal_rows * 2
        img = img.resize((pixel_w, pixel_h), Image.Resampling.NEAREST)

        px = img.load()
        self.matrix = [
            [1 if (px[x, y][3] > 0 and sum(px[x, y][:3]) > 0) else 0 for x in range(pixel_w)]
            for y in range(pixel_h)
        ]
        self.renderer = BinmapRenderer(self.matrix, fg=self.fg)

    def draw(self, start_y, start_x, engine, layer=0):
        self.renderer.draw(start_y, start_x,
                           lambda y, x, c, fg: engine.push_binmap(y, x, c, fg, layer=layer))


class BinmapColorRenderer:
    """四象限字符彩色渲染器。

    在 BinmapRenderer 的二值分辨率（2×2 px/格）基础上，为每个格子单独计算
    亮点像素的均值 fg 色和暗点像素的均值 bg 色。

    block_colors: dict { (cell_y, cell_x): (fg_rgb, bg_rgb) }
      fg_rgb / bg_rgb 为 (R, G, B) 元组或 None。
    """

    CHAR_MAP = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"

    def __init__(self, matrix, block_colors, skip_empty=True):
        self.matrix = matrix
        self.block_colors = block_colors
        self.skip_empty = skip_empty
        self.height = len(matrix)
        self.width = len(matrix[0]) if self.height > 0 else 0

    def draw(self, start_y, start_x, push_binmap_func):
        for y in range(0, self.height, 2):
            for x in range(0, self.width, 2):
                tl = self.matrix[y][x]     if y < self.height and x < self.width         else 0
                tr = self.matrix[y][x + 1] if y < self.height and x + 1 < self.width     else 0
                bl = self.matrix[y + 1][x] if y + 1 < self.height and x < self.width     else 0
                br = self.matrix[y + 1][x + 1] if y + 1 < self.height and x + 1 < self.width else 0
                index = (1 if tl else 0) | (2 if tr else 0) | (4 if bl else 0) | (8 if br else 0)
                if self.skip_empty and index == 0:
                    continue
                fg, bg = self.block_colors.get((y // 2, x // 2), (None, None))
                push_binmap_func(
                    start_y + y // 2, start_x + x // 2, self.CHAR_MAP[index], fg, bg
                )


class BinmapColorImageRenderer:
    """从图片文件加载并用四象限彩色字符渲染。

    每个终端格子对应 2×2 原始像素，cell_aspect 补偿终端格子高宽比。
    亮点像素（alpha>0 且亮度>0）均值 → fg；暗点像素均值 → bg（sRGB 直接平均）。
    """

    def __init__(self, path, target_width, cell_aspect=2.0, threshold=10):
        img = Image.open(path).convert("RGBA")
        w, h = img.size
        pixel_w = target_width * 2
        terminal_rows = max(1, round(pixel_w * h / (w * 2 * cell_aspect)))
        pixel_h = terminal_rows * 2
        img = img.resize((pixel_w, pixel_h), Image.Resampling.NEAREST)

        px = img.load()

        # 二值矩阵：与 BinmapImageRenderer 保持一致（>0 阈值）
        self.matrix = [
            [1 if (px[x, y][3] > 0 and sum(px[x, y][:3]) > 0) else 0
             for x in range(pixel_w)]
            for y in range(pixel_h)
        ]

        # 为每个 2×2 块预计算 fg/bg 均值色
        # 透明像素（alpha=0）不参与颜色均值，否则其 RGB(0,0,0) 会将 bg 拉向黑色
        self.block_colors = {}
        for by in range(0, pixel_h, 2):
            for bx in range(0, pixel_w, 2):
                lit, dark = [], []
                for dy in range(2):
                    for dx in range(2):
                        py, ppx = by + dy, bx + dx
                        if py >= pixel_h or ppx >= pixel_w:
                            continue
                        r, g, b, a = px[ppx, py]
                        if self.matrix[py][ppx]:
                            lit.append((r, g, b))
                        elif a > 0:          # 仅不透明的暗像素贡献 bg
                            dark.append((r, g, b))
                fg = _avg_rgb(lit) if lit else None
                bg = _avg_rgb(dark) if dark else None
                self.block_colors[(by // 2, bx // 2)] = (fg, bg)

        self.renderer = BinmapColorRenderer(self.matrix, self.block_colors)

    def draw(self, start_y, start_x, engine, layer=0):
        self.renderer.draw(start_y, start_x,
                           lambda y, x, c, fg, bg=None: engine.push_binmap(y, x, c, fg, bg, layer))


def _avg_rgb(pixels):
    """sRGB 直接平均，返回 (R, G, B) 整数元组。"""
    n = len(pixels)
    return (sum(p[0] for p in pixels) // n,
            sum(p[1] for p in pixels) // n,
            sum(p[2] for p in pixels) // n)


class BrailleColorRenderer:
    """盲文字符彩色渲染器（仅 fg）。

    字符形状由二值矩阵决定，fg 颜色为对应块内所有不透明像素的均值。
    """

    def __init__(self, matrix, block_fg, dots=6, skip_empty=True):
        self.matrix = matrix
        self.block_fg = block_fg
        self.skip_empty = skip_empty
        self.rows_per_cell = 3 if dots == 6 else 4
        self.dot_map = _BRAILLE_DOT_MAP_6 if dots == 6 else _BRAILLE_DOT_MAP_8
        self.height = len(matrix)
        self.width = len(matrix[0]) if self.height > 0 else 0

    def draw(self, start_y, start_x, push_braille_func):
        rpc = self.rows_per_cell
        for cy in range(0, self.height, rpc):
            for cx in range(0, self.width, 2):
                bits = 0
                for dr, dc, bit in self.dot_map:
                    py, px = cy + dr, cx + dc
                    if py < self.height and px < self.width and self.matrix[py][px]:
                        bits |= bit
                if self.skip_empty and bits == 0:
                    continue
                fg = self.block_fg.get((cy // rpc, cx // 2))
                push_braille_func(start_y + cy // rpc, start_x + cx // 2, bits, fg)


class BrailleColorImageRenderer:
    """从图片文件加载并用盲文彩色字符渲染（仅 fg，dots=6 或 8）。

    fg 为块内所有不透明像素的 sRGB 均值，灰度/点阵形状仍由二值化决定。
    """

    def __init__(self, path, target_width, dots=6, cell_aspect=2.0):
        rows_per_cell = 3 if dots == 6 else 4
        img = Image.open(path).convert("RGBA")
        w, h = img.size
        pixel_w = target_width * 2
        terminal_rows = max(1, round(pixel_w * h / (w * 2 * cell_aspect)))
        pixel_h = terminal_rows * rows_per_cell
        img = img.resize((pixel_w, pixel_h), Image.Resampling.NEAREST)

        px = img.load()

        self.matrix = [
            [1 if (px[x, y][3] > 0 and sum(px[x, y][:3]) > 0) else 0 for x in range(pixel_w)]
            for y in range(pixel_h)
        ]

        # 每块内所有不透明像素（alpha>0）取均值 → fg
        self.block_fg = {}
        for cy in range(0, pixel_h, rows_per_cell):
            for cx in range(0, pixel_w, 2):
                opaque = []
                for dr in range(rows_per_cell):
                    for dc in range(2):
                        py, ppx = cy + dr, cx + dc
                        if py >= pixel_h or ppx >= pixel_w:
                            continue
                        r, g, b, a = px[ppx, py]
                        if a > 0:
                            opaque.append((r, g, b))
                if opaque:
                    self.block_fg[(cy // rows_per_cell, cx // 2)] = _avg_rgb(opaque)

        self.renderer = BrailleColorRenderer(self.matrix, self.block_fg, dots=dots)

    def draw(self, start_y, start_x, engine, layer=0):
        self.renderer.draw(start_y, start_x,
                           lambda y, x, bits, fg: engine.push_braille(y, x, bits, fg, layer))


class ImageRenderer:
    _palette_cache = None

    def __init__(self, path, target_width, enable_256_color_reduction=False):
        self.path = path
        self.width = target_width
        self.enable_256_color_reduction = enable_256_color_reduction
        if ImageRenderer._palette_cache is None:
            ImageRenderer._palette_cache = self._generate_ansi256_palette_rgb()

        # Load, resize and cache
        img = Image.open(path).convert("RGBA")
        aspect = img.height / img.width
        self.height = int(self.width * aspect)
        if self.height % 2 != 0:
            self.height = max(2, self.height - 1)
        img = img.resize((self.width, self.height), Image.Resampling.NEAREST)

        self.pixels = img.load()
        self.processed_colors = [[None for _ in range(self.width)] for _ in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                p = self.pixels[x, y]
                self.processed_colors[y][x] = (
                    self._rgb_to_ansi256(p) if enable_256_color_reduction else p
                )

    @staticmethod
    def _generate_ansi256_palette_rgb():
        p = [
            (0, 0, 0),
            (128, 0, 0),
            (0, 128, 0),
            (128, 128, 0),
            (0, 0, 128),
            (128, 0, 128),
            (0, 128, 128),
            (192, 192, 192),
            (128, 128, 128),
            (255, 0, 0),
            (0, 255, 0),
            (255, 255, 0),
            (0, 0, 255),
            (255, 0, 255),
            (0, 255, 255),
            (255, 255, 255),
        ]
        levels = [0, 95, 135, 175, 215, 255]
        for r in range(6):
            for g in range(6):
                for b in range(6):
                    p.append((levels[r], levels[g], levels[b]))
        for i in range(24):
            gray = 8 + i * 10
            p.append((gray, gray, gray))
        return p

    def _rgb_to_ansi256(self, rgb):
        r, g, b = rgb[:3]
        min_dist = float("inf")
        idx = 0
        for i, (pr, pg, pb) in enumerate(self._palette_cache):
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < min_dist:
                min_dist, idx = d, i
        return idx

    def draw(self, start_y, start_x, engine, layer=0):
        threshold = 128
        for y in range(0, self.height, 2):
            for x in range(self.width):
                t_raw, b_raw = self.pixels[x, y], self.pixels[x, y + 1]
                t_col, b_color = self.processed_colors[y][x], self.processed_colors[y + 1][x]
                t_alpha = t_raw[3] if len(t_raw) > 3 else 255
                b_alpha = b_raw[3] if len(b_raw) > 3 else 255

                if t_alpha < threshold and b_alpha < threshold:
                    continue
                elif t_alpha < threshold:
                    engine.push_image(start_y + (y // 2), start_x + x, "▄", b_color, None, layer)
                elif b_alpha < threshold:
                    engine.push_image(start_y + (y // 2), start_x + x, "▀", t_col, None, layer)
                else:
                    engine.push_image(start_y + (y // 2), start_x + x, "▀", t_col, b_color, layer)


class BrailleRenderer:
    """盲文字符单色渲染器。将二值矩阵映射到盲文 Unicode 字符（U+2800–U+28FF）。

    每个终端格子对应 2×3（6点）或 2×4（8点）像素，分辨率分别是 half-block 的 3× 和 4×。
    """

    def __init__(self, matrix, dots=8, fg=(255, 255, 255), skip_empty=True):
        self.matrix = matrix
        self.fg = fg
        self.skip_empty = skip_empty
        self.rows_per_cell = 3 if dots == 6 else 4
        self.dot_map = _BRAILLE_DOT_MAP_6 if dots == 6 else _BRAILLE_DOT_MAP_8
        self.height = len(matrix)
        self.width = len(matrix[0]) if self.height > 0 else 0

    def draw(self, start_y, start_x, push_braille_func):
        rpc = self.rows_per_cell
        for cy in range(0, self.height, rpc):
            for cx in range(0, self.width, 2):
                bits = 0
                for dr, dc, bit in self.dot_map:
                    py, px = cy + dr, cx + dc
                    if py < self.height and px < self.width and self.matrix[py][px]:
                        bits |= bit
                if self.skip_empty and bits == 0:
                    continue
                push_braille_func(start_y + cy // rpc, start_x + cx // 2, bits, self.fg)


class BrailleImageRenderer:
    """从图片文件加载并用盲文字符渲染的单色渲染器。

    dots=6 → 2×3 像素/格（分辨率 3× half-block）
    dots=8 → 2×4 像素/格（分辨率 4× half-block）
    """

    def __init__(self, path, target_width, fg=(255, 255, 255), dots=8, cell_aspect=2.0):
        self.fg = fg
        rows_per_cell = 3 if dots == 6 else 4

        img = Image.open(path).convert("RGBA")
        w, h = img.size
        pixel_w = target_width * 2
        # terminal_rows 对所有方法通用，pixel_h 按 rows_per_cell 对齐
        terminal_rows = max(1, round(pixel_w * h / (w * 2 * cell_aspect)))
        pixel_h = terminal_rows * rows_per_cell
        img = img.resize((pixel_w, pixel_h), Image.Resampling.NEAREST)

        px = img.load()
        self.matrix = [
            [1 if (px[x, y][3] > 0 and sum(px[x, y][:3]) > 0) else 0 for x in range(pixel_w)]
            for y in range(pixel_h)
        ]
        self.renderer = BrailleRenderer(self.matrix, dots=dots, fg=fg)

    def draw(self, start_y, start_x, engine, layer=0):
        self.renderer.draw(start_y, start_x,
                           lambda y, x, bits, fg: engine.push_braille(y, x, bits, fg, layer))
