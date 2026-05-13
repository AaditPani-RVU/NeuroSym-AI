# neurosym-ai Roadmap

## v0.3.x — Finish line ✅

- [x] Publish v0.3.3 to PyPI
- [x] py.typed marker
- [x] Near-miss reporting
- [x] SAT linter rule aliasing bug
- [x] Pack hash inconsistency

---

## v0.4.0 — NeMo Guardrails replacement ✅

**Goal:** position neurosym-ai as a credible, lean alternative to NeMo Guardrails for teams that don't need Colang dialog orchestration.

### Shipped

- [x] `ConversationGuard` + `ConversationSession` — stateful multi-turn evaluation, thread-safe, serializable, window-aware gradual-escalation detection
- [x] `IntentClassifierRule` — zero-shot NLI via `facebook/bart-large-mnli`, CPU-only, `[classifier]` extra
- [x] `NeurosymCallbackHandler` — LangChain callback adapter, `[langchain]` extra
- [x] `BENCHMARKS.md` — honest, sourced performance comparison with NeMo
- [x] `MIGRATION_GUIDE.md` — Colang concept mapping with side-by-side code

---

## v0.4.x — Integrity, async, and adapters

**Anchor:** make what 0.4.0 shipped correct, complete, and production-honest before expanding the surface.

### 0.4.1 — Release integrity (immediate)

Bugs caught post-ship that undermine credibility:

- [x] `version.py` was stuck at `0.3.4` while `pyproject.toml` said `0.4.0`
- [x] `no_path_outside_sandbox` prefix bug: `"/sandbox".startswith("/sandbox")` passed `"/sandbox_evil/..."` — fixed to require trailing `os.sep`
- [x] `neurosym.__init__` was missing `RegexRule`, `SchemaRule`, `DenyIfContains`, `PythonPredicateRule` — commonly used symbols that required knowing the submodule path

**Remaining:**
- [ ] `NeurosymCallbackHandler` does not inherit from `BaseCallbackHandler` — current tests use a fake base class, so real LangChain registration is untested. Fix: lazy-inherit via a module-level factory so the class is properly registered in LangChain's callback system
- [ ] `BENCHMARKS.md` bench script (`nemo_comparison.py`) still embeds aggressive NeMo assumptions in reference comments — align with the more careful prose

### 0.4.2 — Async ConversationGuard

- [ ] `ConversationSession.acheck(role, content)` using the existing `Guard.aapply_text()` async path
- [ ] Async-safe locking model: replace `threading.Lock` with a strategy that works correctly under both sync and async callers (asyncio lock inside async methods, threading lock for sync)
- [ ] Tests for concurrent async sessions

**Why here:** `Guard` already has a full async API (`aapply`, `aapply_text`, `agenerate`). `ConversationGuard` being sync-only is an asymmetry that blocks async web frameworks from using it. This is a completion item, not a new feature.

### 0.4.3 — Role-aware conversation artifacts

- [ ] `ConversationSession._build_context()` currently concatenates turns as `[role] content\n` strings. Add an optional structured artifact path: rules that want to inspect individual turns by role can receive a `list[Turn]` instead of flat text
- [ ] Keep flat text as the default — all existing rules continue working unchanged
- [ ] New `ConversationRule` protocol: `evaluate_turns(turns: list[Turn]) -> list[Violation]` — opt-in, does not break `Rule`

**Why here, not 0.5:** `ConversationGuard` is the v0.4 anchor. Role-aware access is a natural extension of it that unblocks rule authors who need to distinguish who said what. Deferring it to v0.5 risks having the protocol baked in wrong once the DSL is designed. Better to ship it early and let it stabilise.

**Where I disagree with Codex on this:** Codex put role-aware artifacts in v0.5 as a companion to the DSL. My view: the protocol shape needs to be stable before the DSL encodes it. Shipping it in 0.4.x means the DSL in 0.5 builds on proven ground.

### 0.4.4 — LlamaIndex adapter

- [ ] `NeurosymQueryHandler` — wraps LlamaIndex query engine calls (input check on the query, output check on the synthesized response)
- [ ] Minimal surface, one supported LlamaIndex interface (`QueryEngine`), tight version pinning in `[llamaindex]` extra
- [ ] Real smoke test against actual LlamaIndex import (not a fake base class)

**Why after 0.4.3:** LlamaIndex copies the LangChain adapter pattern. That pattern needs to be correct first (0.4.1 NeurosymCallbackHandler inheritance fix). Adapters that copy a broken pattern compound the problem.

**Where I disagree with Codex on this:** Codex made LlamaIndex conditional on "adapter contract hardening" but didn't give it a slot. I've given it a concrete slot (0.4.4) once 0.4.1 is done. The dependency is the fix, not an indefinite hold.

---

## v0.5.0 — Policy-as-Code

**Anchor:** make guardrail policies definable, auditable, serializable, and deployable without writing raw Python rule subclasses for every project.

**Why this anchor:** neurosym-ai's current authoring model is `Guard(rules=[BanTopicsRule(), RegexRule(...)])` — powerful but invisible. Teams can't diff policies across deploys, can't audit what version of a policy ran on what request, and can't share policies across services without copying Python source. v0.5 fixes this.

### 1. Python EDSL for policy authoring

- [ ] Typed Python EDSL that compiles to existing `Rule`, `AllOf`, `AnyOf`, `Not`, `Implies` primitives — no new runtime, no interpreter
- [ ] Makes the existing composite algebra ergonomic: named policies, chaining, threshold wiring
- [ ] Explicit allow/block semantics surfaced at the DSL layer (current `AnyOf` semantics are correct but easy to misread)
- [ ] **Not a Colang parser.** No textual DSL, no runtime, no grammar.

**Where I disagree with Codex:** Codex said "no textual format ever." I think a minimal YAML/TOML loader for simple policies — keyword lists, regex patterns, topic presets — is valid and practical for non-Python users (security teams, policy authors). This is narrow scope: serialise/deserialise primitive rule configs, not a full DSL evaluator. I've kept it as a separate item below so it can be scoped independently.

### 2. Serializable policy registry

- [ ] Named, versioned policy snapshots: `PolicySnapshot(id, version, rules_config, pack_hashes, created_at)`
- [ ] Serialize to JSON; deserialize back to a runnable `Guard`
- [ ] Python predicates and custom rule classes are marked opaque with their source key (cannot round-trip, clearly documented)
- [ ] Builds on existing `GuardResult.to_dict()` audit trail and existing pack hashes in `PromptInjectionRule` / `SemanticInjectionRule`

### 3. Declarative config loader (YAML/TOML) for primitive rules

- [ ] Load simple policies from YAML: banned topics, regex patterns, schema paths, severity thresholds
- [ ] No arbitrary code execution — only the rule types that have fully serializable configs (BanTopicsRule, RegexRule, DenyIfContains, SchemaRule, BanTopicsRule presets)
- [ ] Intended audience: security/policy teams who author policies, engineers who deploy them

**Scope limit:** this is a loader, not a DSL. It cannot express `AllOf`, `AnyOf`, or custom predicates. Those stay Python-only.

### 4. Evidence-grounded checks (not generic hallucination detection)

- [ ] New rule family: `GroundingRule(evidence: str | list[str])` — given a retrieved context and an answer, detect claims in the answer that are not supported by the evidence
- [ ] Starting implementation: NLI entailment via `IntentClassifierRule`'s existing pipeline, repurposed for premise/hypothesis
- [ ] **Hard scope limit:** no factuality check without supplied evidence. Without a source document, the library cannot know truth. The rule must require evidence as a constructor argument — no evidence = no rule.
- [ ] Benchmark data required before marking stable (FP/FN rates on a grounding corpus)

**Where Codex was exactly right:** the distinction between "evidence-grounded check" and "generic hallucination detector" is the most important call in v0.5. Generic hallucination detection without a ground truth source is pseudoscience in a library. Codex was sharper on this than the original roadmap.

### 5. Evaluation harness as a release gate

- [ ] Extend existing bench corpus beyond prompt injection to: topic harm (FP + FN), action-policy paths, secret leakage streaming, conversation escalation patterns, grounding recall/precision
- [ ] Metrics tracked per rule class, surfaced in CI
- [ ] v0.5 will not ship without baseline numbers on all new rule classes

**Where Codex was right:** the current test suite is strong on unit behavior but has no product-level metrics. A library that makes safety claims needs recall/precision numbers, not just "test passes."

### Out of scope for v0.5

- Full Colang runtime — neurosym-ai is not a dialog orchestration framework and should not become one
- Generic hallucination detection without evidence input
- Mandatory GPU/model paths in core
- More framework adapters (those belong in 0.4.x)

---

## v0.6.0+ (tentative)

- LlamaIndex deep integration (beyond the basic 0.4.4 adapter)
- Streaming `ConversationGuard` (feed chunks into a multi-turn session)
- OpenTelemetry trace export from `GuardResult`
- Policy diff tooling (compare two `PolicySnapshot` instances)

---

## Debate notes (on record)

### What Codex got right that we acted on

- `version.py` stuck at `0.3.4` — real bug, fixed immediately
- `no_path_outside_sandbox` prefix traversal bug — real security issue, fixed
- Missing top-level exports (`RegexRule`, `SchemaRule`, `DenyIfContains`, `PythonPredicateRule`) — fixed
- `NeurosymCallbackHandler` not inheriting from `BaseCallbackHandler` — valid, added to 0.4.1 backlog
- Evidence-grounding ≠ generic hallucination detection — adopted this framing wholesale
- Evaluation harness as a release gate, not an afterthought — adopted for v0.5

### Where we disagreed with Codex

- **Role-aware conversation artifacts in 0.5 (Codex) vs 0.4.3 (us):** The protocol shape needs to be stable before the v0.5 DSL encodes it. Shipping it in 0.4.x means the DSL builds on proven ground, not speculative design.
- **LlamaIndex as indefinitely deferred (Codex) vs 0.4.4 (us):** Codex said "only after adapter contract hardening" with no concrete slot. We gave it 0.4.4, gated on the 0.4.1 LangChain fix landing first. The dependency is the fix, not an open-ended hold.
- **No YAML/declarative format ever (Codex) vs narrow YAML loader in 0.5 (us):** Codex interpreted "no textual DSL" as "no declarative format at all." We think a config loader for primitive, fully-serializable rules (topic lists, regex patterns) is practical and does not require building an interpreter. Hard-scoped to serializable types only.
- **"Claim calibration" as a blocking 0.4.x priority (Codex) vs done as part of BENCHMARKS rewrite (us):** The BENCHMARKS.md rewrite already fixed the GPU/LLM misleading claims. Codex framed this as an ongoing priority item — we consider it resolved and don't want to keep it on the open list as a distraction.
