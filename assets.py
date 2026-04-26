from PIL import Image, ImageFont
from utils import debug_log
from renderers import ImageRenderer, BinmapImageRenderer
import os

class FontRegistry:
    """字体注册表，用于预加载和管理多种字体实例。"""
    def __init__(self):
        self._fonts = {}

    def register(self, font_id, font_path, size=16, vertical_compress=False):
        """预加载字体并注册 ID。"""
        from font import FontManager
        if not os.path.exists(font_path):
            debug_log(f"[FontRegistry] Error: Font path not found: {font_path}")
            return False
        
        self._fonts[font_id] = FontManager(font_path, size, vertical_compress)
        return True

    def get(self, font_id):
        """获取已注册的字体实例。"""
        return self._fonts.get(font_id)

class ImageRegistry:
    """图像注册表，用于预加载和缓存图像渲染器。"""
    def __init__(self):
        self._images = {}

    def register(self, image_id, path, target_width, mode="color", **kwargs):
        """预加载图像并注册 ID。
        mode: "color" (ImageRenderer) 或 "binmap" (BinmapImageRenderer)
        """
        if not os.path.exists(path):
            debug_log(f"[ImageRegistry] Error: Image path not found: {path}")
            return False

        if mode == "color":
            self._images[image_id] = ImageRenderer(path, target_width, **kwargs)
        elif mode == "binmap":
            self._images[image_id] = BinmapImageRenderer(path, target_width, **kwargs)
        return True

    def get(self, image_id):
        """获取已注册的图像渲染器实例。"""
        return self._images.get(image_id)

# 全局单例
fonts = FontRegistry()
images = ImageRegistry()
