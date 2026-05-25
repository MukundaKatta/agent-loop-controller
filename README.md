# agent-loop-controller

Control agent loops with step limits, pause/resume, and abort signals.

## Install

```
pip install agent-loop-controller
```

## Usage

```python
from agent_loop_controller import LoopController, LoopAbortedError, LoopStepLimitError

ctrl = LoopController(max_steps=10)
ctrl.start()

while not ctrl.is_done():
    try:
        ctrl.step()
    except LoopStepLimitError:
        break
    # ... agent work ...

# From another thread:
ctrl.pause()    # blocks next step()
ctrl.resume()   # unblocks
ctrl.abort()    # next step() raises LoopAbortedError

print(ctrl.stats.steps, ctrl.stats.elapsed_s)
```
