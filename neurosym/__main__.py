# neurosym/__main__.py — run: python -m neurosym <command>
from __future__ import annotations

import argparse
from collections.abc import Sequence

from neurosym.engine.guard import Guard
from neurosym.llm.fallback import FallbackLLM
from neurosym.llm.ollama import OllamaLLM
from neurosym.rules.base import Rule
from neurosym.rules.regex_rule import RegexRule


def _build_llm() -> FallbackLLM:
    try:
        from neurosym.llm.gemini import GeminiLLM

        primary = GeminiLLM("gemini-1.5-flash")
    except Exception:
        primary = None

    secondary = OllamaLLM("phi3:mini")
    if primary is None:
        return FallbackLLM(secondary, secondary)
    return FallbackLLM(primary, secondary)


# ── check ──────────────────────────────────────────────────────────────────


def cmd_check(args: argparse.Namespace) -> None:
    rules: list[Rule] = []
    if args.rule == "email":
        rules.append(RegexRule("no-email", r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"))
    llm = _build_llm()
    guard = Guard(rules=rules, llm=llm, max_retries=2)
    res = guard.generate(args.text, temperature=0.2)
    print(res.output)
    print("\nTRACE:\n" + res.report())


# ── packs ──────────────────────────────────────────────────────────────────


def cmd_packs_list(args: argparse.Namespace) -> None:
    from neurosym.rules.adversarial import list_packs

    packs = list_packs()
    if not packs:
        print("No packs found.")
        return
    print(f"{'Name':<24}  {'Ver':<6}  {'Hash':<18}  {'Presets':>7}  Description")
    print("-" * 82)
    for pk in packs:
        n_presets = len(pk["presets"])
        desc = pk["description"][:35]
        print(f"{pk['name']:<24}  {pk['version']:<6}  {pk['hash']:<18}  {n_presets:>7}  {desc}")


def cmd_packs_show(args: argparse.Namespace) -> None:
    import json

    from neurosym.rules.adversarial import _PACKS_DIR, _compute_hash

    pack_file = _PACKS_DIR / f"{args.name}.json"
    if not pack_file.exists():
        print(f"Pack '{args.name}' not found in {_PACKS_DIR}")
        return
    data = json.loads(pack_file.read_bytes())
    # Use the same normalized hash algorithm as list_packs() for consistency
    pack_hash = _compute_hash(data.get("presets", {}))
    print(f"Pack:        {data['name']}  (version {data['version']})")
    print(f"Hash:        {pack_hash}")
    print(f"Description: {data['description']}")
    print(f"\nPresets ({len(data['presets'])} categories):")
    for preset_name, patterns in data["presets"].items():
        print(f"  {preset_name:<32}  {len(patterns)} patterns")


# ── policy ─────────────────────────────────────────────────────────────────


def cmd_policy_lint_demo(args: argparse.Namespace) -> None:
    try:
        from neurosym.policy import lint
        from neurosym.rules.adversarial import PromptInjectionRule
        from neurosym.rules.composite import AllOf, AnyOf, Not
    except ImportError as e:
        print(f"Error importing: {e}")
        return

    r = PromptInjectionRule()
    demos = [
        (
            "Contradictory — AllOf([rule, Not(rule)])",
            AllOf([r, Not(r)], id="contradictory"),
        ),
        (
            "Tautological — AnyOf([rule, Not(rule)])",
            AnyOf([r, Not(r)], id="tautological"),
        ),
        (
            "Valid — AllOf([injection_rule, max_steps(10)])",
            __import__("neurosym.rules.composite", fromlist=["AllOf"]).AllOf(
                [
                    r,
                    __import__("neurosym.rules.action_policy", fromlist=["max_steps"]).max_steps(
                        10
                    ),
                ],
                id="valid_policy",
            ),
        ),
    ]
    print("=== neurosym policy lint demo ===\n")
    for label, policy in demos:
        print(f"Policy: {label}")
        try:
            issues = lint(policy)
        except ImportError as e:
            print(f"  ERROR: {e}")
            break
        if issues:
            for issue in issues:
                print(f"  [{issue.kind.upper()}] {issue.message}")
        else:
            print("  OK — no logical issues detected.")
        print()


# ── doctor ─────────────────────────────────────────────────────────────────


def cmd_doctor(args: argparse.Namespace) -> None:
    from neurosym.version import __version__

    print(f"neurosym-ai  v{__version__}\n")

    from neurosym.rules.adversarial import list_packs

    packs = list_packs()
    print(f"Rule packs ({len(packs)}):")
    if packs:
        for pk in packs:
            print(f"  {pk['name']:<28}  hash={pk['hash']}  presets={len(pk['presets'])}")
    else:
        print("  (none found)")

    print("\nOptional dependencies:")
    _OPTIONAL_DEPS = [
        ("z3-solver", "z3"),
        ("sentence-transformers", "sentence_transformers"),
        ("fastembed", "fastembed"),
        ("pydantic", "pydantic"),
        ("PyYAML", "yaml"),
        ("typer", "typer"),
        ("rich", "rich"),
    ]
    for display, import_name in _OPTIONAL_DEPS:
        try:
            __import__(import_name)
            status = "OK"
        except ImportError:
            status = "not installed"
        print(f"  {display:<30}  {status}")

    print("\nBenchmark (bundled corpus):")
    try:
        from neurosym.bench.corpus.prompt_injection import CASES
        from neurosym.bench.harness import BenchmarkRunner
        from neurosym.rules.adversarial import PromptInjectionRule

        runner = BenchmarkRunner(Guard(rules=[PromptInjectionRule()]))
        result = runner.run(CASES)
        print(
            f"  cases={result.total}"
            f"  block_rate={result.block_rate:.1%}"
            f"  fpr={result.false_positive_rate:.1%}"
            f"  avg={result.avg_latency_ms:.2f}ms"
            f"  p99={result.p99_latency_ms:.2f}ms"
        )
    except Exception as exc:
        print(f"  (benchmark unavailable: {exc})")


# ── main ───────────────────────────────────────────────────────────────────


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="neurosym")
    sub = p.add_subparsers(dest="cmd", required=True)

    # check
    pc = sub.add_parser("check", help="Generate text then validate/repair")
    pc.add_argument("--rule", choices=["email"], default="email")
    pc.add_argument("--text", required=True)
    pc.set_defaults(func=cmd_check)

    # packs
    packs_p = sub.add_parser("packs", help="Manage versioned rule packs")
    packs_sub = packs_p.add_subparsers(dest="packs_cmd", required=True)

    packs_list_p = packs_sub.add_parser("list", help="List available packs")
    packs_list_p.set_defaults(func=cmd_packs_list)

    packs_show_p = packs_sub.add_parser("show", help="Show pack details")
    packs_show_p.add_argument("name", help="Pack name (e.g. injection-v1)")
    packs_show_p.set_defaults(func=cmd_packs_show)

    # policy
    policy_p = sub.add_parser("policy", help="Policy analysis tools")
    policy_sub = policy_p.add_subparsers(dest="policy_cmd", required=True)

    lint_p = policy_sub.add_parser("lint", help="SAT-based policy linter demo")
    lint_p.set_defaults(func=cmd_policy_lint_demo)

    # doctor
    doctor_p = sub.add_parser("doctor", help="Print diagnostic info and quick benchmark")
    doctor_p.set_defaults(func=cmd_doctor)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
