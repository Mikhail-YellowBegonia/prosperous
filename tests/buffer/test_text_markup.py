import pytest
from components import Text
from styles import Style, DEFAULT_STYLE
from theme import set_theme, DEFAULT_THEME

def cell_char(engine, row, col):
    return engine.screen_logic[row][col][0]

def cell_style(engine, row, col):
    return engine.screen_logic[row][col][1]

class TestRichTextBuffer:
    def test_multiline_text_height(self, engine):
        t = Text(text="Line 1\nLine 2\nLine 3")
        assert t.get_height() == 3

    def test_basic_markup_rendering(self, engine):
        # <red> 对应 Style(fg=1)
        t = Text(text="Normal <red>Red</> Normal")
        t.draw(engine)
        
        # "Normal " (7 chars)
        assert "".join(cell_char(engine, 0, i) for i in range(7)) == "Normal "
        assert cell_style(engine, 0, 0).fg == DEFAULT_STYLE.fg
        
        # "Red" (3 chars)
        assert "".join(cell_char(engine, 0, i) for i in range(7, 10)) == "Red"
        assert cell_style(engine, 0, 7).fg == 1
        
        # " Normal"
        assert cell_char(engine, 0, 10) == " "
        assert cell_style(engine, 0, 10).fg == DEFAULT_STYLE.fg

    def test_theme_tag_rendering(self, engine):
        # 预设一个主题标签
        set_theme({
            **DEFAULT_THEME,
            "#test": {"style": Style(fg=200, bold=True)}
        })
        
        t = Text(text="<#test>Theme</>")
        t.draw(engine)
        
        assert "".join(cell_char(engine, 0, i) for i in range(5)) == "Theme"
        style = cell_style(engine, 0, 0)
        assert style.fg == 200
        assert style.bold is True

    def test_nested_markup(self, engine):
        t = Text(text="<red>R <bold>RB</> R</>")
        t.draw(engine)
        
        # "R "
        assert cell_style(engine, 0, 0).fg == 1
        assert cell_style(engine, 0, 0).bold is False
        
        # "RB"
        assert cell_style(engine, 0, 2).fg == 1
        assert cell_style(engine, 0, 2).bold is True
        
        # " R"
        assert cell_style(engine, 0, 4).fg == 1
        assert cell_style(engine, 0, 4).bold is False

    def test_multiline_alignment(self, engine):
        # width=10, "A" (len 1) center -> offset 4
        # "BB" (len 2) right -> offset 8
        t = Text(text="A\nBB", width=10, align="left") # 默认 left 测试基础
        t.draw(engine)
        assert cell_char(engine, 0, 0) == "A"
        assert cell_char(engine, 1, 0) == "B"
        
        t.align = "right"
        engine.clear_prepare()
        t.draw(engine)
        assert cell_char(engine, 0, 9) == "A"
        assert cell_char(engine, 1, 8) == "B"
        assert cell_char(engine, 1, 9) == "B"
