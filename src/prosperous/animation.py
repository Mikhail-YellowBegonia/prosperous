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
    def int_value(self) -> int:
        """当前插值结果，四舍五入为整数。适合驱动离散坐标（如 scroll_y、pos）。"""
        return round(self.value)

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


# ── Kinetic (Physical) ────────────────────────────────────────────────────────


class Kinetic:
    """动力学动画系统（物理模拟）。

    与 Tween 的“时间驱动”不同，Kinetic 是“状态驱动”的。它模拟了一个受弹簧力和阻力影响的物理实体。
    非常适合处理中途可能改变目标的连续动画（如焦点跟随、弹性伸缩）。

    设想方案：
        - 采用临界阻尼弹簧模型 (Critically Damped Spring)。
        - 核心参数：stiffness (劲度/弹性), damping (阻尼/稳定性)。

    参数：
        initial_value: 起始数值
        stiffness:     弹簧强度 (默认 120)，越大“拉力”越强。
        damping:       阻尼系数 (默认 16)，越大越不容易抖动，越接近 1.0 越接近临界阻尼。
    """

    def __init__(self, initial_value: float, stiffness: float = 120.0, damping: float = 16.0):
        self._current_value = initial_value
        self._target_value = initial_value
        self._velocity = 0.0
        self.stiffness = stiffness
        self.damping = damping

    @property
    def value(self) -> float:
        """当前的物理模拟值。"""
        return self._current_value

    @property
    def int_value(self) -> int:
        """当前模拟值，四舍五入为整数。需先调用 update(dt)。适合驱动离散坐标。"""
        return round(self._current_value)

    @property
    def velocity(self) -> float:
        """当前的瞬间速度。"""
        return self._velocity

    def set_target(self, target: float):
        """更新目标值。物体将根据当前速度平滑地滑向新目标。"""
        self._target_value = target

    def update(self, dt: float):
        """执行一个物理步进。基于临界阻尼弹簧算法。"""
        if dt <= 0:
            return

        # 弹簧物理公式：
        # F_spring = stiffness * (target - current)
        # F_damper = damping * velocity
        # a = F_spring - F_damper (假设质量 m=1)

        displacement = self._current_value - self._target_value
        spring_force = -self.stiffness * displacement
        damper_force = -self.damping * self._velocity

        acceleration = spring_force + damper_force

        # 简单的 Euler 积分（对 UI 动画足够稳定且计算开销极低）
        self._velocity += acceleration * dt
        self._current_value += self._velocity * dt

    @property
    def done(self) -> bool:
        """当位移和速度都极小时视为完成。"""
        return abs(self._current_value - self._target_value) < 0.001 and abs(self._velocity) < 0.001
