"""Job-local hook for the `sglang-lpminf` cell: SGLang 0.5.22 LPM without its 128-request FCFS fallback.

What it changes. sglang/srt/managers/schedule_policy.py (0.5.22, md5 b8ec334ac1ed028e3c176022ea1f9143) defines the
module constant WAITING_QUEUE_PREFIX_MATCH_MAX = 128 (line 133). SchedulePolicy._determine_active_policy (line 307)
returns FCFS instead of LPM/HRRN whenever len(waiting_queue) > that constant, and _touch_waiting_prefixes (line 297)
uses it as the FCFS refresh window (not reached by an LPM run once LPM never falls back). Both read it as a module global
at call time; nothing else in the package names it (grep over the installed package, 2026-10-30). If the environment
variable PM_WAITING_QUEUE_PREFIX_MATCH_MAX is set, this hook replaces the constant with its value right after the
module body runs, before any other code can use it. Without the variable the hook does nothing at all.

How it reaches the scheduler. slurm/engine_sglang.sh puts this directory on PYTHONPATH (and sets the variable) ONLY on the
`python -m sglang.launch_server` command line when LPM_INF=1; the shared env is not modified. Every interpreter runs
`site`, which imports `sitecustomize` from sys.path, so the hook also runs in SGLang's scheduler, a multiprocessing
"spawn" child (srt/entrypoints/engine.py:1964 mp.set_start_method("spawn", force=True)) that inherits the environment.
The env has no sitecustomize of its own (`import sitecustomize` -> ModuleNotFoundError, 2026-10-30), so none is shadowed.

Safety. It refuses (the import of schedule_policy raises, so the server dies before /health answers) if the stock value
is not exactly 128 or the variable is not an integer above 128 (a sitecustomize that raises is only reported by site.py,
so the refusal is deferred to the import of the target). Each process that imports the module writes one marker
line to stderr (server.log):
  [pm-lpminf-hook] pid=<pid> ppid=<ppid> sglang.srt.managers.schedule_policy.WAITING_QUEUE_PREFIX_MATCH_MAX 128 -> <new> file=<path>
engine_post_health_check requires such a line from a pid other than the launch_server pid (i.e. a spawned child).
"""
import os
import sys

_TARGET = "sglang.srt.managers.schedule_policy"
_NAME = "WAITING_QUEUE_PREFIX_MATCH_MAX"
_STOCK = 128
_VAL = os.environ.get("PM_WAITING_QUEUE_PREFIX_MATCH_MAX")

if _VAL:
    import importlib.abc
    import importlib.machinery

    # site.py catches (and only prints) an exception raised by sitecustomize itself, so a bad value must not raise here:
    # it is recorded and the import of the target module fails instead (the scheduler then dies before /health).
    _ERR = None
    try:
        _NEW = int(_VAL)
    except ValueError:
        _NEW, _ERR = None, f"PM_WAITING_QUEUE_PREFIX_MATCH_MAX={_VAL!r} is not an integer"
    if _ERR is None and _NEW <= _STOCK:
        _ERR = f"PM_WAITING_QUEUE_PREFIX_MATCH_MAX={_NEW} must exceed the stock {_STOCK}"

    class _PmLpmInfFinder(importlib.abc.MetaPathFinder):
        """Finds the target with the normal path finder and wraps that spec's loader.exec_module."""

        def find_spec(self, fullname, path, target=None):
            if fullname != _TARGET:
                return None
            if _ERR is not None:
                raise RuntimeError(f"[pm-lpminf-hook] {_ERR}; refusing to import {_TARGET}")
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            if spec is None or spec.loader is None:
                return spec
            orig_exec = spec.loader.exec_module      # PathFinder returns a fresh loader per call: the wrap is local

            def exec_module(module, _orig=orig_exec):
                _orig(module)
                old = getattr(module, _NAME, None)
                if type(old) is not int or old != _STOCK:
                    raise RuntimeError(f"[pm-lpminf-hook] expected stock {_NAME}={_STOCK} in "
                                       f"{getattr(module, '__file__', '?')}, found {old!r}; refusing to patch")
                setattr(module, _NAME, _NEW)
                sys.stderr.write(f"\n[pm-lpminf-hook] pid={os.getpid()} ppid={os.getppid()} {_TARGET}.{_NAME} "
                                 f"{_STOCK} -> {_NEW} file={getattr(module, '__file__', '?')}\n")
                sys.stderr.flush()

            spec.loader.exec_module = exec_module
            return spec

    sys.meta_path.insert(0, _PmLpmInfFinder())
