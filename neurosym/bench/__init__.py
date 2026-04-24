"""neurosym.bench — Benchmark harness for measuring guardrail effectiveness.

Usage::

    from neurosym.bench import BenchmarkRunner, BenchmarkCase
    from neurosym.rules.adversarial import PromptInjectionRule

    guard = Guard(rules=[PromptInjectionRule()], deny_above="high")
    runner = BenchmarkRunner(guard)
    results = runner.run(BenchmarkCase.load_builtin("prompt_injection"))
    print(results.report())

CLI::

    neurosym bench --corpus prompt_injection --policy my_policy.yaml
"""

from .harness import BenchmarkCase, BenchmarkResult, BenchmarkRunner, CaseResult

__all__ = ["BenchmarkCase", "BenchmarkResult", "BenchmarkRunner", "CaseResult"]
