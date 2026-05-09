# Changelog

All notable changes to neurosym-ai are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.3.2] — 2026-05-10 — "Semantic fallback, lean install, forecaster hardening"

### Added

- **`SemanticInjectionRule`** (`rules/semantic.py`) — embedding-based fallback detector that
  catches paraphrase attacks missed by the regex layer. Uses `sentence-transformers`
  (`all-MiniLM-L6-v2` by default) with cosine similarity against curated per-category attack
  centroids. Block rate target: 95%+ combined with `PromptInjectionRule`. Composable with
  existing rules; model and centroids are pinned per version for reproducible audit traces.
- **`neurosym/rules/centroids/injection-centroids-v1.json`** — 9 attack categories × ~8
  paraphrase centroid texts each; designed to catch paraphrases that bypass all regex presets.
- **`[embeddings]` extra** (`pip install 'neurosym-ai[embeddings]'`) — gates
  `sentence-transformers>=3.0` and `numpy>=1.24` as optional dependencies.
- **`[cli]` extra** — `typer>=0.12` and `rich>=13.7` moved out of core.
- **`[llm]` extra** — `httpx>=0.27` and `tenacity>=9.0` moved out of core.
- **`[forecaster]` extra** — `pydantic>=2.0` and `PyYAML>=6.0` moved out of core.
- **`[all]` extra** — convenience meta-extra that installs every optional feature.
- **`impact_exceptions.py`** — `ImpactForecastUnavailable` split into its own zero-dep module
  so `import neurosym` never fails when `[forecaster]` is not installed.

### Fixed

- **`ImpactAgent.hypothesize()` silent `[]` on failure** — all failure paths (`result.ok=False`,
  unparseable output, schema mismatch) now raise `ImpactForecastUnavailable` with a descriptive
  `.reason`. Returning `[]` on failure was indistinguishable from "no impact found".
- **`ImpactForecastUnavailable` not exported from forecaster package** — now re-exported from
  `neurosym.agents.impact_forecaster` in addition to the top-level `neurosym` namespace.

### Changed

- **Core install footprint reduced** — `dependencies` in `pyproject.toml` trimmed from 7 packages
  to 1 (`jsonschema`). Guard + rules + benchmark now work with a minimal install.
- **`dev` extra** now depends on `neurosym-ai[all]` so the full test suite always runs against
  every optional feature.

### Added (tests)

- `tests/test_semantic_injection.py` — 20 structural/mock tests + 10 integration tests
  (skipped when `sentence-transformers` not installed): threshold behaviour, category filtering,
  meta field correctness, `ImportError` path, `evaluate()` normalisation contract.
- `tests/test_impact_agent.py` — 15 tests for `ImpactAgent.hypothesize()`: happy path (single,
  multiple, empty list, pre-parsed Python list, markdown-fenced JSON), failure paths (guard
  failure, unparseable output, schema mismatch, wrong type), regression for the silent-`[]` bug,
  export contract from both `neurosym` and `neurosym.agents.impact_forecaster`.

---

## [0.3.1] — 2026-05-03 — "Test the v0.3.0 surface"

### Fixed

- **Guard.stream() yield-before-check** (Codex adversarial finding): the chunk that triggers a
  hard-deny streaming rule was previously forwarded to the consumer before the denial was checked.
  Fixed in `engine/guard.py` — the hard-deny check now runs before `yield`, so the violating
  chunk is suppressed entirely.

### Added (tests)

- `tests/test_output_secrets.py` — `SecretLeakageRule`: AWS, GitHub, Google, Slack, Stripe,
  JWT, bearer, private-key headers; negative cases (UUIDs, hex hashes); full `StreamingRule`
  contract (chunk feeding, cross-boundary detection via the 256-char overlap window, `reset()`).
- `tests/test_output_system_prompt.py` — `SystemPromptRegurgitationRule`: verbatim match,
  sliding-window partial match, false-positive guards, custom `min_span` behaviour.
- `tests/test_streaming.py` — `Guard.stream()`: clean-stream, rule partitioning (batch vs.
  streaming), regression test for the yield-before-check bug, `deny_above` path.
- `tests/test_agents_loader.py` — `load_agent_prompt`, `invalidate_cache`, `AgentNotFoundError`,
  `AgentLoadError` on empty file, `lru_cache` identity, all `registry` functions (`list_agents`,
  `agent_exists`, `get_agent`).
- `tests/test_doctor_cli.py` — `python -m neurosym doctor` exit-code, version string, deps
  section, rule-packs section, benchmark output; Typer entrypoint help and no-args behaviour.

---

## [0.3.0] — 2026-04-xx — "Output guards, streaming, agent system, doctor CLI"

### Added

- `SecretLeakageRule` (`rules/output/secrets.py`) — 12 regex patterns; implements `StreamingRule`.
- `SystemPromptRegurgitationRule` (`rules/output/system_prompt.py`) — sliding-window substring match.
- `Guard.stream()` (`engine/guard.py`) — generator-based streaming with incremental rule evaluation.
- `StreamingRule` protocol (`rules/base.py`).
- Agent loader system (`agents/loader.py`, `agents/registry.py`).
- Bundled agent prompts: `neurosym_dev_agent`, `security_auditor`.
- `ImpactForecastAgent` (`agents/impact_forecaster/`).
- `doctor` CLI subcommand (`python -m neurosym doctor`).
- Typer-based `neurosym` script (`cli_tui.py`).

---

## [0.2.0] — earlier

- Action policy rules (`ActionPolicyRule`, `DESTRUCTIVE_ACTIONS`, `HIGH_RISK_ACTIONS`).
- Z3-based SAT policy linter (`policy/sat.py`, `lint()`).
- Composite rules (`AllOf`, `AnyOf`, `Not`, `Implies`).
- Benchmark harness (`bench/`).

---

## [0.1.3] — earlier

- Initial public release.
- `Guard`, `GuardResult`, `Artifact`, `Rule`, `BaseRule`, `Violation`.
- `PromptInjectionRule` with versioned pack (`rules/packs/injection-v1.json`).
- PII redaction (`pre/redaction.py`).
- JSON schema validation (`rules/schema_rule.py`).
