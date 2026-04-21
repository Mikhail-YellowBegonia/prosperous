import time
import threading
from __init__ import RenderEngine, ImageRenderer, BinmapImageRenderer, FontManager, BigTextRenderer, cleanup

def logic_loop(engine):
    # Pre-initialize resources
    # Ensure these paths match your actual files
    try:
        image = ImageRenderer("img/sanae_RGBA.png", 59, enable_256_color_reduction=True)
        logo = BinmapImageRenderer("img/Aliya.png", 120, fg=(100, 200, 250))
    except Exception as e:
        print(f"Error loading images: {e}")
        return

    fm = FontManager("ToshibaT300.ttf", 16, vertical_compress=True) 
    big_text = BigTextRenderer(fm)
    
    frame_count = 0
    while engine.is_running:
        engine.listen_size()
        
        with engine.lock:
            engine.clear_prepare()
            engine.clear_spaces()
            
            # Draw standard text via engine.push
            engine.push(1, 1, f"Frame: {frame_count}", 46, 0, 0)
            engine.push(2, 1, "Prosperous", 7, 0, 0)

            # Insert your code here

            # Composite everything
            engine.flush_spaces()
        
        frame_count += 1
        time.sleep(0.01)

def render_loop(engine, fps):
    interval = 1.0 / fps
    while engine.is_running:
        start = time.perf_counter()
        
        engine.swap_buffers()
        engine.render()
        
        elapsed = time.perf_counter() - start
        time.sleep(max(0, interval - elapsed))

if __name__ == "__main__":
    engine = RenderEngine()
    
    try:
        t1 = threading.Thread(target=logic_loop, args=(engine,), daemon=True)
        t2 = threading.Thread(target=render_loop, args=(engine, 16), daemon=True)
        t1.start()
        t2.start()

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        engine.is_running = False
    finally:
        cleanup(engine.cli_height)
        print("\n[Prosperous] Exited safely.")
