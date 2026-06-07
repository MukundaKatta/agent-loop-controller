# agent-loop-controller

Control agent loops with step limits, pause/resume, and abort signals.

`agent-loop-controller` is a tiny, dependency-free helper for the classic
"run an agent until it's done" loop. It gives you a single `LoopController`
object that:

- enforces a maximum number of steps,
- can be **paused** and **resumed** from another thread,
- can be **aborted** so the loop exits promptly,
- tracks basic stats (step count, elapsed time, current state).

It is thread-safe: control methods (`pause`, `resume`, `abort`, ...) may be
called from a different thread than the one driving the loop.

## Install

```
pip install agent-loop-controller
```

Requires Python 3.9+. No third-party dependencies.

## Usage

```python
from agent_loop_controller import LoopController, LoopAbortedError, LoopStepLimitError

ctrl = LoopController(max_steps=10)

while not ctrl.is_done():
    try:
        ctrl.step()           # counts a step, blocks if paused, raises if aborted
    except LoopStepLimitError:
        print("hit the step limit")
        break
    except LoopAbortedError:
        print("aborted")
        break

    # ... do one unit of agent work here ...

print(ctrl.stats.steps, "steps in", ctrl.stats.elapsed_s, "seconds")
```

### Controlling the loop from another thread

```python
import threading
from agent_loop_controller import LoopController, LoopAbortedError

ctrl = LoopController()

def run():
    try:
        while not ctrl.is_done():
            ctrl.step()       # blocks while paused, raises on abort
            # ... agent work ...
    except LoopAbortedError:
        pass

t = threading.Thread(target=run)
t.start()

ctrl.pause()      # the worker blocks on its next step()
ctrl.resume()     # the worker continues
ctrl.abort()      # the worker's next step() raises LoopAbortedError and exits
t.join()
```

## API

### `LoopController(max_steps=None, on_step=None)`

Create a controller.

- `max_steps` (`int | None`): maximum number of steps. When reached, the next
  `step()` raises `LoopStepLimitError` and the loop is marked completed. `None`
  means no limit. The step count is guaranteed never to exceed `max_steps`.
- `on_step` (`Callable[[LoopController], None] | None`): optional callback
  invoked after each successful step (not called for a rejected/limit step).

**Control methods**

- `start()` — mark the loop as running and record the start time. Optional;
  `step()` starts the loop automatically on first call.
- `step() -> int` — advance by one step. Blocks while paused. Raises
  `LoopAbortedError` if aborted, or `LoopStepLimitError` if the limit would be
  exceeded (the step is not counted in that case). Returns the new step count.
- `pause()` — pause the loop so the next `step()` blocks.
- `resume()` — resume a paused loop.
- `abort()` — abort the loop; the next `step()` raises `LoopAbortedError`. Also
  wakes a `step()` that is currently blocked on a pause.
- `complete()` — mark the loop as successfully completed.
- `reset()` — reset to the idle state so the controller can be reused.

**Query methods / properties**

- `is_done() -> bool` — `True` if aborted or completed.
- `is_running() -> bool`
- `is_paused() -> bool`
- `state -> LoopState` — current state.
- `steps -> int` — number of steps taken.
- `max_steps -> int | None`
- `stats -> LoopStats` — a snapshot of `steps`, `start_time`, `end_time`,
  `state`, and the `elapsed_s` property.

### `LoopState`

A string enum: `IDLE`, `RUNNING`, `PAUSED`, `ABORTED`, `COMPLETED`.

### `LoopStats`

Dataclass snapshot with fields `steps`, `start_time`, `end_time`, `state`, and
an `elapsed_s` property (seconds; frozen once the loop finishes).

### Exceptions

- `LoopAbortedError` — raised by `step()` after `abort()`.
- `LoopStepLimitError` — raised by `step()` when `max_steps` would be exceeded.

## Development

Run the test suite (standard library only, no extra dependencies):

```
python -m unittest discover -s tests
```

## License

MIT
