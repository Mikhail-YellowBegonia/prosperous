from styles import Style

DEFAULT_THEME = {
    "Panel": {
        "padding": 1,
        "style": Style(fg=15),
    },
    "InputBox": {
        "focus_style": Style(fg=220),
    },
    "Button": {
        "focus_style": Style(fg=220, bold=True),
    },
    "Text": {},
    "ProgressBar": {
        "filled_style": Style(fg=(80, 200, 120)),
        "empty_style": Style(fg=(60, 60, 60)),
    },
    "LogView": {},
}

_theme: dict = dict(DEFAULT_THEME)


def set_theme(theme: dict) -> None:
    """替换全局 Theme。通常在 Live 上下文之前调用一次。"""
    global _theme
    _theme = theme


def get_theme(type_name: str) -> dict:
    """返回指定组件类型的 Theme 参数字典，找不到时返回空字典。"""
    return _theme.get(type_name, {})
