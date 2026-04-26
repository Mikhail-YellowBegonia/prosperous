import time


# ── Easing functions ──────────────────────────────────────────────────────────
# 所有 easing 函数签名：(t: float) -> float，其中 t ∈ [0, 1]
# 可传入任意符合此签名的自定义函数。


def linear(t: float) -> float:
    return t


def ease_out(t: float) -> float:
    """二次缓出（默认）：快进慢出，适合大多数 UI 位移动画。"""
    return 1 - (1 - t) ** 2


def ease_in(t: float) -> float:
    """二次缓入：慢进快出。"""
    return t * t


def ease_in_out(t: float) -> float:
    """三次 S 曲线：两端慢、中间快，适合焦点切换等需要对称感的动画。"""
    return t * t * (3 - 2 * t)


# ── Tween ─────────────────────────────────────────────────────────────────────


class Tween:
    """固定时长的数值插值动画。

    接管一个浮点属性从 start 到 end 的过渡，由 easing 函数定义曲线形状。
    Tween 本身无副作用，每帧通过 .value 属性查询当前插值结果。

    参数：
        start:    起始值
        end:      目标值
        duration: 动画时长（秒）
        easing:   (t: float) -> float，t ∈ [0, 1]，默认 ease_out（二次缓出）

    示例：
        anim = Tween(start=0, end=10, duration=0.4)

        # 主循环每帧查询
        card.pos = (round(anim.value), x)
        if anim.done:
            card.pos = (10, x)   # snap 到终值
    """

    def __init__(
        self,
        start: float,
        end: float,
        duration: float,
        easing=None,
    ):
        self.start = start
        self.end = end
        self.duration = duration
        self._easing = easing if easing is not None else ease_out
        self._t0 = time.perf_counter()

    # ── 查询 ──────────────────────────────────────────────────────────────────

    @property
    def progress(self) -> float:
        """归一化进度，范围 [0, 1]。到达 1.0 后保持不变。"""
        return min(1.0, (time.perf_counter() - self._t0) / self.duration)

    @property
    def value(self) -> float:
        """当前插值结果，到达终点后稳定返回 end。"""
        return self.start + (self.end - self.start) * self._easing(self.progress)

    @property
    def done(self) -> bool:
        """动画是否已完成（elapsed >= duration）。"""
        return (time.perf_counter() - self._t0) >= self.duration

    # ── 控制 ──────────────────────────────────────────────────────────────────

    def restart(self, start: float = None, end: float = None, duration: float = None):
        """从当前时间重新开始动画，可选更新 start / end / duration。"""
        if start is not None:
            self.start = start
        if end is not None:
            self.end = end
        if duration is not None:
            self.duration = duration
        self._t0 = time.perf_counter()
