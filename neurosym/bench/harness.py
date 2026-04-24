"""Benchmark harness for measuring guardrail block rate, FPR, and latency."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from neurosym.engine.guard import Guard


@dataclass
class BenchmarkCase:
    """A single benchmark input with its expected outcome."""

    text: str
    should_block: bool
    label: str = ""
    category: str = ""

    @staticmethod
    def load_builtin(name: str) -> list[BenchmarkCase]:
        """Load a built-in benchmark corpus by name.

        Available corpora:
          - "prompt_injection": 100+ adversarial voice/text prompts
          - "safe_commands": benign voice commands (for FPR measurement)
        """
        import importlib

        mod = importlib.import_module(f"neurosym.bench.corpus.{name}")
        return mod.CASES  # type: ignore[no-any-return]


@dataclass
class CaseResult:
    """Result for a single benchmark case."""

    case: BenchmarkCase
    blocked: bool
    latency_ms: float
    violations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def correct(self) -> bool:
        return self.blocked == self.case.should_block

    @property
    def is_false_positive(self) -> bool:
        return self.blocked and not self.case.should_block

    @property
    def is_false_negative(self) -> bool:
        return not self.blocked and self.case.should_block


@dataclass
class BenchmarkResult:
    """Aggregated results from a benchmark run."""

    case_results: list[CaseResult]
    guard_config: str = ""

    @property
    def total(self) -> int:
        return len(self.case_results)

    @property
    def attack_cases(self) -> list[CaseResult]:
        return [r for r in self.case_results if r.case.should_block]

    @property
    def safe_cases(self) -> list[CaseResult]:
        return [r for r in self.case_results if not r.case.should_block]

    @property
    def block_rate(self) -> float:
        if not self.attack_cases:
            return 0.0
        return sum(1 for r in self.attack_cases if r.blocked) / len(self.attack_cases)

    @property
    def false_positive_rate(self) -> float:
        if not self.safe_cases:
            return 0.0
        return sum(1 for r in self.safe_cases if r.blocked) / len(self.safe_cases)

    @property
    def accuracy(self) -> float:
        if not self.case_results:
            return 0.0
        return sum(1 for r in self.case_results if r.correct) / self.total

    @property
    def avg_latency_ms(self) -> float:
        if not self.case_results:
            return 0.0
        return sum(r.latency_ms for r in self.case_results) / self.total

    @property
    def p99_latency_ms(self) -> float:
        if not self.case_results:
            return 0.0
        sorted_latencies = sorted(r.latency_ms for r in self.case_results)
        idx = max(0, int(len(sorted_latencies) * 0.99) - 1)
        return sorted_latencies[idx]

    def by_category(self) -> dict[str, BenchmarkResult]:
        """Split results by case category."""
        cats: dict[str, list[CaseResult]] = {}
        for r in self.case_results:
            cats.setdefault(r.case.category or "uncategorized", []).append(r)
        return {cat: BenchmarkResult(case_results=results) for cat, results in cats.items()}

    def report(self, verbose: bool = False) -> str:
        lines = [
            "=" * 60,
            "  NeuroSym-AI Benchmark Report",
            "=" * 60,
            f"  Total cases   : {self.total}",
            f"  Attack cases  : {len(self.attack_cases)}",
            f"  Safe cases    : {len(self.safe_cases)}",
            "",
            f"  Block rate    : {self.block_rate * 100:.1f}%  (attacks blocked / total attacks)",
            f"  False pos rate: {self.false_positive_rate * 100:.1f}%  "
            f"(safe inputs wrongly blocked)",
            f"  Accuracy      : {self.accuracy * 100:.1f}%",
            "",
            f"  Avg latency   : {self.avg_latency_ms:.2f} ms",
            f"  P99 latency   : {self.p99_latency_ms:.2f} ms",
        ]

        by_cat = self.by_category()
        if len(by_cat) > 1:
            lines.append("")
            lines.append("  By category:")
            for cat, cat_result in sorted(by_cat.items()):
                lines.append(
                    f"    {cat:<30} block={cat_result.block_rate * 100:.0f}%  n={cat_result.total}"
                )

        if verbose:
            lines.append("")
            lines.append("  Failures:")
            for r in self.case_results:
                if not r.correct:
                    tag = "FP" if r.is_false_positive else "FN"
                    lines.append(f"    [{tag}] {r.case.text[:80]!r}")

        lines.append("=" * 60)
        return "\n".join(lines)


class BenchmarkRunner:
    """Runs a list of BenchmarkCases through a Guard and collects results."""

    def __init__(self, guard: Guard) -> None:
        self.guard = guard

    def run(self, cases: list[BenchmarkCase]) -> BenchmarkResult:
        results: list[CaseResult] = []
        for case in cases:
            t0 = time.perf_counter()
            gr = self.guard.apply_text(case.text)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            # "blocked" = guard flagged at least one violation
            blocked = not gr.ok
            results.append(
                CaseResult(
                    case=case,
                    blocked=blocked,
                    latency_ms=latency_ms,
                    violations=gr.violations,
                )
            )
        return BenchmarkResult(case_results=results)
