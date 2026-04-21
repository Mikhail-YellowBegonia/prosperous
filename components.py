class InputBox:
    def __init__(self, width=40, label="INPUT", border_color=7, text_color=15):
        self.width = width
        self.label = label
        self.text = ""
        self.border_color = border_color
        self.text_color = text_color
        self.cursor_visible = True
        self._last_blink = 0

    def handle_input(self, key):
        if not key: return
        
        if key == "BACKSPACE":
            self.text = self.text[:-1]
        elif key == "SPACE":
            self.text += " "
        elif key == "ENTER":
            self.text = "" # 按回车清空，作为测试反馈
        elif len(key) == 1: 
            if len(self.text) < self.width - 4:
                self.text += key

    def draw(self, start_y, start_x, engine):
        # 简单的闪烁光标逻辑
        import time
        if time.time() - self._last_blink > 0.5:
            self.cursor_visible = not self.cursor_visible
            self._last_blink = time.time()
        
        cursor = " " if not self.cursor_visible else "█"
        
        w = self.width
        label_txt = f" {self.label} "
        top = "┌" + label_txt.center(w - 2, "─") + "┐"
        
        # 处理显示内容
        display_text = self.text + cursor
        content = display_text.ljust(w - 2)[:w - 2]
        mid = "│" + content + "│"
        
        bot = "└" + "─" * (w - 2) + "┘"

        engine.push(start_y, start_x, top, self.border_color, 0, 0)
        engine.push(start_y + 1, start_x, mid, self.text_color, 0, 0)
        engine.push(start_y + 2, start_x, bot, self.border_color, 0, 0)
