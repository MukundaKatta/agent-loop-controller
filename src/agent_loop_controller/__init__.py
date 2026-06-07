"""
agent-loop-controller: Control agent loops with pause, resume, step-limit, and abort.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class LoopState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ABORTED = "aborted"
    COMPLETED = "completed"


class LoopAbortedError(RuntimeError):
    """Raised when a loop is aborted via abort()."""


class LoopStepLimitError(RuntimeError):
    """Raised when max_steps is exceeded."""


@dataclass
class LoopStats:
    steps: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    state: LoopState = LoopState.IDLE

    @property
    def elapsed_s(self) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.monotonic()
        return end - self.start_time


class LoopController:
    """
    Control an agent loop: enforce step limits, support pause/resume, and abort.

    Usage::

        ctrl = LoopController(max_steps=10)

        while not ctrl.is_done():
            ctrl.step()       # increments step count, checks limits, blocks if paused
            # ... do agent work ...

        ctrl.stats.steps   # how many steps ran
    """

    def __init__(
        self,
        max_steps: Optional[int] = None,
        on_step: Optional[Callable[["LoopController"], None]] = None,
    ) -> None:
        self._max_steps = max_steps
        self._on_step = on_step
        self._lock = threading.Lock()
        self._pause_event = threading.Event()
        self._pause_event.set()  # not paused initially
        self._stats = LoopStats()

    # -- control API ---------------------------------------------------------

    def start(self) -> None:
        """Mark the loop as started."""
        with self._lock:
            self._stats.state = LoopState.RUNNING
            self._stats.start_time = time.monotonic()

    def step(self) -> int:
        """
        Advance by one step.

        - Blocks if the loop is paused.
        - Raises LoopAbortedError if aborted.
        - Raises LoopStepLimitError if max_steps exceeded.
        Returns the current step count.
        """
        # Block while paused
        self._pause_event.wait()

        with self._lock:
            state = self._stats.state
            if state == LoopState.ABORTED:
                raise LoopAbortedError("Loop was aborted")
            if state == LoopState.COMPLETED:
                return self._stats.steps
            if state == LoopState.IDLE:
                self._stats.state = LoopState.RUNNING
                self._stats.start_time = time.monotonic()

            # If taking this step would exceed the limit, do not count it:
            # the step never runs, it raises instead.
            if self._max_steps is not None and self._stats.steps >= self._max_steps:
                self._stats.state = LoopState.COMPLETED
                self._stats.end_time = time.monotonic()
                raise LoopStepLimitError(f"Max steps ({self._max_steps}) exceeded")

            self._stats.steps += 1
            steps = self._stats.steps

        if self._on_step:
            self._on_step(self)

        return steps

    def pause(self) -> None:
        """Pause the loop (next step() call will block)."""
        with self._lock:
            if self._stats.state == LoopState.RUNNING:
                self._stats.state = LoopState.PAUSED
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume a paused loop."""
        with self._lock:
            if self._stats.state == LoopState.PAUSED:
                self._stats.state = LoopState.RUNNING
        self._pause_event.set()

    def abort(self) -> None:
        """Abort the loop; next step() raises LoopAbortedError."""
        self._finish(LoopState.ABORTED)
        self._pause_event.set()  # unblock any waiting step()

    def complete(self) -> None:
        """Mark the loop as successfully completed."""
        self._finish(LoopState.COMPLETED)

    def reset(self) -> None:
        """Reset the controller to idle for reuse."""
        with self._lock:
            self._stats = LoopStats()
        self._pause_event.set()

    def _finish(self, state: LoopState) -> None:
        with self._lock:
            self._stats.state = state
            self._stats.end_time = time.monotonic()

    # -- query API -----------------------------------------------------------

    def is_done(self) -> bool:
        with self._lock:
            return self._stats.state in (LoopState.ABORTED, LoopState.COMPLETED)

    def is_running(self) -> bool:
        with self._lock:
            return self._stats.state == LoopState.RUNNING

    def is_paused(self) -> bool:
        with self._lock:
            return self._stats.state == LoopState.PAUSED

    @property
    def state(self) -> LoopState:
        with self._lock:
            return self._stats.state

    @property
    def stats(self) -> LoopStats:
        with self._lock:
            return LoopStats(
                steps=self._stats.steps,
                start_time=self._stats.start_time,
                end_time=self._stats.end_time,
                state=self._stats.state,
            )

    @property
    def steps(self) -> int:
        with self._lock:
            return self._stats.steps

    @property
    def max_steps(self) -> Optional[int]:
        return self._max_steps


__all__ = [
    "LoopController",
    "LoopState",
    "LoopStats",
    "LoopAbortedError",
    "LoopStepLimitError",
]
