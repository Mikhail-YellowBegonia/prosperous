import time
import threading
from __init__ import RenderEngine, ImageRenderer, BinmapImageRenderer, FontManager, BigTextRenderer, InputHandler, cleanup
from components import InputBox

def logic_loop(engine):
    # 初始化组件
    input_box = InputBox(width=40, label="TEST INPUT")

    frame_count = 0
    while engine.is_running:
        engine.listen_size()

        # 1. 处理输入逻辑 (从队列中取出并分发)
        with engine.lock:
            while engine.input_events:
                key = engine.input_events.pop(0)
                input_box.handle_input(key)

        # 2. 准备渲染内容
        with engine.lock:
            engine.clear_prepare()
            engine.clear_spaces()

            # 状态栏
            engine.push(1, 1, f"Frame: {frame_count}", 46, 0, 0)
            engine.push(2, 1, f"Status: Input Loop Ready", 208, 0, 0)

            # 渲染输入框组件
            input_box.draw(5, 10, engine)

            engine.push(9, 10, "Try Typing, Backspace, Enter.", 244, 0, 0)

            # 合并图像空间并完成
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
