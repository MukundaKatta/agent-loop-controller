import threading
import time
import pytest
from agent_loop_controller import (
    LoopController, LoopState, LoopStats,
    LoopAbortedError, LoopStepLimitError,
)


def test_basic_step():
    ctrl = LoopController()
    n = ctrl.step()
    assert n == 1


def test_steps_count():
    ctrl = LoopController()
    for _ in range(5):
        ctrl.step()
    assert ctrl.steps == 5


def test_max_steps_raises():
    ctrl = LoopController(max_steps=3)
    ctrl.step(); ctrl.step(); ctrl.step()
    with pytest.raises(LoopStepLimitError):
        ctrl.step()


def test_max_steps_is_done_after_limit():
    ctrl = LoopController(max_steps=2)
    ctrl.step(); ctrl.step()
    with pytest.raises(LoopStepLimitError):
        ctrl.step()
    assert ctrl.is_done()


def test_abort_raises():
    ctrl = LoopController()
    ctrl.abort()
    with pytest.raises(LoopAbortedError):
        ctrl.step()


def test_is_done_aborted():
    ctrl = LoopController()
    ctrl.abort()
    assert ctrl.is_done()


def test_complete():
    ctrl = LoopController()
    ctrl.complete()
    assert ctrl.is_done()
    assert ctrl.state == LoopState.COMPLETED


def test_state_idle_initially():
    ctrl = LoopController()
    assert ctrl.state == LoopState.IDLE


def test_state_running_after_step():
    ctrl = LoopController()
    ctrl.step()
    assert ctrl.state == LoopState.RUNNING


def test_state_paused():
    ctrl = LoopController()
    ctrl.step()
    ctrl.pause()
    assert ctrl.is_paused()
    assert ctrl.state == LoopState.PAUSED


def test_resume_from_paused():
    ctrl = LoopController()
    ctrl.step()
    ctrl.pause()
    ctrl.resume()
    assert ctrl.is_running()


def test_pause_blocks_step():
    ctrl = LoopController()
    ctrl.step()
    ctrl.pause()

    results = []

    def do_step():
        results.append(ctrl.step())

    t = threading.Thread(target=do_step, daemon=True)
    t.start()
    time.sleep(0.05)
    assert len(results) == 0  # still blocked
    ctrl.resume()
    t.join(timeout=1.0)
    assert len(results) == 1


def test_reset():
    ctrl = LoopController()
    ctrl.step(); ctrl.step()
    ctrl.abort()
    ctrl.reset()
    assert ctrl.state == LoopState.IDLE
    assert ctrl.steps == 0


def test_reset_allows_reuse():
    ctrl = LoopController(max_steps=2)
    ctrl.step(); ctrl.step()
    with pytest.raises(LoopStepLimitError):
        ctrl.step()
    ctrl.reset()
    ctrl.step()
    assert ctrl.steps == 1


def test_on_step_callback():
    called = []
    ctrl = LoopController(on_step=lambda c: called.append(c.steps))
    ctrl.step(); ctrl.step(); ctrl.step()
    assert called == [1, 2, 3]


def test_stats_elapsed():
    ctrl = LoopController()
    ctrl.step()
    s = ctrl.stats
    assert s.elapsed_s >= 0


def test_stats_steps():
    ctrl = LoopController()
    ctrl.step(); ctrl.step()
    assert ctrl.stats.steps == 2


def test_max_steps_property():
    ctrl = LoopController(max_steps=5)
    assert ctrl.max_steps == 5


def test_is_running_false_when_aborted():
    ctrl = LoopController()
    ctrl.abort()
    assert not ctrl.is_running()


def test_start():
    ctrl = LoopController()
    ctrl.start()
    assert ctrl.state == LoopState.RUNNING
