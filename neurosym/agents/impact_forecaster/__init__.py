# ImpactForecastUnavailable has no optional deps — always importable.
from .impact_exceptions import ImpactForecastUnavailable

# ImpactAgent, ImpactForecast, ImpactHypothesis, GitHubAdapter require the
# [forecaster] extra (pydantic, PyYAML). Wrap so `import neurosym` never
# fails just because the extra is absent.
try:
    from .agent import ImpactAgent
    from .github_adapter import GitHubAdapter
    from .impact_models import ImpactForecast, ImpactHypothesis
except ImportError:
    pass  # [forecaster] extra not installed — pydantic-dependent symbols unavailable

__all__ = [
    "ImpactForecastUnavailable",
    "ImpactAgent",
    "ImpactHypothesis",
    "ImpactForecast",
    "GitHubAdapter",
]
