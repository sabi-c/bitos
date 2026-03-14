"""
BITOS Step Animator
All animations use discrete steps — no smooth interpolation.
Per spec: "ALL animations must use steps()"
"""
import time


class StepAnimator:
    """Discrete-step animation. Advances one step per interval."""

    def __init__(self, total_steps: int, duration_s: float, loop: bool = True):
        self.total_steps = total_steps
        self.duration_s = duration_s
        self.loop = loop
        self._step_duration = duration_s / total_steps
        self._current_step = 0
        self._elapsed = 0.0
        self._finished = False

    def update(self, dt: float):
        """Advance animation by dt seconds."""
        if self._finished:
            return

        self._elapsed += dt
        if self._elapsed >= self._step_duration:
            self._elapsed -= self._step_duration
            self._current_step += 1

            if self._current_step >= self.total_steps:
                if self.loop:
                    self._current_step = 0
                else:
                    self._current_step = self.total_steps - 1
                    self._finished = True

    @property
    def step(self) -> int:
        return self._current_step

    @property
    def finished(self) -> bool:
        return self._finished

    def reset(self):
        self._current_step = 0
        self._elapsed = 0.0
        self._finished = False


# ── Preset Animators ───────────────────────────────────────────

def blink_cursor(on_duration=0.5, off_duration=0.3):
    """Returns an animator that alternates 0/1 for cursor blink."""
    return StepAnimator(total_steps=2, duration_s=on_duration + off_duration, loop=True)


def typing_dots():
    """3-step dots animation: .  ..  ..."""
    return StepAnimator(total_steps=3, duration_s=1.2, loop=True)


def loading_bar():
    """8-step loading bar fill."""
    return StepAnimator(total_steps=8, duration_s=1.6, loop=True)


def orb_rotate():
    """8-step rotation for boot screen orbs."""
    return StepAnimator(total_steps=8, duration_s=2.0, loop=True)
