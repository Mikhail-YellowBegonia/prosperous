import time
import threading
import contextlib
from engine import RenderEngine
from input_handler import InputHandler
from utils import cleanup


class Live:
    """Prosperous 应用入口，以上下文管理器方式使用。

    内部管理渲染线程、输入线程，并负责退出时恢复终端状态。

    参数：
        fps:       渲染帧率（screen_buffer → 终端输出的频率），默认 30。
        logic_fps: 逻辑帧率（poll() 的最高调用频率）。None 表示不限速，
                   由用户自行控制循环节奏。建议设为 fps 的 1～2 倍。

    典型用法：
        with Live(fps=30, logic_fps=60) as live:
            live.add(my_panel)
            while live.running:
                for key in live.poll():
                    if key == "ESC": live.engine.is_running = False
                    focus.handle_input(key)
                with live.frame():
                    pass  # 场景组件已由 frame() 自动绘制
    """

    def __init__(self, fps: int = 30, logic_fps: int = None):
        self.fps = fps
        self._logic_interval = (1.0 / logic_fps) if logic_fps else 0
        self.engine: RenderEngine = None
        self._input_handler: InputHandler = None
        self._render_thread: threading.Thread = None
        self._input_thread: threading.Thread = None
        self._last_poll: float = 0.0
        self._scene: list = []

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

    def stop(self):
        """退出主循环，触发 __exit__ 清理流程。"""
        self.engine.is_running = False

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

    def add(self, component) -> None:
        """注册顶层组件到场景，frame() 时自动绘制。"""
        if component not in self._scene:
            self._scene.append(component)

    def remove(self, component) -> None:
        """从场景中移除组件，下一帧起不再绘制。组件本身不会被销毁，可重新 add()。"""
        try:
            self._scene.remove(component)
        except ValueError:
            pass

    @contextlib.contextmanager
    def frame(self):
        """帧绘制上下文：清空缓冲区 → 绘制场景组件 → yield 供手动补充绘制 → 合并合成层。"""
        with self.engine.lock:
            self.engine.clear_prepare()
            self.engine.clear_spaces()
            try:
                for component in self._scene:
                    if component.visible:
                        component.draw(self.engine)
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
