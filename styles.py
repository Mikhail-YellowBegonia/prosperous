from dataclasses import dataclass, field
from typing import Optional, Union, Tuple

@dataclass
class Style:
    fg: Optional[Union[int, Tuple[int, int, int]]] = None
    bg: Optional[Union[int, Tuple[int, int, int]]] = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False
    reverse: bool = False
    hidden: bool = False
    strike: bool = False

    def merge(self, other: 'Style') -> 'Style':
        """将另一个样式的非空属性合并到当前样式，返回新样式"""
        new_style = Style(
            fg=other.fg if other.fg is not None else self.fg,
            bg=other.bg if other.bg is not None else self.bg,
            bold=other.bold or self.bold,
            dim=other.dim or self.dim,
            italic=other.italic or self.italic,
            underline=other.underline or self.underline,
            blink=other.blink or self.blink,
            reverse=other.reverse or self.reverse,
            hidden=other.hidden or self.hidden,
            strike=other.strike or self.strike,
        )
        return new_style

# 系统默认样式
DEFAULT_STYLE = Style(fg=15, bg=None)
ANSI_RESET = "\033[0m"
