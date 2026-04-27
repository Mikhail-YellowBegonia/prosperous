import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from live import Live
from assets import images

IMG_PATH = os.path.join(os.path.dirname(__file__), "img", "square_cat.png")
TARGET_W = 20
GAP = 2

images.register("color",          IMG_PATH, TARGET_W, mode="color")
images.register("binmap",         IMG_PATH, TARGET_W, mode="binmap",        fg=(255, 255, 255))
images.register("binmap_color",   IMG_PATH, TARGET_W, mode="binmap_color")
images.register("braille6",       IMG_PATH, TARGET_W, mode="braille6",      fg=(255, 255, 255))
images.register("braille6_color", IMG_PATH, TARGET_W, mode="braille6_color")

STRIDE = TARGET_W + GAP
METHODS = [
    ("half-block (color)",  0,          "color"),
    ("binmap     (mono)",   STRIDE,     "binmap"),
    ("binmap     (color)",  STRIDE * 2, "binmap_color"),
    ("braille6   (mono)",   STRIDE * 3, "braille6"),
    ("braille6   (color)",  STRIDE * 4, "braille6_color"),
]

with Live(fps=10) as live:
    while live.running:
        keys = live.poll()
        if "q" in keys or "Q" in keys:
            live.stop()

        with live.frame():
            for label, col, img_id in METHODS:
                live.engine.push(0, col, label)
                r = images.get(img_id)
                if r:
                    r.draw(1, col, live.engine)
