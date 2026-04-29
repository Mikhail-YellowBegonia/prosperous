import re
from typing import List, Tuple, Optional
from .styles import Style, DEFAULT_STYLE
from .theme import get_theme
from .utils import get_visual_width

def wrap_segments(segments: List[Tuple[str, Style]], width: int) -> List[List[Tuple[str, Style]]]:
    """
    将一组富文本片段 (text, style) 根据宽度折行。
    
    参数:
        segments: 格式为 [(text, style), ...]
        width: 最大视觉宽度限制。
        
    返回:
        List[List[Tuple[str, Style]]]: 折行后的多行片段列表。
    """
    if width <= 0:
        return [segments]
        
    lines = []
    current_line = []
    current_width = 0
    
    for text, style in segments:
        if not text:
            continue
            
        style = style or DEFAULT_STYLE
        
        # 逐字符处理以支持精确折行
        pending_text = ""
        for char in text:
            char_w = get_visual_width(char)
            
            # 如果加上这个字符就超宽了
            if current_width + char_w > width:
                # 提交当前行
                if pending_text:
                    current_line.append((pending_text, style))
                if current_line:
                    lines.append(current_line)
                
                # 重置新行
                current_line = []
                current_width = 0
                pending_text = ""
                
                # 如果单个字符就比总宽度还宽（极窄容器），也得强行放下
                if char_w > width:
                    lines.append([(char, style)])
                    continue

            pending_text += char
            current_width += char_w
            
        # 段落处理完后，将剩余部分加入当前行
        if pending_text:
            current_line.append((pending_text, style))
            
    if current_line:
        lines.append(current_line)
        
    return lines if lines else [[]]

class MarkupParser:
    """Prosperous 标记解析器。
    语法: <tag>内容</> 或 <#theme_id>内容</>
    支持嵌套和换行。
    """
    
    # 组 1 匹配 <tag> 或 <#tag>，但不匹配以 / 开头的结束标签
    TOKEN_RE = re.compile(r'(<#?[^/][^>]*>)|(</>)')

    @classmethod
    def parse_to_lines(cls, text: str, base_style: Optional[Style] = None) -> List[List[Tuple[str, Style]]]:
        """将带标记的字符串解析为多行段落。
        返回格式: [ [(text, style), ...], [(text, style), ...] ]
        """
        base_style = base_style or DEFAULT_STYLE
        lines = text.split('\n')
        result_lines = []

        for line in lines:
            result_lines.append(cls._parse_line(line, base_style))
            
        return result_lines

    @classmethod
    def _parse_line(cls, line: str, base_style: Style) -> List[Tuple[str, Style]]:
        if not line:
            return [("", base_style)]

        segments = []
        style_stack = [base_style]
        
        last_pos = 0
        for match in cls.TOKEN_RE.finditer(line):
            # 1. 提取标签前的文本
            content = line[last_pos:match.start()]
            if content:
                segments.append((content, style_stack[-1]))
            
            # 2. 识别是开启标签还是关闭标签
            tag_match = match.group(1)   # <...>
            close_match = match.group(2) # </>
            
            if tag_match:
                tag_val = tag_match[1:-1]
                new_style = cls._resolve_style(tag_val, style_stack[-1])
                style_stack.append(new_style)
            elif close_match:
                if len(style_stack) > 1:
                    style_stack.pop()
            
            last_pos = match.end()
            
        # 3. 处理最后一段剩余文本
        remaining = line[last_pos:]
        if remaining:
            segments.append((remaining, style_stack[-1]))
            
        return segments

    @staticmethod
    def _resolve_style(tag: str, current_style: Style) -> Style:
        """解析标签值为 Style 对象。支持 #id, 颜色名和属性名。"""
        if tag.startswith('#'):
            # 主题查询
            theme_params = get_theme(tag)
            if not theme_params:
                return current_style
            s = theme_params.get("style") if isinstance(theme_params, dict) else None
            return current_style.merge(s) if isinstance(s, Style) else current_style
        
        # 临时样式解析
        parts = tag.split()
        new_params = {}
        
        # 简单关键字映射
        attrs = {"bold", "dim", "italic", "underline", "blink", "reverse", "hidden", "strike"}
        colors = {
            "black": 0, "red": 1, "green": 2, "yellow": 3, "blue": 4, "magenta": 5, "cyan": 6, "white": 7,
            "bright_black": 8, "bright_red": 9, "bright_green": 10, "bright_yellow": 11,
            "bright_blue": 12, "bright_magenta": 13, "bright_cyan": 14, "bright_white": 15
        }

        for p in parts:
            p = p.lower()
            if p in attrs:
                new_params[p] = True
            elif p in colors:
                if not new_params.get("fg"): # 优先作为前景色
                    new_params["fg"] = colors[p]
            elif p.startswith("bg:"):
                color_name = p[3:]
                if color_name in colors:
                    new_params["bg"] = colors[color_name]
                elif color_name.startswith("#") and len(color_name) == 7:
                    # HEX 支持
                    try:
                        r = int(color_name[1:3], 16)
                        g = int(color_name[3:5], 16)
                        b = int(color_name[5:7], 16)
                        new_params["bg"] = (r, g, b)
                    except ValueError: pass
            elif p.startswith("#") and len(p) == 7:
                # 前景 HEX 支持
                try:
                    r = int(p[1:3], 16)
                    g = int(p[3:5], 16)
                    b = int(p[5:7], 16)
                    new_params["fg"] = (r, g, b)
                except ValueError: pass

        if not new_params:
            return current_style
            
        return current_style.merge(Style(**new_params))

def parse_markup(text: str, base_style: Optional[Style] = None) -> List[List[Tuple[str, Style]]]:
    return MarkupParser.parse_to_lines(text, base_style)
