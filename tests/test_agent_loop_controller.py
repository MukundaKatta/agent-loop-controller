"""Unit tests for agent_loop_controller.

These tests use only the Python standard library (``unittest``) so they run
with no third-party dependencies::

    python3 -m unittest discover -s tests
"""
import threading
import time
import unittest

from agent_loop_controller import (
    LoopController,
    LoopState,
    LoopStats,
    LoopAbortedError,
    LoopStepLimitError,
)


class StepTests(unittest.TestCase):
    def test_basic_step(self):
        ctrl = LoopController()
        self.assertEqual(ctrl.step(), 1)

    def test_steps_count(self):
        ctrl = LoopController()
        for _ in range(5):
            ctrl.step()
        self.assertEqual(ctrl.steps, 5)

    def test_step_returns_incrementing_values(self):
        ctrl = LoopController()
        self.assertEqual([ctrl.step() for _ in range(3)], [1, 2, 3])


class StepLimitTests(unittest.TestCase):
    def test_max_steps_raises(self):
        ctrl = LoopController(max_steps=3)
        ctrl.step()
        ctrl.step()
        ctrl.step()
        with self.assertRaises(LoopStepLimitError):
            ctrl.step()

    def test_max_steps_is_done_after_limit(self):
        ctrl = LoopController(max_steps=2)
        ctrl.step()
        ctrl.step()
        with self.assertRaises(LoopStepLimitError):
            ctrl.step()
        self.assertTrue(ctrl.is_done())
        self.assertEqual(ctrl.state, LoopState.COMPLETED)

    def test_steps_never_exceed_max_steps(self):
        # Regression test: a rejected step must not be counted, so the step
        # count must never grow past max_steps.
        ctrl = LoopController(max_steps=3)
        ctrl.step()
        ctrl.step()
        ctrl.step()
        with self.assertRaises(LoopStepLimitError):
            ctrl.step()
        self.assertEqual(ctrl.steps, 3)

    def test_max_steps_zero_rejects_first_step(self):
        ctrl = LoopController(max_steps=0)
        with self.assertRaises(LoopStepLimitError):
            ctrl.step()
        self.assertEqual(ctrl.steps, 0)
        self.assertTrue(ctrl.is_done())

    def test_max_steps_one(self):
        ctrl = LoopController(max_steps=1)
        self.assertEqual(ctrl.step(), 1)
        with self.assertRaises(LoopStepLimitError):
            ctrl.step()
        self.assertEqual(ctrl.steps, 1)

    def test_no_limit_when_max_steps_none(self):
        ctrl = LoopController(max_steps=None)
        for _ in range(50):
            ctrl.step()
        self.assertEqual(ctrl.steps, 50)
        self.assertFalse(ctrl.is_done())

    def test_max_steps_property(self):
        ctrl = LoopController(max_steps=5)
        self.assertEqual(ctrl.max_steps, 5)


class AbortTests(unittest.TestCase):
    def test_abort_raises(self):
        ctrl = LoopController()
        ctrl.abort()
        with self.assertRaises(LoopAbortedError):
            ctrl.step()

    def test_is_done_aborted(self):
        ctrl = LoopController()
        ctrl.abort()
        self.assertTrue(ctrl.is_done())

    def test_is_running_false_when_aborted(self):
        ctrl = LoopController()
        ctrl.abort()
        self.assertFalse(ctrl.is_running())

    def test_abort_after_steps(self):
        ctrl = LoopController()
        ctrl.step()
        ctrl.step()
        ctrl.abort()
        with self.assertRaises(LoopAbortedError):
            ctrl.step()
        self.assertEqual(ctrl.steps, 2)


class CompleteTests(unittest.TestCase):
    def test_complete(self):
        ctrl = LoopController()
        ctrl.complete()
        self.assertTrue(ctrl.is_done())
        self.assertEqual(ctrl.state, LoopState.COMPLETED)

    def test_step_after_complete_returns_count(self):
        ctrl = LoopController()
        ctrl.step()
        ctrl.complete()
        # step() on a completed loop returns the current count without raising
        self.assertEqual(ctrl.step(), 1)


class StateTests(unittest.TestCase):
    def test_state_idle_initially(self):
        ctrl = LoopController()
        self.assertEqual(ctrl.state, LoopState.IDLE)

    def test_state_running_after_step(self):
        ctrl = LoopController()
        ctrl.step()
        self.assertEqual(ctrl.state, LoopState.RUNNING)

    def test_start(self):
        ctrl = LoopController()
        ctrl.start()
        self.assertEqual(ctrl.state, LoopState.RUNNING)
        self.assertTrue(ctrl.is_running())

    def test_loop_state_is_str_enum(self):
        # LoopState members compare equal to their string values.
        self.assertEqual(LoopState.RUNNING, "running")


class PauseResumeTests(unittest.TestCase):
    def test_state_paused(self):
        ctrl = LoopController()
        ctrl.step()
        ctrl.pause()
        self.assertTrue(ctrl.is_paused())
        self.assertEqual(ctrl.state, LoopState.PAUSED)

    def test_resume_from_paused(self):
        ctrl = LoopController()
        ctrl.step()
        ctrl.pause()
        ctrl.resume()
        self.assertTrue(ctrl.is_running())

    def test_pause_blocks_step(self):
        ctrl = LoopController()
        ctrl.step()
        ctrl.pause()

        results = []

        def do_step():
            results.append(ctrl.step())

        t = threading.Thread(target=do_step, daemon=True)
        t.start()
        time.sleep(0.05)
        self.assertEqual(len(results), 0)  # still blocked
        ctrl.resume()
        t.join(timeout=1.0)
        self.assertEqual(len(results), 1)

    def test_abort_unblocks_paused_step(self):
        # A step blocked on pause should wake up and raise when aborted.
        ctrl = LoopController()
        ctrl.step()
        ctrl.pause()

        errors = []

        def do_step():
            try:
                ctrl.step()
            except LoopAbortedError as exc:
                errors.append(exc)

        t = threading.Thread(target=do_step, daemon=True)
        t.start()
        time.sleep(0.05)
        ctrl.abort()
        t.join(timeout=1.0)
        self.assertFalse(t.is_alive())
        self.assertEqual(len(errors), 1)


class ResetTests(unittest.TestCase):
    def test_reset(self):
        ctrl = LoopController()
        ctrl.step()
        ctrl.step()
        ctrl.abort()
        ctrl.reset()
        self.assertEqual(ctrl.state, LoopState.IDLE)
        self.assertEqual(ctrl.steps, 0)

    def test_reset_allows_reuse(self):
        ctrl = LoopController(max_steps=2)
        ctrl.step()
        ctrl.step()
        with self.assertRaises(LoopStepLimitError):
            ctrl.step()
        ctrl.reset()
        ctrl.step()
        self.assertEqual(ctrl.steps, 1)


class CallbackTests(unittest.TestCase):
    def test_on_step_callback(self):
        called = []
        ctrl = LoopController(on_step=lambda c: called.append(c.steps))
        ctrl.step()
        ctrl.step()
        ctrl.step()
        self.assertEqual(called, [1, 2, 3])

    def test_on_step_not_called_when_limit_hit(self):
        called = []
        ctrl = LoopController(max_steps=1, on_step=lambda c: called.append(c.steps))
        ctrl.step()
        with self.assertRaises(LoopStepLimitError):
            ctrl.step()
        self.assertEqual(called, [1])


class StatsTests(unittest.TestCase):
    def test_stats_elapsed(self):
        ctrl = LoopController()
        ctrl.step()
        self.assertGreaterEqual(ctrl.stats.elapsed_s, 0)

    def test_stats_steps(self):
        ctrl = LoopController()
        ctrl.step()
        ctrl.step()
        self.assertEqual(ctrl.stats.steps, 2)

    def test_stats_is_snapshot(self):
        # stats returns a copy, so it should not change as the loop advances.
        ctrl = LoopController()
        ctrl.step()
        snapshot = ctrl.stats
        ctrl.step()
        self.assertEqual(snapshot.steps, 1)
        self.assertEqual(ctrl.stats.steps, 2)

    def test_elapsed_zero_before_start(self):
        stats = LoopStats()
        self.assertEqual(stats.elapsed_s, 0.0)

    def test_elapsed_uses_end_time_when_finished(self):
        ctrl = LoopController()
        ctrl.step()
        ctrl.complete()
        first = ctrl.stats.elapsed_s
        time.sleep(0.02)
        second = ctrl.stats.elapsed_s
        # Once completed, elapsed is frozen at end_time and stops growing.
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
