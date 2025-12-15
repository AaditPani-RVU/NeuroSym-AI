# neurosym/__main__.py — run: python -m neurosym check --rule email --text "..."
from __future__ import annotations

import argparse
from collections.abc import Sequence

from neurosym.engine.guard import Guard
from neurosym.llm.fallback import FallbackLLM
from neurosym.llm.ollama import OllamaLLM
from neurosym.rules.base import Rule
from neurosym.rules.regex_rule import RegexRule


def _build_llm() -> FallbackLLM:
    """
    Build a fallback LLM chain.

    Note: Gemini is an optional dependency. We import it lazily so that
    `python -m neurosym ...` still works in environments without providers extras.
    """
    try:
        from neurosym.llm.gemini import GeminiLLM  # optional dependency

        primary = GeminiLLM("gemini-1.5-flash")
    except Exception:
        primary = None

    secondary = OllamaLLM("phi3:mini")
    if primary is None:
        # fallback-only mode
        return FallbackLLM(secondary, secondary)
    return FallbackLLM(primary, secondary)


def cmd_check(args: argparse.Namespace) -> None:
    rules: list[Rule] = []
    if args.rule == "email":
        rules.append(RegexRule("no-email", r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"))

    llm = _build_llm()
    guard = Guard(rules=rules, llm=llm, max_retries=2)

    res = guard.generate(args.text, temperature=0.2)
    print(res.output)
    print("\nTRACE:\n" + res.report())


def main(argv: Sequence[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="neurosym")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check", help="Generate text then validate/repair with simple rules")
    pc.add_argument("--rule", choices=["email"], default="email")
    pc.add_argument("--text", required=True)
    pc.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
