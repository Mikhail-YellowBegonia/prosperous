import time
import threading
from __init__ import RenderEngine, ImageRenderer, BinmapImageRenderer, FontManager, BigTextRenderer, InputHandler, cleanup
from components import InputBox

from styles import Style

from components import InputBox, Panel
from interaction import FocusManager

def logic_loop(engine):
    # 阶段 3 测试：焦点系统
    focus_manager = FocusManager()
    
    # 创建两个输入框
    input1 = InputBox(pos=(4, 5), width=30, label="BOX ONE")
    input2 = InputBox(pos=(4, 40), width=30, label="BOX TWO")
    
    focus_manager.add_component(input1)
    focus_manager.add_component(input2)
    
    # 根面板容器
    root_panel = Panel(pos=(2, 2), width=75, height=10, title="FOCUS SYSTEM TEST")
    root_panel.add_child(input1)
    root_panel.add_child(input2)
    
    frame_count = 0
    while engine.is_running:
        engine.listen_size()

        # 核心交互分发：全部交给 focus_manager
        with engine.lock:
            while engine.input_events:
                key = engine.input_events.pop(0)
                focus_manager.handle_input(key)

        with engine.lock:
            engine.clear_prepare()
            engine.clear_spaces()

            engine.push(1, 1, f"Frame: {frame_count}", Style(fg=46))
            engine.push(12, 2, "Use LEFT/RIGHT to switch focus, type to see results.", Style(fg=244))
            
            root_panel.draw(engine)

            engine.flush_spaces()

        frame_count += 1
        time.sleep(0.01)

def render_loop(engine, fps):
# ... (保持不变)

    interval = 1.0 / fps
    while engine.is_running:
        start = time.perf_counter()
        engine.swap_buffers()
        engine.render()
        elapsed = time.perf_counter() - start
        time.sleep(max(0, interval - elapsed))

if __name__ == "__main__":
    engine = RenderEngine()
    input_handler = InputHandler(engine)
    
    try:
        t1 = threading.Thread(target=logic_loop, args=(engine,), daemon=True)
        t2 = threading.Thread(target=render_loop, args=(engine, 30), daemon=True)
        t3 = threading.Thread(target=input_handler.listen, daemon=True)
        
        t1.start()
        t2.start()
        t3.start()

        # 主线程阻塞，直到 engine 停止
        while engine.is_running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        engine.is_running = False
    finally:
        input_handler.stop()
        cleanup(engine.cli_height)
        print("\n[Prosperous] Exited safely.")
