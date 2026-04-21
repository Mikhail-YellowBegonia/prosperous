from PIL import Image, ImageFont
from utils import debug_log

class FontManager:
    def __init__(self, font_path, size=16, vertical_compress=False):
        self.font_path = font_path
        self.size = size
        self.vertical_compress = vertical_compress
        self.atlas = {} 
        
        debug_log(f"[FontManager] Loading: {font_path} at size {size}, vertical_compress={vertical_compress}")
        try:
            self.font = ImageFont.truetype(font_path, size)
            self.ascent, self.descent = self.font.getmetrics()
            self.cell_height = self.ascent + self.descent
            self._generate_atlas()
        except Exception as e:
            debug_log(f"[FontManager] Error: {e}")
            self.font = None

    def _generate_atlas(self):
        valid_count = 0
        for i in range(32, 127):
            char = chr(i)
            try:
                mask, offset = self.font.getmask2(char, mode='L')
                w, h = mask.size
                advance_width = int(self.font.getlength(char))
                if advance_width <= 0: advance_width = self.size // 2
                
                canvas_w, canvas_h = advance_width, self.cell_height
                full_cell_img = Image.new('L', (canvas_w, canvas_h), 0)
                
                if w > 0 and h > 0:
                    full_cell_img.paste(mask, (offset[0], offset[1], offset[0] + w, offset[1] + h))
                
                pixels = full_cell_img.load()
                raw_matrix = [[1 if pixels[x, y] > 127 else 0 for x in range(canvas_w)] for y in range(canvas_h)]
                
                if self.vertical_compress:
                    self.atlas[char] = [raw_matrix[y] for y in range(0, canvas_h, 2)]
                else:
                    self.atlas[char] = raw_matrix
                
                valid_count += 1
            except Exception as e:
                debug_log(f"[FontManager] Error processing '{char}': {e}")
                self.atlas[char] = [[0] * 8 for _ in range(8)]

    def get_char(self, char):
        return self.atlas.get(char, [[0]])

class BigTextRenderer:
    def __init__(self, font_manager):
        self.fm = font_manager

    def render_string(self, text, start_y, start_x, fg=(255, 255, 255), push_binmap_func=None):
        if not text: return
        char_matrices = [self.fm.get_char(c) for c in text if len(self.fm.get_char(c)) > 0]
        if not char_matrices: return

        max_h = max(len(m) for m in char_matrices)
        total_w = sum(len(m[0]) for m in char_matrices)
        full_matrix = [[0 for _ in range(total_w)] for _ in range(max_h)]
        
        curr_x = 0
        for matrix in char_matrices:
            h, w = len(matrix), len(matrix[0])
            for y in range(h):
                for x in range(w):
                    full_matrix[y][curr_x + x] = matrix[y][x]
            curr_x += w
        
        from renderers import BinmapRenderer
        br = BinmapRenderer(full_matrix, fg=fg)
        br.draw(start_y, start_x, push_binmap_func)
