import time
import threading
import contextlib
from engine import RenderEngine
from input_handler import InputHandler
from utils import cleanup


class Live:
    def __init__(self, fps: int = 30, logic_fps: int = None):
        self.fps = fps
        self._logic_interval = (1.0 / logic_fps) if logic_fps else 0
        self.engine: RenderEngine = None
        self._input_handler: InputHandler = None
        self._render_thread: threading.Thread = None
        self._input_thread: threading.Thread = None
        self._last_poll: float = 0.0

    def __enter__(self):
        self.engine = RenderEngine()
        self._input_handler = InputHandler(self.engine)

        self._render_thread = threading.Thread(target=self._render_loop, daemon=True)
        self._input_thread = threading.Thread(target=self._input_handler.listen, daemon=True)

        self._render_thread.start()
        self._input_thread.start()
        return self

    def __exit__(self, *_):
        self.engine.is_running = False
        self._input_handler.stop()
        cleanup(self.engine.cli_height)

    @property
    def running(self) -> bool:
        return self.engine.is_running

    def poll(self) -> list[str]:
        """限速至 logic_fps（未设置则不限速），检测终端尺寸，返回本帧按键事件并清空队列。"""
        if self._logic_interval > 0:
            elapsed = time.perf_counter() - self._last_poll
            if elapsed < self._logic_interval:
                time.sleep(self._logic_interval - elapsed)
        self._last_poll = time.perf_counter()

        self.engine.listen_size()
        with self.engine.lock:
            events = list(self.engine.input_events)
            self.engine.input_events.clear()
        return events

    @contextlib.contextmanager
    def frame(self):
        """帧绘制上下文：自动清空准备缓冲区，退出时合并合成层。持锁期间渲染线程等待交换。"""
        with self.engine.lock:
            self.engine.clear_prepare()
            self.engine.clear_spaces()
            try:
                yield self.engine
            finally:
                self.engine.flush_spaces()

    def _render_loop(self):
        interval = 1.0 / self.fps
        while self.engine.is_running:
            start = time.perf_counter()
            self.engine.swap_buffers()
            self.engine.render()
            elapsed = time.perf_counter() - start
            time.sleep(max(0, interval - elapsed))
