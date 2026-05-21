# Changelog

All notable changes to neurosym-ai are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.4.3] — 2026-05-22 — "Role-aware conversation artifacts"

### Added

- **`ConversationRule` protocol** (`neurosym.engine.conversation`) — `@runtime_checkable`
  protocol with a single method `evaluate_turns(turns: list[Turn]) -> list[Violation]`.
  Rules implementing `ConversationRule` receive structured turn objects with per-turn
  `role` and `content` instead of a flat text window. This enables role-filtered checks
  (user-only, assistant-only), turn-ordering logic, and per-turn metadata access.

- **Rule routing in `ConversationGuard`** — `__init__` now accepts
  `list[Rule | ConversationRule]`. At construction time rules are split:
  - `ConversationRule` implementors → `evaluate_turns()` path
  - Plain `Rule` implementors → existing flat-text `Guard` path
  - Rules implementing **both** → `evaluate_turns()` path only (no double-evaluation)

- **`ConversationSession._apply_conv_rules()`** — internal helper that runs all
  `ConversationRule` rules and merges violations into the `GuardResult` in-place.
  Called from both `check()` and `acheck()`.

- **`ConversationSession.from_state()` updated** — accepts an optional `conv_rules`
  parameter so restored sessions carry their conversation rules through.

- **Top-level exports** — `ConversationRule` and `Turn` are now exported from
  `neurosym` (previously required knowing the submodule path).

### Added (tests)

- `tests/test_conversation_rule.py` — 13 tests: protocol runtime-checkability,
  `evaluate_turns` receives `list[Turn]` not flat text, window respected, role
  filtering (user-only fires/ignores assistant turns), violation merging, text+conv
  rule co-existence, dual-protocol rule uses `evaluate_turns` exclusively,
  `acheck` runs conv rules, `from_state` preserves conv_rules, export contract.

---

## [0.4.2] — 2026-05-21 — "Async ConversationGuard"

### Added

- **`ConversationSession.acheck(role, content)`** — async version of `check()`, delegates
  to `Guard.aapply_text()` so the event loop is never blocked. The `asyncio.Lock` is held
  only during the brief history snapshot and append steps, never across the `await`.
- **`ConversationSession.aadd(role, content)`** — async version of `add()`.
- **`ConversationGuard.asession()`** — `@asynccontextmanager` yielding a
  `ConversationSession`. Drop-in for `session()` in async web frameworks (FastAPI, Starlette,
  aiohttp). Supports `restore_state=` for cross-request session continuity.
- **Dual locking model** — `threading.Lock` for sync callers (unchanged), `asyncio.Lock`
  for async callers. Neither lock is held across an `await`, so concurrent `acheck` calls
  on the same session are safe without blocking the event loop.

### Added (tests)

- `tests/test_conversation_async.py` — 10 tests: `acheck` clean/blocked, history
  accumulation on violation, multi-turn context via `aadd`, `asession` restore_state,
  20-concurrent `acheck` within one session, 3 independent concurrent sessions,
  interleaved `aadd`/`acheck` ordering.

---

## [0.4.1] — 2026-05-21 — "Release integrity"

### Fixed

- **`NeurosymCallbackHandler` inheritance** — the class now properly inherits from
  `BaseCallbackHandler` via a module-level factory (`_make_handler_class`). Previously it
  was a plain class with no LangChain parent, so LangChain's `isinstance` registration
  checks silently failed. The factory captures the base at import time; if LangChain is
  not installed, instantiation raises `ImportError` with an actionable install hint.
- **`nemo_comparison.py` aggressive GPU claims** — source comment `[1]`, the NeMo result
  `notes` field, the GPU table row, and the summary line all now reflect the accurate
  nuance from `BENCHMARKS.md`: NeMo Guardrails does not require GPU for API-backed
  deployments; GPU is relevant only for self-hosted local model serving.

### Added (tests)

- `test_handler_is_subclass_of_base_callback_handler` — verifies `issubclass` and
  `isinstance` hold against the injected `BaseCallbackHandler`, confirming real LangChain
  registration will work.

---

## [0.3.4] — 2026-05-12 — "Near-miss reporting"

### Added

- **Near-miss reporting** — `SemanticInjectionRule` now accepts a `near_miss_threshold`
  parameter (default `0.0`, disabled). When set, inputs that score between
  `near_miss_threshold` and `threshold` produce `NearMiss` entries in `GuardResult.near_misses`
  instead of violations. Useful for monitoring borderline traffic, threshold tuning, and
  flagging inputs for human review without blocking them.
- **`NearMiss` dataclass** and **`NearMissRule` protocol** exported from `neurosym` top level
  and `neurosym.rules`. Rules implementing `NearMissRule` are automatically called by
  `Guard.apply()` and `Guard.aapply()` when no violations were raised.
- `GuardResult.near_misses` field (list of dicts) included in `to_dict()` output.

---

## [0.3.3] — 2026-05-12 — "BanTopicsRule, SemanticInjectionRule late_resolve hardening"

### Added

- **`BanTopicsRule`** (`rules/harm.py`) — topic-based harm detection that fires on dangerous
  subject matter regardless of phrasing. Closes the structural blind spot in tone/injection-based
  classifiers (100% bypass rate on harmful_content seeds found by Lethe 2026-05-10): clinically-
  or academically-worded synthesis requests score near 0.0 on Toxicity + PromptInjection scanners
  but are caught by topic-pattern matching. Includes four built-in presets:
  - `cbrn_weapons` — CBRN synthesis: explosives (TATP, RDX, PETN), nerve agents (sarin, VX,
    novichok), biological toxins (ricin, botulinum), IED/pipe bomb construction instructions.
  - `drug_synthesis` — illicit drug production: fentanyl, methamphetamine, MDMA, clandestine labs.
  - `self_harm_methods` — suicide and self-harm method requests.
  - `malware_exploit` — working exploit code for CVEs, ransomware/rootkit/RAT creation.
  - Patterns are bidirectional (substance-then-verb and verb-then-substance) with `re.DOTALL`
    so they fire across multi-line prompts regardless of word order.
  - `extra_patterns` parameter for custom additions; `available_presets()` for introspection.

- **`SemanticInjectionRule` tail-segment check** — new `tail_fraction` parameter (default 0.25)
  evaluates the last 25% of the input in isolation alongside the full-text check. Addresses the
  Lethe `late_resolve` bypass: a ~60–80-token innocent preamble context-shifts the full-text
  embedding below threshold even when an injection payload is present at the end. The tail check
  catches the payload independently of its preamble. Violation meta includes `check_mode`
  (`"full"` or `"tail"`), `tail_fraction`, and `tail_word_count` for audit traces. Disabled with
  `tail_fraction=0.0` for backwards-compatible behaviour.

### Added (tests)

- `tests/test_ban_topics.py` — 40 tests: CBRN synthesis true-positives (bidirectional patterns,
  Lethe jb-004 pharma-preamble pipe bomb), drug synthesis, self-harm method requests, working
  exploit true-positives; 18 safe/educational true-negatives including historical mentions,
  addiction/symptom queries, and "explain how X works" queries; preset isolation, extra_patterns,
  `available_presets`, violation field correctness, user_message sanitization, top-level export.
- `tests/test_semantic_injection.py` — 8 new tail-check tests in
  `TestSemanticInjectionRuleTailCheck`: tail fires when full-text passes, full-text early-exit
  (encode called once), `check_mode` field on both violation paths, `tail_fraction=0.0` disables
  tail check, short-text tail skipped, both-below-threshold → None.

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
