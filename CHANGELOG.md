# Changelog

All notable changes to neurosym-ai are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
