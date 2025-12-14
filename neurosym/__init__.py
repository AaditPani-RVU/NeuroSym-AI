# neurosym/__init__.py
try:
    from .version import __version__
except Exception:  # fallback for editable/dev envs
    __version__ = "0.0.0+dev"

from .engine.guard import Guard, GuardResult
from .rules.base import Rule, Violation

__all__ = ["__version__", "Guard", "GuardResult", "Rule", "Violation"]
