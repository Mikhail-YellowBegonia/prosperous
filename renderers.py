from PIL import Image

class BinmapRenderer:
    def __init__(self, binmap, fg=(255, 255, 255), bg=None, skip_empty=True):
        self.binmap = binmap
        self.height = len(binmap)
        self.width = len(binmap[0]) if self.height > 0 else 0
        self.fg = fg
        self.bg = bg
        self.skip_empty = skip_empty
        self.char_map = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"

    def draw(self, start_y, start_x, push_func):
        for y in range(0, self.height, 2):
            for x in range(0, self.width, 2):
                tl = self.binmap[y][x] if y < self.height and x < self.width else 0
                tr = self.binmap[y][x+1] if y < self.height and x+1 < self.width else 0
                bl = self.binmap[y+1][x] if (y+1) < self.height and x < self.width else 0
                br = self.binmap[y+1][x+1] if (y+1) < self.height and (x+1) < self.width else 0
                index = (1 if tl else 0) + (2 if tr else 0) + (4 if bl else 0) + (8 if br else 0)
                if self.skip_empty and index == 0: continue
                push_func(start_y + (y // 2), start_x + (x // 2), self.char_map[index], self.fg, self.bg, 0)

class BinmapImageRenderer:
    def __init__(self, path, target_width, fg=(255, 255, 255), vertical_compress=True):
        self.path = path
        self.fg = fg
        img = Image.open(path).convert('RGBA')
        w, h = img.size
        pixel_w = target_width * 2
        pixel_h = int(pixel_w * (h / w))
        img = img.resize((pixel_w, pixel_h), Image.Resampling.NEAREST)
        if vertical_compress:
            pixel_h = max(1, pixel_h // 2)
            img = img.resize((pixel_w, pixel_h), Image.Resampling.NEAREST)
        
        self.matrix = []
        px = img.load()
        for y in range(pixel_h):
            row = [1 if (px[x, y][3] > 0 and sum(px[x, y][:3]) > 0) else 0 for x in range(pixel_w)]
            self.matrix.append(row)
        self.renderer = BinmapRenderer(self.matrix, fg=self.fg)

    def draw(self, start_y, start_x, push_func):
        self.renderer.draw(start_y, start_x, push_func)

class ImageRenderer:
    _palette_cache = None

    def __init__(self, path, target_width, enable_256_color_reduction=False):
        self.path = path
        self.width = target_width
        self.enable_256_color_reduction = enable_256_color_reduction
        if ImageRenderer._palette_cache is None:
            ImageRenderer._palette_cache = self._generate_ansi256_palette_rgb()
        
        # Load, resize and cache
        img = Image.open(path).convert('RGBA')
        aspect = img.height / img.width
        self.height = int(self.width * aspect)
        if self.height % 2 != 0: self.height = max(2, self.height - 1)
        img = img.resize((self.width, self.height), Image.Resampling.NEAREST)
        
        self.pixels = img.load()
        self.processed_colors = [[None for _ in range(self.width)] for _ in range(self.height)]
        for y in range(self.height):
            for x in range(self.width):
                p = self.pixels[x, y]
                self.processed_colors[y][x] = self._rgb_to_ansi256(p) if enable_256_color_reduction else p

    @staticmethod
    def _generate_ansi256_palette_rgb():
        p = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192), (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0), (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)]
        levels = [0, 95, 135, 175, 215, 255]
        for r in range(6):
            for g in range(6):
                for b in range(6): p.append((levels[r], levels[g], levels[b]))
        for i in range(24):
            gray = 8 + i * 10
            p.append((gray, gray, gray))
        return p

    def _rgb_to_ansi256(self, rgb):
        r, g, b = rgb[:3]
        min_dist = float('inf')
        idx = 0
        for i, (pr, pg, pb) in enumerate(self._palette_cache):
            d = (r-pr)**2 + (g-pg)**2 + (b-pb)**2
            if d < min_dist:
                min_dist, idx = d, i
        return idx

    def draw(self, start_y, start_x, push_func):
        threshold = 128
        for y in range(0, self.height, 2):
            for x in range(self.width):
                t_raw, b_raw = self.pixels[x, y], self.pixels[x, y+1]
                t_col, b_color = self.processed_colors[y][x], self.processed_colors[y+1][x]
                t_alpha = t_raw[3] if len(t_raw) > 3 else 255
                b_alpha = b_raw[3] if len(b_raw) > 3 else 255

                if t_alpha < threshold and b_alpha < threshold: continue
                elif t_alpha < threshold: push_func(start_y + (y // 2), start_x + x, "▄", b_color, None, 0)
                elif b_alpha < threshold: push_func(start_y + (y // 2), start_x + x, "▀", t_col, None, 0)
                else: push_func(start_y + (y // 2), start_x + x, "▀", t_col, b_color, 0)
