━━━ MIMIR ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT   : neurosym-ai
STACK     : Python 3.10+ · Typer CLI · Pydantic v2 · httpx · tenacity · rich · PyYAML · jsonschema · z3-solver (opt) · Pytest
SCANNED   : 2026-05-06 | 99 source files
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[STRUCTURE]
neurosym-ai/
├── neurosym/               — main package
│   ├── agents/             — agent system (loader, registry, impact_forecaster)
│   ├── engine/             — core guard engine (guard.py)
│   ├── llm/                — LLM adapters (base, fallback, gemini, ollama)
│   ├── policy/             — policy rules (action, adversarial, composite, regex, schema, python_pred)
│   ├── rules/              — rule implementations
│   │   ├── output/         — output guards (secrets.py, system_prompt.py)
│   │   └── packs/          — bundled rule packs (injection-v1.json)
│   ├── pre/                — pre-processing (redaction.py)
│   ├── bench/              — benchmark harness
│   ├── tests/              — full test suite (14 test files)
│   ├── utils/              — CLI helpers, JSON tools, plugins
│   ├── schemas/            — JSON schemas (invoice.json)
│   ├── cli_tui.py          — Typer app entry point
│   └── __init__.py         — public API surface
├── docs/                   — documentation
├── pyproject.toml          — build + tooling config
└── CHANGELOG.md            — untracked (in-progress)

[ENTRY POINTS]
neurosym/cli_tui.py   — Typer CLI app; registered as `neurosym` console script
neurosym/__init__.py  — public package API (imports/re-exports for library users)

[DEV COMMANDS]
pip install -e ".[dev]"   → editable install with all dev deps
pip install -e ".[z3]"    → add SMT/constraint solving (z3-solver)
pip install -e ".[providers]" → add cloud LLM SDKs (Gemini, etc.)
pytest                    → run full test suite (testpaths = neurosym/tests)
pytest --cov=neurosym     → run with coverage
mypy neurosym             → strict type checking (excludes tests/examples/agents)
ruff check .              → lint
ruff format .             → format
python -m build           → build sdist + wheel
twine upload dist/*       → publish to PyPI
neurosym                  → run the CLI (after install)

[WISDOM]
(none)

[RECENT WORK]
2026-05-01  feat: v0.3.0 — output guards, streaming, agent system, doctor CLI
2026-04-28  fix: make GeminiLLM import optional to unblock CI
2026-04-28  fix: add pydantic and PyYAML to core dependencies
2026-04-28  feat: add ImpactForecaster agent with symbolic + LLM hybrid analysis
2026-04-28  Update README.md
2026-04-24  chore: update pypi badge to v0.2.0
2026-04-24  Release v0.2.0: adversarial detection, action policies, composite rules, benchmark harness
2025-12-17  chore: mypy strict fixes + fallback typing
2025-12-16  Release 0.1.2
2025-12-16  Improve README with badges and design polish
2025-12-16  Release 0.1.1: production-grade guard engine and JSON tooling

[OPEN THREADS]
(none)

[UNCOMMITTED CHANGES]
M  neurosym/engine/guard.py       (staged)
M  neurosym/version.py            (unstaged)
M  pyproject.toml                 (unstaged)
?? CHANGELOG.md                   (new, untracked)
?? neurosym/tests/test_agents_loader.py      (new, untracked)
?? neurosym/tests/test_doctor_cli.py         (new, untracked)
?? neurosym/tests/test_output_secrets.py     (new, untracked)
?? neurosym/tests/test_output_system_prompt.py (new, untracked)
?? neurosym/tests/test_streaming.py          (new, untracked)
