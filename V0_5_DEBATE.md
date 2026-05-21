## 1. AGREEMENTS

### Production-Grade Safety Is The Right Anchor

- The anchor is directionally sound: v0.4 already has useful safety primitives, but not yet a production safety system.
- The proposed phrase "from proof-of-concept rules to a complete safety system" matches the current repo shape.
- `Guard` is already the runtime enforcement point.
- `Rule` is already the extension contract.
- `GuardResult` is already the decision envelope.
- `Artifact` is already the typed boundary for information-first guarding.
- `ConversationGuard` is already the stateful multi-turn entry point.
- `ActionPolicyRule` is already the structured-agent enforcement primitive.
- The roadmap correctly avoids replacing these primitives.
- The roadmap also correctly frames v0.5 as a layer of policy, evidence, evaluation, observability, and agent integration.
- That layering is healthier than adding another monolithic "safety model" abstraction.
- The core thesis should remain: symbolic checks should compose with optional learned checks, not be hidden behind them.
- The roadmap is strongest when it treats learned components as optional evidence-producing rules.
- The roadmap is weakest only where it implies a complete safety system without a complete evaluation and governance story.
- The proposal at least recognizes that gap by making 0.5.1 an eval gate.
- The production framing should be retained.
- The implementation should be more conservative than the marketing language.
- The library should continue to present itself as a guardrail toolkit, not as a universal safety guarantee.

### Lean Core Is Non-Negotiable And Correct

- The design principle "No mandatory GPU/model in core" is correct.
- The existing package reinforces that principle.
- Core dependencies are currently small: `jsonschema` plus a Python-version-gated typing dependency.
- Heavy features are already behind extras.
- `SemanticInjectionRule` requires `[embeddings]`.
- `IntentClassifierRule` requires `[classifier]`.
- `lint()` requires `z3-solver`.
- LangChain support is behind a soft import pattern.
- This is a strong base for 0.5.
- It keeps first install fast.
- It keeps import-time failures low.
- It makes the library usable in serverless and CI environments.
- It avoids forcing users to download hundreds of megabytes of model weights to use regex, schema, action, and topic rules.
- It makes release testing more tractable.
- It reduces support load from torch, CUDA, tokenizers, and platform-specific wheels.
- It also makes security review simpler because core behavior is mostly deterministic.
- The roadmap correctly extends this pattern with `[otel]`.
- The same rule should apply to grounding.
- `GroundingRule` must not import transformers or torch at module import time.
- `GroundingRule` should either live behind `[classifier]` or a new `[grounding]` extra.
- If it shares NLI dependencies with `IntentClassifierRule`, the extra should be explicit about that reuse.
- The core package must remain usable without network access.
- The core package must remain usable without model downloads.
- The core package must remain usable in locked-down build systems.

### Building On 0.4 Primitives Is The Right Constraint

- The "no rewrites" principle is important.
- `Guard.apply_text()` and `Guard.apply_json()` already cover the most common production integration path.
- `Guard.aapply_text()` and `Guard.agenerate()` already establish async support.
- `Guard.stream()` already covers streaming output enforcement.
- `ConversationSession` already provides state serialization.
- `ActionPolicyRule` already handles structured agent plans.
- Composite rules already establish a policy algebra.
- The SAT linter already defines a logical interpretation over composite rules.
- These pieces are enough to support 0.5 if the design stays disciplined.
- A new policy layer should compile down to existing `Rule` instances.
- A registry should store snapshots of rule configurations, not parallel enforcement logic.
- An audit system should consume `GuardResult`, not invent a second result type.
- A pipeline guard should wrap `Guard` and `ConversationGuard`, not fork their evaluation semantics.
- Tool-call safety should reuse `ActionPolicyRule` and `Artifact(kind="json")`.
- Memory safety should reuse input/output rule evaluation over structured artifacts.
- The current repo has enough building blocks for incremental hardening.
- The roadmap is sound when it treats 0.5 as "operationalization" rather than "new engine".

### PolicySnapshot Is A Good Missing Primitive

- `PolicySnapshot(id, version, rules_config, pack_hashes, created_at)` fills a real gap.
- Today, a `Guard` is a runtime object with a list of rule instances.
- Today, rule configuration is not consistently serializable.
- Today, pack hashes exist inside some violation metadata.
- `PromptInjectionRule` already records `pack` and `pack_hash`.
- `SemanticInjectionRule` already records `centroids_hash`.
- A snapshot can make those provenance details first-class.
- That matters for auditability.
- That matters for reproducibility.
- That matters for benchmark baselines.
- That matters for registry diffs.
- That matters for incident response.
- If a user asks why content was blocked two months later, the answer depends on the exact policy.
- If a user compares two release candidates, the answer depends on rule configuration and pack hashes.
- If a user rolls back a policy, the rollback target must be immutable and addressable.
- A snapshot object is the right unit for this.
- It should be frozen or effectively immutable.
- It should have a stable canonical serialization.
- It should avoid embedding live Python callables.
- It should include the neurosym package version.
- It should include extras-sensitive rule metadata when available.
- It should include pack and centroid identifiers.
- It should include a content hash of the normalized snapshot.
- It should be separate from `Guard` so runtime performance is not dragged into policy management.

### A Policy Authoring Layer Is Justified

- The current low-level API is good for developers.
- It is not yet ideal for policy review.
- A Python EDSL can make policy intent more legible.
- A YAML/TOML loader can support teams that review policies outside application code.
- A CLI can let CI validate policies without importing application modules.
- This is useful for real deployments.
- Policy authoring is especially useful because the repo already has multiple rule families.
- Users need to combine `PromptInjectionRule`, `BanTopicsRule`, `SchemaRule`, `RegexRule`, and action rules.
- Users need a way to name these combinations.
- Users need a way to version them.
- Users need a way to diff them.
- Users need a way to run evaluations against them.
- An EDSL that compiles to `AllOf`, `AnyOf`, `Not`, and `Implies` is consistent with the current codebase.
- A loader for primitive rules is a good starting point.
- Keeping the first loader to primitive rules is the right scope boundary.
- It avoids serializing arbitrary Python code.
- It avoids loading unsafe plugins by default.
- It avoids promising that every custom `Rule` can round-trip through YAML.
- It gives enough value for policy packs and examples.
- This is a worthwhile 0.5.0 scope if constrained tightly.

### The Eval Harness Gate Is The Strongest Part Of The Plan

- Making 0.5.1 a hard release gate is the best design choice in the roadmap.
- Safety libraries are unusually prone to regressions that look like improvements.
- A broader rule can improve recall while silently destroying precision.
- A narrower rule can reduce false positives while letting obvious attacks through.
- A model threshold can look good on a few demos and fail on category splits.
- A policy loader can change semantics even if all unit tests pass.
- Existing benchmarks are already present but limited.
- `BenchmarkCase` already captures text, expected block status, label, and category.
- `BenchmarkRunner` already measures blocked status and latency.
- `BenchmarkResult` already reports block rate, false positive rate, accuracy, average latency, and p99 latency.
- The proposed `EvalHarness` can build directly on this.
- The proposed per-rule-class precision, recall, and F1 are necessary additions.
- The proposed `--fail-below-recall` flag is important for CI.
- It should be paired with a false-positive ceiling.
- It should be paired with latency ceilings for core deterministic policies.
- It should be paired with category minimums.
- A single aggregate recall threshold is too easy to game.
- Pre-built eval datasets for every new rule class are mandatory.
- This is especially true for `GroundingRule`.
- It is also true for YAML loader semantics.
- It is also true for policy diff behavior.
- The gate should apply to every sub-version in v0.5.
- That means 0.5.0 should not ship without at least a policy authoring baseline.
- The spirit of the proposal is correct.
- The sequence needs tightening, but the gate is right.

### AttackLibrary Is A Good Abstraction

- `AttackLibrary` is a natural evolution of `bench/corpus/prompt_injection.py`.
- The current corpus is Python code.
- Python-code corpora are easy to maintain for developers.
- They are less convenient for external contribution, metadata validation, and CLI usage.
- An `AttackLibrary` can normalize datasets from Python modules, JSONL, and package resources.
- It can make categories explicit.
- It can make expected outcome explicit.
- It can make rule-class targeting explicit.
- It can make dataset versions explicit.
- It can include provenance without leaking unsafe content in end-user logs.
- The "8+ categories" target is reasonable because the existing prompt injection corpus already has many categories.
- Categories should include safe cases, not only attack cases.
- Categories should include near-miss cases.
- Categories should include benign dual-use cases.
- Categories should include role-specific conversation cases.
- Categories should include structured tool-call cases.
- The abstraction should support local datasets in CI.
- The abstraction should avoid fetching datasets over the network at test time.
- The abstraction should have deterministic iteration order.
- The abstraction should carry a dataset hash.
- This will make benchmark deltas credible.

### GroundingRule Is Correctly Scoped To Evidence Entailment

- The proposal's hard scope limit is important: `GroundingRule` is not generic hallucination detection.
- Generic hallucination detection is an overloaded and frequently misleading product claim.
- Evidence-grounded checking is a narrower and testable claim.
- The constructor requirement `GroundingRule(evidence: str | list[str])` is sound.
- The "no evidence = TypeError" rule is right.
- It prevents users from instantiating a fake hallucination detector.
- It makes the API honest.
- It forces the caller to define the grounding source.
- It supports deterministic audit fields.
- It allows evaluation to distinguish entailed, contradicted, and not-enough-information cases.
- It also aligns with the current optional classifier model pattern.
- `IntentClassifierRule` already wraps NLI-style classification.
- Grounding can reuse the NLI dependency family without making it core.
- Grounding should produce structured metadata: claim spans, evidence ids, label, score, threshold.
- Grounding should treat "not enough information" differently from "contradiction".
- The output policy can then decide whether unsupported claims block, warn, or create near misses.
- That is a better architecture than returning a single generic "hallucination" violation.

### Observable Safety Is A Necessary Production Layer

- `GuardResult.to_dict()` already gives a serializable representation.
- `TraceEntry` already records attempts, prompt used, input, output, violations, and repairs.
- `Violation` already supports machine-readable metadata.
- `NearMiss` already exists.
- These are the right inputs for observability.
- OpenTelemetry support belongs in an optional extra.
- Audit logs belong outside the enforcement path unless explicitly enabled.
- A structured `AuditLog` abstraction is useful.
- Pluggable sinks are useful.
- Near-miss aggregation is useful because near misses are not valuable if they remain isolated per request.
- Threshold suggestions are plausible if scoped to "suggestions" rather than auto-tuning.
- The proposal correctly separates `GuardResult.to_otel_span()` from core enforcement.
- However, it should avoid tying `GuardResult` to a live OpenTelemetry span object in core.
- The clean implementation is likely `to_otel_attributes()` in core and `to_otel_span()` behind `[otel]`.
- The overall direction is correct.
- Safety systems need observability because policy decisions become operational incidents.
- Production users need to answer "what changed", "what fired", "how often", "on whose traffic", and "with what latency".
- The roadmap names these concerns.

### Registry And Diff Are Natural After Snapshots

- `PolicyRegistry` follows naturally from `PolicySnapshot`.
- Content addressing is the right storage model.
- SHA-256 is an appropriate default.
- A local file-based registry is the right v0.5 scope.
- A remote service is not necessary for 0.5.
- Local registry support helps CI.
- Local registry support helps rollbacks.
- Local registry support helps reproducible examples.
- `PolicySnapshot.diff(other)` is useful for human review.
- Diffs should be structured, not raw text.
- Diffs should include rule additions.
- Diffs should include rule removals.
- Diffs should include parameter changes.
- Diffs should include pack hash changes.
- Diffs should include severity changes.
- Diffs should include threshold changes.
- Diffs should include dataset baseline changes only if eval results are attached separately.
- Optional signed policies are directionally right.
- Keeping signing optional is correct.
- GPG and SSH signing both have user-environment complexity.
- The registry should not block the core roadmap on signing.
- The registry should provide a stable manifest format before signatures.
- The proposed push/pull/diff/rollback CLI is useful if kept local-first.

### Agentic Pipeline Safety Is The Right End-State

- Agentic safety is the right end-state for v0.5.
- The repo already has parts of it.
- `ConversationGuard` already handles multi-turn state.
- `ActionPolicyRule` already handles structured plans.
- `no_path_outside_sandbox()` already covers a high-risk class of tool misuse.
- `destructive_needs_confirmation()` already covers confirmation semantics.
- `NeurosymCallbackHandler` already integrates with LangChain at LLM input/output boundaries.
- What is missing is first-class tool call and memory semantics.
- A `PipelineGuard` can unify multiple guard points in an agent loop.
- A `ToolCallGuard` can evaluate pre-call arguments and post-call results.
- A `MemoryGuard` can separate read and write policies.
- `AgentTrustLevel` is a strong idea because source trust matters.
- System instructions, user input, tool output, retrieved content, memory, and agent-generated plans should not share one policy blindly.
- Different trust levels need different rule sets.
- This is especially true for indirect prompt injection from tool outputs and retrieved documents.
- The proposal correctly places agentic safety after policy authoring, eval, evidence, observability, and registry.
- It is complex enough to be last.
- It should remain last unless split into smaller pieces.

### Existing Async Support Supports The Roadmap

- `Guard.aapply()` already evaluates rules concurrently.
- Sync rules are run via `asyncio.to_thread()`.
- Native async rules can expose `aevaluate()`.
- `ConversationSession.acheck()` already avoids holding the async lock across evaluation.
- `Guard.agenerate()` already wraps blocking LLM calls in an executor.
- This means 0.5 does not need a new async runtime.
- Pipeline and tool guards can build on `aapply_json()` and `aapply_text()`.
- Observability can record async spans without changing rule contracts.
- Eval harnesses can add async runners later without blocking initial sync support.
- The current design does expose thread-pool costs for many sync rules.
- That is manageable in 0.5 with documentation and benchmarks.
- It is not a reason to rewrite `Guard`.

### Existing Streaming Support Is A Useful Constraint

- `StreamingRule` is already present.
- `BanTopicsRule` already implements streaming-style `feed()`, `finalize()`, and `reset()`.
- `Guard.stream()` already stops before yielding a chunk that triggers hard-deny streaming violations.
- This is important for production output safety.
- The roadmap should preserve this behavior.
- Policy authoring must not make streaming rules impossible to express.
- Eval harnesses should eventually include streaming cases.
- Observability should distinguish pre-yield blocking from post-hoc blocking.
- Pipeline safety should preserve streaming semantics for agent outputs.
- This is another reason to build on existing primitives.

### Sanitized User Messaging Is A Good Pattern

- `Violation` already separates `message` from `user_message`.
- `GuardResult.user_summary()` already exposes sanitized summaries.
- This is a strong safety and product choice.
- It reduces accidental echoing of attack text.
- It gives application developers a safe default.
- Audit logs can preserve full metadata for restricted access.
- OpenTelemetry attributes should probably avoid raw matched text by default.
- Policy diffs can show rule configuration without exposing user content.
- Eval reports can show redacted examples by default.
- The roadmap should make this separation explicit in observability and audit sections.
- It should avoid adding APIs that encourage raw prompt logging by default.

### Pack Hashes Are Already A Good Provenance Pattern

- `PromptInjectionRule` has pack loading and hash computation.
- `list_packs()` already returns pack metadata.
- `SemanticInjectionRule` has centroid hashes.
- These are strong precedents for policy snapshot design.
- `PolicySnapshot.pack_hashes` should not be an afterthought.
- It should generalize the existing pack-hash behavior.
- Pack hashes should be recorded for regex packs.
- Pack hashes should be recorded for harm presets if they become externalized.
- Pack hashes should be recorded for grounding datasets.
- Pack hashes should be recorded for eval datasets.
- The registry should use the same canonicalization approach.
- The diff system should highlight pack hash changes as high-impact.

### CLI Expansion Is Reasonable

- The package already exposes `neurosym = "neurosym.cli_tui:app"`.
- There are existing tests for doctor CLI.
- A `neurosym policy lint` command is consistent with the package.
- A `neurosym eval` command is consistent with production CI usage.
- A `neurosym audit` command is plausible after structured audit logs exist.
- A `neurosym policy diff` command is useful after snapshots exist.
- The CLI should remain an optional `[cli]` feature if it requires Typer and Rich.
- The core library should expose Python APIs independently of CLI installation.
- CLI commands should fail clearly when optional extras are missing.
- The roadmap direction is correct.

## 2. CHALLENGES AND REFRAMES

### Challenge: 0.5.1 As A Gate Cannot Come After 0.5.0 In Practice

- The proposal says 0.5.1 is a hard release gate for all of 0.5.
- But 0.5.0 is itself part of 0.5.
- If 0.5.0 ships before the eval harness, the gate is violated.
- The current sequence creates a governance contradiction.
- This is not just process pedantry.
- Policy authoring can change semantics without changing runtime rules.
- A buggy loader can silently invert `must_not_match`.
- A buggy EDSL can compile `allow_if` into a blocking condition.
- A buggy snapshot canonicalizer can miss meaningful diffs.
- These are exactly the changes that need a baseline before release.
- Concrete alternative: make evaluation infrastructure the first 0.5 artifact.
- Concrete alternative: release `0.5.0` as "Evaluation Foundation And Policy Snapshot".
- Concrete alternative: move authoring syntax to `0.5.1`.
- Concrete mitigation if numbering cannot change: require 0.5.0 to include a minimal `EvalHarness` before public release.
- Concrete mitigation: treat the named "0.5.1" as an internal milestone, not a public package version.
- Concrete mitigation: add a `release_gate.md` or CI job that blocks every 0.5 tag until eval baselines exist.
- Recommended reframe: "No new rule class or policy compiler ships without a dataset and baseline."

### Challenge: The EDSL Must Respect Violation Semantics

- The repo's `Rule` contract is violation-oriented.
- `evaluate(output) -> list[Violation]` means an empty list is pass.
- `AllOf` aggregates child violations.
- `AnyOf` violates only if all children violate.
- `Not` violates when the inner rule passes.
- `Implies` treats the condition as "passes" when it has no violations.
- This is not the same as a boolean predicate algebra over "allowed".
- A fluent API like `policy(x).block(...).allow_if(...)` risks hiding that distinction.
- The phrase `allow_if` is especially dangerous.
- Users will read it as "if condition true then allow".
- But existing `Rule` instances do not return true or false.
- They return violations.
- A condition rule that passes is semantically "true" only by convention.
- A condition rule that violates is semantically "false" only in the SAT linter's abstraction.
- This must be explicit.
- Concrete alternative: introduce named predicate wrappers.
- Example API: `when(PredicateRule(...)).require(Rule(...))`.
- Example API: `deny_if(Rule(...))` for normal violation rules.
- Example API: `allow_if(PassPredicate(...))` only for rules declared as predicates.
- Concrete alternative: make the EDSL compile through a small internal AST first.
- Suggested classes:
- `PolicyExpr`
- `Deny(rule: Rule)`
- `Require(predicate: Rule)`
- `AllowAny(predicates: list[Rule])`
- `DenyAll(rules: list[Rule])`
- `DenyWhen(condition: Rule, consequence: Rule)`
- The AST should then compile to existing composites.
- This makes semantics auditable before touching runtime behavior.
- Concrete mitigation: documentation must define "fires" vs "passes".
- Concrete mitigation: CLI lint output must show compiled composite form.
- Concrete mitigation: unit tests must assert compiled behavior on stub rules.
- Concrete mitigation: avoid shipping `allow_if` until its semantics are unambiguous.

### Challenge: PolicySnapshot Cannot Serialize Arbitrary Rule Instances

- The current rule ecosystem includes objects with compiled regexes.
- It includes JSON schema validators.
- It includes closures in `ActionPolicyRule`.
- It includes function-decorated rules from `@rule`.
- It includes model-backed rules with cached encoders and pipelines.
- It includes rules that may have private fields.
- It includes custom user classes.
- A generic `rules_config` field is too vague.
- If snapshots try to serialize arbitrary Python objects, the feature will be brittle and unsafe.
- If snapshots serialize only primitive rules, the scope must say so.
- Concrete alternative: define a `RuleConfig` schema for built-in serializable rules.
- Suggested shape:
- `{"type": "RegexRule", "id": "...", "params": {...}}`
- `{"type": "BanTopicsRule", "id": "...", "params": {"presets": [...]}}`
- `{"type": "PromptInjectionRule", "id": "...", "params": {"presets": [...], "pack": "injection-v1"}}`
- `{"type": "SchemaRule", "id": "...", "params": {"schema": {...}}}`
- `{"type": "SemanticInjectionRule", "id": "...", "params": {"centroids": "...", "threshold": 0.75}}`
- `{"type": "IntentClassifierRule", "id": "...", "params": {"bad_intents": [...], "threshold": 0.7, "model": "..."}}`
- User custom rules should be referenced, not serialized.
- Suggested custom rule shape:
- `{"type": "python", "import": "myapp.rules:MyRule", "params": {...}, "trusted": false}`
- By default, the loader should reject `type: python`.
- A CLI flag like `--allow-python-rules` can enable it for trusted CI.
- Concrete mitigation: snapshots can include `unserializable_rules` metadata for runtime-created guards.
- Concrete mitigation: require built-in rule classes to implement `to_config()` before they are supported by snapshot round-trip.
- Concrete mitigation: do not promise universal round-trip in 0.5.0.

### Challenge: YAML/TOML Loading Is A Security Boundary

- Policy files are executable in effect even if they are data files.
- A loaded policy decides what content is blocked.
- A malicious policy can disable safety.
- A malicious policy can lower thresholds.
- A malicious policy can remove harm presets.
- A malicious policy can change severity so `deny_above` no longer triggers.
- A malicious policy can point to unsafe external packs if external packs are supported.
- YAML parsing itself can be dangerous if unsafe loaders are used.
- TOML is simpler but still semantically powerful.
- Concrete alternative: support TOML first for primitive rules.
- Concrete alternative: support YAML only through `yaml.safe_load` behind `[policy-yaml]` or `[cli]`.
- Concrete mitigation: never instantiate arbitrary imports by default.
- Concrete mitigation: require an allowlist registry for rule types.
- Suggested class: `RuleFactoryRegistry`.
- Suggested method: `RuleFactoryRegistry.register(type_name: str, factory: Callable[[dict], Rule])`.
- Suggested default registry: built-in primitive rule factories only.
- Suggested loader API:
- `load_policy(path, *, trusted_python=False, registry=None) -> PolicySnapshot`
- Suggested compiler API:
- `compile_policy(snapshot, *, registry=None) -> Guard`
- Concrete mitigation: policy lint should report use of custom or untrusted rule factories.
- Concrete mitigation: policy snapshots should include the source file hash.
- Concrete mitigation: policy push should refuse unsigned or unreviewed policy changes in strict mode.

### Challenge: DenyIfContains Is Not Currently A Named Rule

- The roadmap mentions `DenyIfContains`.
- The repo has `RegexRule`.
- The repo has `BanTopicsRule`.
- The repo has output secret and system prompt rules.
- There is no obvious `DenyIfContains` file in the listed context.
- Adding a new named rule just for substring matching may be useful.
- But it can also duplicate `RegexRule`.
- Concrete alternative: implement it as a loader alias to `RegexRule`.
- Example:
- `DenyIfContains(tokens=["foo", "bar"], case_sensitive=False)`
- Compiles to `RegexRule(id=..., pattern=[re.escape(token) ...], must_not_match=True, flags=re.I)`.
- Concrete mitigation: if exposed as a Python class, keep it tiny and deterministic.
- Suggested API:
- `ContainsRule(id: str, values: list[str], mode: Literal["any", "all"]="any", case_sensitive: bool=False, must_not_contain: bool=True)`
- Better name: `ContainsRule`, not `DenyIfContains`.
- Rationale: rule classes should describe detection; policy layers decide deny behavior.
- If the roadmap keeps `DenyIfContains`, document it as a policy-loader shorthand.

### Challenge: Policy Lint Needs More Than SAT

- `neurosym/policy/sat.py` is a strong start.
- But it reasons over abstract firing variables.
- It does not know regex language inclusion.
- It does not know schema satisfiability.
- It does not know model thresholds.
- It does not know severity routing.
- It does not know `deny_above`.
- It does not know `deny_rule_ids`.
- It does not know custom rule side effects.
- A `policy lint` CLI that only runs SAT will overpromise.
- Concrete alternative: split lint checks into tiers.
- Tier 1: structural lint.
- Tier 2: SAT lint for composites.
- Tier 3: configuration lint for built-in rule types.
- Tier 4: dataset smoke eval.
- Suggested class names:
- `PolicyLintResult`
- `PolicyLintIssue`
- `PolicyLinter`
- `StructuralPolicyLinter`
- `SatPolicyLinter`
- `BuiltinConfigLinter`
- Suggested issue severities:
- `error`
- `warning`
- `info`
- Suggested issue kinds:
- `unknown_rule_type`
- `unserializable_rule`
- `missing_eval_dataset`
- `unsatisfiable_policy`
- `tautological_policy`
- `subsumed_rule`
- `unsafe_custom_import`
- `missing_pack_hash`
- `threshold_out_of_range`
- `severity_not_denied`
- Concrete mitigation: CLI output should say "logical abstraction" for SAT findings.
- Concrete mitigation: `z3-solver` should remain optional under `[z3]`.
- Concrete mitigation: `neurosym policy lint` should degrade gracefully without Z3.

### Challenge: Severity And Blocking Semantics Are Under-Specified

- `GuardResult.ok` is true iff no violations.
- `GuardResult.blocked` is always `not ok`.
- `hard_denied` is only set by `deny_above` or `deny_rule_ids`.
- This is clearly documented in `Guard`.
- Production policies often need more than this.
- Some users want warnings that do not block.
- Near misses already exist and do not block.
- `Severity="info"` still blocks today if it is a `Violation`.
- A policy authoring layer will expose this tension.
- Users will expect severity to affect blocking.
- The current engine treats severity as metadata unless deny thresholds are configured.
- Concrete alternative: keep engine semantics unchanged but add `PolicyDecision`.
- Suggested class:
- `PolicyDecision(allowed: bool, hard_denied: bool, violations: list[Violation], warnings: list[Violation])`
- But this may be too much for 0.5.
- Concrete mitigation: policy authoring should avoid "warn" until a non-blocking finding type exists.
- Concrete mitigation: use `NearMiss` for non-blocking signals.
- Concrete mitigation: `PolicySnapshot` should record `deny_above` and `deny_rule_ids`.
- Concrete mitigation: docs must state that any `Violation` blocks under current `Guard` semantics.
- Concrete mitigation: if a policy wants severity-based blocking, it must construct `Guard(deny_above=...)` but still gets `blocked=True` for all violations today.
- This inconsistency deserves a design note before 0.5.

### Challenge: GroundingRule May Become A Model Wrapper With False Authority

- NLI models are useful but brittle.
- They are sensitive to evidence length.
- They are sensitive to claim segmentation.
- They are sensitive to domain vocabulary.
- They can confuse contradiction with lack of support.
- They can be overconfident.
- CPU inference latency may be high.
- The default BART MNLI model is large.
- Users may treat a grounding pass as factual truth.
- The API must prevent that interpretation.
- Concrete alternative: name outputs as "entailment checks", not "truth checks".
- Suggested result metadata:
- `label: "entailed" | "contradicted" | "not_supported"`
- `score: float`
- `threshold: float`
- `evidence_ids: list[str]`
- `claims_checked: list[dict]`
- `model: str`
- `mode: "nli"`
- Concrete alternative: add a `ClaimExtractor` boundary but keep default claim extraction deterministic.
- Suggested constructor:
- `GroundingRule(evidence: str | list[str], *, threshold=0.75, mode="sentence", model="facebook/bart-large-mnli")`
- For v0.5, use sentence-level checks only.
- Do not add LLM-based claim extraction in 0.5.
- Concrete mitigation: require explicit evidence.
- Concrete mitigation: require `[grounding]` or `[classifier]` extra.
- Concrete mitigation: include a grounding eval corpus before release.
- Concrete mitigation: expose `unsupported_action: Literal["violate", "near_miss"] = "violate"` only after non-blocking semantics are clear.
- Concrete mitigation: document that absence of contradiction is not entailment.

### Challenge: Grounding Evidence Needs Stable Identity

- The constructor `GroundingRule(evidence: str | list[str])` is too minimal for audits.
- A list of strings has no stable evidence identity.
- Audit logs need to say which evidence supported or contradicted a claim.
- Policy snapshots need to hash evidence.
- Diff needs to know whether evidence changed.
- Eval baselines need stable corpus IDs.
- Concrete alternative: accept an evidence source type.
- Suggested class:
- `Evidence(id: str, text: str, meta: dict[str, Any] | None = None)`
- Suggested constructor:
- `GroundingRule(evidence: str | Evidence | list[str | Evidence], ...)`
- If strings are provided, assign deterministic ids like `evidence[0]`.
- Snapshot serialization should include evidence hashes, not necessarily full evidence text.
- Audit logs should record evidence ids and hashes by default.
- Full evidence text should be optional because it may contain sensitive data.
- Concrete mitigation: if full evidence is embedded, snapshot should mark it as embedded evidence.
- Concrete mitigation: large evidence collections should be rejected in v0.5.2 unless chunking semantics are defined.

### Challenge: Observability Can Leak Sensitive Content

- `TraceEntry` contains prompts and outputs.
- Violations may contain matched examples.
- Regex metadata includes example match text.
- Prompt injection metadata includes match examples.
- Schema validation metadata includes instance excerpts.
- Audit logs and OTel attributes can easily exfiltrate sensitive content.
- Production observability systems often have broad access.
- This is a serious safety and compliance risk.
- Concrete alternative: default audit mode should be redacted.
- Suggested API:
- `AuditLog(redaction="summary")`
- `AuditLog(redaction="metadata")`
- `AuditLog(redaction="raw")`
- Default should be `"summary"`.
- Suggested methods:
- `GuardResult.to_audit_event(redaction="summary")`
- `GuardResult.to_otel_attributes(redaction="summary")`
- Raw prompt and output logging should require explicit opt-in.
- Concrete mitigation: use `GuardResult.user_summary()` for default user-facing and low-trust logs.
- Concrete mitigation: OTel attributes should avoid high-cardinality raw text.
- Concrete mitigation: matched spans should be counted, not emitted, unless raw mode is enabled.
- Concrete mitigation: audit sinks should support field-level redaction hooks.
- Concrete mitigation: docs should warn that audit logs may contain security-sensitive attack strings.

### Challenge: `GuardResult.to_otel_span()` Is Probably The Wrong Core API

- OpenTelemetry spans are usually created by a tracer, not by data objects.
- A `GuardResult` does not know the active tracer.
- A `GuardResult` does not know span lifecycle.
- A `GuardResult` does not know service-level attribute naming conventions.
- Returning a live span object from `GuardResult` risks awkward coupling.
- It would also import OTel types if implemented directly.
- Concrete alternative: core API returns attributes.
- Suggested core method:
- `GuardResult.to_otel_attributes(redaction: str = "summary") -> dict[str, Any]`
- Suggested optional helper:
- `record_guard_result_span(tracer, result, *, name="neurosym.guard", redaction="summary")`
- Suggested optional class:
- `OpenTelemetrySink(AuditSink)`
- Concrete mitigation: keep `[otel]` extra out of core imports.
- Concrete mitigation: if `to_otel_span()` ships, implement it in a separate `neurosym.integrations.otel` module.
- Concrete mitigation: document semantic convention names.
- Suggested attributes:
- `neurosym.ok`
- `neurosym.blocked`
- `neurosym.hard_denied`
- `neurosym.violation.count`
- `neurosym.rule.ids`
- `neurosym.policy.id`
- `neurosym.policy.version`
- `neurosym.policy.hash`
- `neurosym.latency_ms`

### Challenge: NearMissAggregator Needs Strong Scope Control

- Near misses are useful.
- Automatic threshold suggestions are risky.
- A near-miss stream is not a statistically valid calibration set by default.
- Production traffic can be adversarially manipulated.
- Attackers can poison near-miss distributions.
- Different tenants may have different acceptable precision and recall.
- Aggregating by time window alone can hide population shifts.
- Concrete alternative: call it `NearMissReport` first.
- Concrete alternative: suggestions should be disabled by default.
- Suggested API:
- `NearMissAggregator(window: timedelta, min_count: int, group_by=("rule_id",))`
- `aggregate(events) -> list[NearMissCluster]`
- `suggest_thresholds(clusters, *, mode="conservative") -> list[ThresholdSuggestion]`
- Suggestions should include confidence and sample count.
- Suggestions should never mutate a policy.
- Concrete mitigation: include current threshold, proposed threshold, expected delta, and dataset limitation.
- Concrete mitigation: require eval harness confirmation before applying threshold changes.
- Concrete mitigation: audit CLI should label suggestions as advisory.

### Challenge: Registry Push/Pull Implies A Remote Without Defining One

- The proposal says local file-based registry.
- It also says push/pull.
- Push/pull usually implies a remote registry.
- A remote registry is a much larger product surface.
- It brings auth.
- It brings trust roots.
- It brings server APIs.
- It brings conflict resolution.
- It brings multi-user concurrency.
- It brings signing and key management.
- That is too much for 0.5.
- Concrete alternative: define push/pull as filesystem operations.
- Example:
- `neurosym policy push ./registry policy.yaml`
- `neurosym policy pull ./registry --id default --version 1.2.0`
- Better command names for local-only:
- `neurosym policy import`
- `neurosym policy export`
- `neurosym policy pin`
- `neurosym policy rollback`
- Concrete mitigation: reserve networked push/pull for v0.6.
- Concrete mitigation: if command names stay, document URI support as `file://` only in v0.5.
- Concrete mitigation: registry manifests should include `schema_version`.

### Challenge: Signed Policies Are High Value But High Friction

- Optional signing is directionally right.
- GPG support is painful in CI.
- SSH signing support depends on Git and platform tooling.
- Python-native signature verification adds dependencies.
- Users will ask which signatures are trusted.
- Key rotation becomes a feature.
- Revocation becomes a feature.
- Expiry becomes a feature.
- This can consume an entire release.
- Concrete alternative: ship hash pinning first.
- Suggested v0.5 scope:
- `PolicySnapshot.sha256`
- registry manifest with hash references.
- `neurosym policy verify --hash ...`
- Concrete later scope:
- `neurosym policy sign`
- `neurosym policy verify --keyring ...`
- Concrete mitigation: include a signature extension field in the manifest but do not implement enforcement in 0.5.4.
- Concrete mitigation: document how users can sign registry files externally with Git or CI.

### Challenge: AgentTrustLevel Needs A Threat Model Before An Enum

- The idea is strong.
- The details are under-specified.
- Trust level can refer to source identity.
- Trust level can refer to data integrity.
- Trust level can refer to privilege.
- Trust level can refer to policy strictness.
- A simple enum may obscure these differences.
- Example sources:
- `system`
- `developer`
- `user`
- `assistant`
- `tool`
- `retrieved_document`
- `memory`
- `external_web`
- Example risk contexts:
- untrusted text.
- privileged instruction.
- confidential content.
- tool arguments.
- tool results.
- memory write.
- memory read.
- Concrete alternative: use `TrustContext`.
- Suggested class:
- `TrustContext(source: str, trust_level: AgentTrustLevel, channel: str, meta: dict | None = None)`
- Suggested enum:
- `AgentTrustLevel.SYSTEM`
- `AgentTrustLevel.TRUSTED_APP`
- `AgentTrustLevel.USER`
- `AgentTrustLevel.TOOL_OUTPUT`
- `AgentTrustLevel.UNTRUSTED_EXTERNAL`
- Concrete mitigation: allow policy routing by context fields, not only enum.
- Suggested API:
- `PipelineGuard.route(context: TrustContext) -> Guard`
- Concrete mitigation: document default routes.
- Concrete mitigation: do not imply that `system` text is always safe; system prompts can be misconfigured or leaked.

### Challenge: PipelineGuard Can Easily Become A Framework

- Agent loops differ widely.
- LangChain agents differ from LlamaIndex workflows.
- Custom async loops differ from both.
- Tool-call schemas differ.
- Memory APIs differ.
- Streaming behavior differs.
- Retry behavior differs.
- Human confirmation differs.
- A generic `PipelineGuard` can become too abstract to be useful.
- Concrete alternative: define small guard points first.
- Suggested primitives:
- `ToolCall`
- `ToolResult`
- `MemoryRecord`
- `PipelineStep`
- `ToolCallGuard`
- `MemoryGuard`
- Then define `PipelineGuard` as orchestration glue.
- Concrete mitigation: keep `PipelineGuard` framework-neutral.
- Concrete mitigation: provide adapters separately.
- Suggested extras:
- `[langchain]` for LangChain callback/tool wrappers.
- `[llamaindex]` only if implemented later.
- `[agents]` for framework-neutral agent primitives if dependencies remain lean.
- Concrete mitigation: do not add agent loop execution.
- The library should guard agent loops, not become an agent runtime.

### Challenge: ToolCallGuard Must Distinguish Pre-Call And Post-Call Semantics

- A tool call before execution is an intent and arguments object.
- A tool result after execution is untrusted content and possible data.
- These need different rules.
- `ActionPolicyRule` is appropriate pre-call.
- `PromptInjectionRule` may be appropriate post-call for tool output.
- `BanTopicsRule` may be appropriate for user-provided tool arguments.
- `no_path_outside_sandbox()` is specifically pre-call.
- PII leakage rules are likely post-call and pre-send.
- Concrete alternative:
- `ToolCallGuard(pre_rules: list[Rule], post_rules: list[Rule])`
- Suggested API:
- `check_call(tool_name: str, args: dict, context: TrustContext | None = None) -> GuardResult`
- `check_result(tool_name: str, result: Any, context: TrustContext | None = None) -> GuardResult`
- Async variants should exist from day one.
- `acheck_call(...)`
- `acheck_result(...)`
- Concrete mitigation: represent tool calls as `Artifact(kind="json")`.
- Concrete mitigation: include tool name in artifact meta.
- Concrete mitigation: support per-tool policy overrides.

### Challenge: MemoryGuard Needs A Data Model

- "Guard read/write to agent memory" is correct but vague.
- Memory can be vector-store chunks.
- Memory can be key-value facts.
- Memory can be chat history.
- Memory can be user profile.
- Memory can be cached tool results.
- Memory can include embeddings and metadata.
- Memory write risks differ from memory read risks.
- Write risks include prompt injection persistence.
- Write risks include PII retention.
- Write risks include poisoned instructions.
- Write risks include policy-evading paraphrases.
- Read risks include PII disclosure.
- Read risks include untrusted instruction retrieval.
- Read risks include stale or low-trust content influencing privileged actions.
- Concrete alternative: define `MemoryRecord`.
- Suggested class:
- `MemoryRecord(id: str, content: str, namespace: str | None = None, meta: dict | None = None, trust: TrustContext | None = None)`
- Suggested guard:
- `MemoryGuard(write_guard: Guard, read_guard: Guard, namespace_policies: dict[str, Guard] | None = None)`
- Suggested methods:
- `check_write(record: MemoryRecord) -> GuardResult`
- `check_read(records: list[MemoryRecord], purpose: str | None = None) -> GuardResult`
- Concrete mitigation: do not implement vector DB integrations in core.
- Concrete mitigation: provide examples for wrapping common memory stores.

### Challenge: LlamaIndex Integration Should Not Be Promised Without Ownership

- The roadmap says ToolCallGuard plugs into LangChain/LlamaIndex.
- The repo currently has LangChain integration.
- It does not show a LlamaIndex integration.
- LlamaIndex APIs change.
- Supporting two agent frameworks can double compatibility work.
- Concrete alternative: ship framework-neutral `ToolCallGuard` in 0.5.5.
- Concrete alternative: ship LangChain integration because there is already an integration module.
- Concrete alternative: list LlamaIndex as experimental or v0.6.
- Concrete mitigation: use adapter packages or optional modules.
- Suggested module layout:
- `neurosym.integrations.langchain`
- `neurosym.integrations.llamaindex`
- `neurosym.agent.tool_guard`
- Concrete mitigation: no hard dependency on either framework in core.

### Challenge: Eval Metrics Need Rule-Class Attribution That Current Results Do Not Directly Provide

- `GuardResult.violations` includes rule ids.
- `BenchmarkCase` includes category and label.
- There is no first-class rule class target.
- Per-rule-class precision and recall require mapping cases to expected rules or classes.
- A harmful prompt can be correctly blocked by a different rule than the one being evaluated.
- Aggregate blocked status can hide rule-specific failures.
- Example: `PromptInjectionRule` misses an attack but `BanTopicsRule` blocks it because it includes destructive command text.
- The overall result is true positive.
- The injection rule recall is still a false negative.
- Concrete alternative: extend benchmark cases.
- Suggested class:
- `EvalCase(input: Any, expected: ExpectedDecision, labels: set[str], expected_rule_classes: set[str], category: str, id: str)`
- Suggested `ExpectedDecision`:
- `should_block: bool`
- `acceptable_rule_ids: set[str] | None`
- `required_rule_ids: set[str] | None`
- `forbidden_rule_ids: set[str] | None`
- Concrete mitigation: preserve `BenchmarkCase` as a compatibility wrapper.
- Concrete mitigation: `EvalHarness` should report both decision metrics and attribution metrics.
- Concrete mitigation: CLI should make clear which metric failed.

### Challenge: Precision/Recall Requires Negative Sets Per Rule Class

- Recall is easy to define for attack cases.
- Precision requires negative cases.
- For safety filters, negative cases are not simply "safe content".
- They include benign dual-use content.
- They include defensive cybersecurity.
- They include chemistry education.
- They include self-harm support content.
- They include medical or policy discussions.
- They include harmless mentions of system prompts in documentation.
- They include file operations that are safe in context.
- Concrete alternative: every rule-class dataset must include:
- positive attack cases.
- benign near-neighbor cases.
- safe ordinary cases.
- ambiguous cases marked separately.
- Concrete mitigation: do not compute precision on ambiguous cases.
- Concrete mitigation: expose "challenge precision" for near-neighbor negatives.
- Concrete mitigation: require category-level false-positive ceilings.

### Challenge: CI Burden Can Grow Quickly

- Core tests must remain fast.
- Optional model tests can be slow.
- `sentence-transformers` downloads models.
- `transformers` downloads BART.
- OTel tests may need additional dependencies.
- LangChain tests may be version-sensitive.
- Registry tests may involve filesystem state.
- Eval harness tests can be large.
- Concrete alternative: split CI into tiers.
- Tier 1: core deterministic tests.
- Tier 2: optional dependency import and smoke tests.
- Tier 3: nightly model-backed evals.
- Tier 4: release-gate full baselines.
- Concrete mitigation: use tiny synthetic model stubs for unit tests.
- Concrete mitigation: support `NEUROSYM_EVAL_QUICK=1`.
- Concrete mitigation: store baseline JSON artifacts for deterministic rule classes.
- Concrete mitigation: do not require model-backed baselines on every pull request unless models are cached.

### Challenge: AuditLog Sink Semantics Need Backpressure And Failure Policy

- Audit sinks can fail.
- Files can be unwritable.
- Network sinks can time out.
- OTel exporters can drop spans.
- Blocking application requests on audit logging may hurt availability.
- Dropping audit events may hurt compliance.
- Concrete alternative: make failure policy explicit.
- Suggested API:
- `AuditLog(sinks: list[AuditSink], on_error: Literal["raise", "drop", "buffer"]="drop")`
- Suggested sink protocol:
- `emit(event: AuditEvent) -> None`
- `aemit(event: AuditEvent) -> Awaitable[None]`
- Suggested built-in sinks:
- `JsonlFileSink`
- `MemorySink`
- `OpenTelemetrySink`
- `StdoutSink`
- Concrete mitigation: default to non-blocking or explicit sync behavior.
- Concrete mitigation: include dropped-event counters.
- Concrete mitigation: avoid network sinks in core.

### Challenge: `PolicySnapshot.diff(other)` Needs Canonical Paths

- A structured diff is only useful if paths are stable.
- Rule order may or may not be semantically meaningful.
- Composite rule order often affects reporting but not decision logic.
- Lists of rules can be compared by index or by id.
- Comparing by index creates noisy diffs after reorder.
- Comparing by id breaks when duplicate ids exist.
- Duplicate rule ids are currently possible.
- Concrete alternative: snapshots should assign internal stable node ids.
- Suggested fields:
- `node_id`
- `rule_id`
- `type`
- `params`
- `children`
- Concrete mitigation: lint should warn on duplicate `rule_id` within a policy.
- Concrete mitigation: diff should compare by node path and rule id where possible.
- Concrete mitigation: diff output should include both machine-readable and human-readable forms.

### Challenge: Rule IDs Are Not Enforced As Globally Unique

- Rule ids are strings.
- Built-in defaults can repeat if multiple instances exist.
- `RegexRule` requires caller-provided id.
- `BanTopicsRule` default id repeats across instances.
- `PromptInjectionRule` default id repeats across instances.
- SAT linter handles semantic fingerprints internally.
- Runtime violations only show `rule_id`.
- Policy snapshots and eval attribution need better uniqueness.
- Concrete alternative: introduce optional `PolicyNode.id`.
- Rule `id` remains the rule's stable semantic identifier.
- Policy node id identifies the instance in a policy.
- Suggested snapshot node:
- `{"node_id": "input.prompt_injection", "rule_id": "adv.prompt_injection", "type": "PromptInjectionRule", ...}`
- Concrete mitigation: lint duplicate rule ids.
- Concrete mitigation: eval harness can attribute by node id when available.
- Concrete mitigation: `GuardResult` could include policy node id later, but do not break `Violation` now.

### Challenge: Loader Support For `SchemaRule` Needs File References

- JSON schemas can be large.
- Embedding schemas directly in YAML/TOML can be unwieldy.
- Schemas may be reused across policies.
- Relative paths need careful resolution.
- Concrete alternative:
- `schema: {...}` for inline.
- `schema_ref: "./schemas/invoice.json"` for file reference.
- The loader should resolve relative to the policy file, not process cwd.
- The snapshot should store schema content hash.
- The snapshot may embed schema content in canonical form or store a content-addressed reference.
- Concrete mitigation: reject remote schema refs in 0.5.
- Concrete mitigation: validate schema at load time.
- Concrete mitigation: include max schema size guardrails.

### Challenge: Optional Extras Need Naming Discipline

- Existing extras include `[cli]`, `[llm]`, `[forecaster]`, `[embeddings]`, `[z3]`, `[classifier]`, `[langchain]`, `[providers]`.
- The roadmap adds `[otel]`.
- It may need `[grounding]`.
- It may need `[policy-yaml]`.
- It may need `[eval]`.
- Extras can become confusing.
- Concrete alternative:
- Keep policy TOML/JSON loader in core if it uses standard library.
- Put YAML support under `[yaml]` or reuse `[cli]` only if PyYAML is already there.
- Put eval core in core if it only uses deterministic code.
- Put rich CLI reporting under `[cli]`.
- Put OTel under `[otel]`.
- Put NLI grounding under `[classifier]` or `[grounding]`, but not both unless one aliases the other.
- Concrete mitigation: document an extras matrix.
- Concrete mitigation: `neurosym[all]` should include new extras only if dependency weight is acceptable.
- Concrete mitigation: avoid adding torch transitively through `[all]` unless users already accept it through `[classifier]`.

## 3. ADDITIONS AND ALTERNATIVE SUB-VERSIONS

### Add A Policy AST Before The EDSL

- Proposed addition: `neurosym.policy.ast`.
- Rationale: an EDSL without an explicit AST makes compiler bugs hard to inspect.
- The AST should be serializable.
- The AST should preserve intent.
- The AST should compile to existing composite rules.
- The AST should be lintable before compilation.
- Suggested classes:
- `PolicyNode`
- `RuleNode`
- `AllNode`
- `AnyNode`
- `NotNode`
- `ImpliesNode`
- `DenyNode`
- `AllowNode`
- `PolicyDocument`
- Suggested compile function:
- `compile_policy(document: PolicyDocument) -> Rule`
- Suggested guard function:
- `compile_guard(document: PolicyDocument, **guard_kwargs) -> Guard`
- `PolicySnapshot` should snapshot the AST and normalized rule configs.
- The Python EDSL should produce this AST.
- The YAML/TOML loader should produce this AST.
- The registry should store this AST.
- Diff should compare this AST.
- SAT lint should consume the compiled composite or AST.
- This keeps all authoring paths aligned.

### Add Rule Serialization Contracts

- Proposed addition: `SerializableRule`.
- Suggested protocol:
- `class SerializableRule(Protocol):`
- `    id: str`
- `    def to_config(self) -> RuleConfig: ...`
- Suggested registry:
- `RuleConfigRegistry`
- Suggested function:
- `rule_from_config(config: RuleConfig, registry: RuleConfigRegistry | None = None) -> Rule`
- Built-in supported rule configs for 0.5:
- `RegexRule`
- `SchemaRule`
- `PromptInjectionRule`
- `BanTopicsRule`
- `SemanticInjectionRule`
- `IntentClassifierRule`
- `ContainsRule` if added.
- `ActionPolicyRule` factories only for named built-ins.
- The generic `ActionPolicyRule` with arbitrary `Callable` should not serialize.
- Named action policies can serialize:
- `destructive_needs_confirmation`
- `no_high_risk_without_intent`
- `max_steps`
- `no_path_outside_sandbox`
- Suggested config for action factories:
- `{"type": "action_policy", "factory": "max_steps", "params": {"limit": 5}}`
- This avoids trying to serialize lambdas.

### Add Baseline Artifacts As First-Class Objects

- Proposed addition: `EvalBaseline`.
- Suggested class:
- `EvalBaseline(policy_hash: str, dataset_hash: str, metrics: EvalMetrics, created_at: str, neurosym_version: str)`
- Rationale: the release gate needs durable evidence.
- `EvalResult` should represent one run.
- `EvalBaseline` should represent an approved reference.
- Suggested API:
- `EvalResult.compare_to(baseline: EvalBaseline) -> EvalDelta`
- Suggested CLI:
- `neurosym eval run policy.toml --dataset prompt_injection --output result.json`
- `neurosym eval compare result.json baseline.json`
- `neurosym eval bless result.json --output baseline.json`
- Gate conditions should compare against both absolute thresholds and previous baselines.
- This prevents "threshold drift" across sub-versions.

### Add Dataset Manifests

- Proposed addition: `DatasetManifest`.
- Suggested fields:
- `id`
- `version`
- `description`
- `case_count`
- `categories`
- `hash`
- `source`
- `license`
- `created_at`
- `expected_rule_classes`
- Rationale: eval datasets are part of the safety product.
- Built-in datasets need versioning.
- External datasets need validation.
- Dataset hashes should be included in eval results.
- Dataset manifests should live next to JSONL cases.
- The existing Python corpus can be exposed through a manifest shim.
- Long term, JSONL is better for contribution.

### Add A `DecisionPolicy` Or Explicitly Defer It

- Current `Guard` blocks on any violation.
- Some production users will need non-blocking warnings.
- The roadmap's observability and near-miss features increase this need.
- Proposed addition if scope allows:
- `DecisionPolicy`
- Suggested API:
- `DecisionPolicy(block_on_severity: Severity | None = None, block_rule_ids: set[str] | None = None, warn_rule_ids: set[str] | None = None)`
- But this touches core semantics.
- It may be too risky for v0.5.
- Alternative: explicitly defer non-blocking violations to v0.6.
- For v0.5, use `NearMiss` for non-blocking.
- The roadmap should state this boundary.
- Otherwise `Policy Authoring Layer` will attract warning/allowlist requirements immediately.

### Add `PolicyContext`

- Proposed addition: `PolicyContext`.
- Suggested class:
- `PolicyContext(policy_id: str | None = None, policy_version: str | None = None, policy_hash: str | None = None, source: str | None = None, trace_id: str | None = None)`
- Rationale: `Artifact.meta` can carry this today, but it is ad hoc.
- Audit logs need policy metadata.
- OTel spans need policy metadata.
- Eval results need policy metadata.
- Pipeline guards need context routing.
- A lightweight context object can normalize this.
- It should remain optional.
- It should be convertible to artifact metadata.
- It should not change `Rule.evaluate()`.

### Add `PolicyPack`

- Proposed addition: `PolicyPack`.
- Suggested class:
- `PolicyPack(name: str, version: str, snapshots: list[PolicySnapshot], datasets: list[DatasetManifest] = [])`
- Rationale: registry and eval baselines often move together.
- A policy without its eval dataset is hard to trust.
- A policy without its baseline is hard to promote.
- For v0.5, this can be a manifest file only.
- It does not need a remote package system.
- It can support examples like:
- `starter-prompt-injection`
- `starter-agent-actions`
- `starter-grounding`
- It can later support signed packs.

### Add `neurosym policy explain`

- Proposed CLI addition:
- `neurosym policy explain policy.toml`
- Rationale: policy authoring needs inspection.
- Output should show:
- normalized policy AST.
- compiled composite rule.
- rule types.
- rule ids.
- pack hashes.
- optional extras required.
- serialization warnings.
- eval datasets linked.
- This is more useful than lint alone.
- It helps users trust the compiler.
- It helps maintainers debug loader issues.
- It helps reviewers see what a YAML/TOML policy actually does.

### Add `neurosym eval matrix`

- Proposed CLI addition:
- `neurosym eval matrix policy.toml --datasets all`
- Rationale: release gates need category-level reporting.
- Output should include:
- rule class.
- dataset.
- category.
- precision.
- recall.
- F1.
- false positive rate.
- latency p50.
- latency p95.
- latency p99.
- case count.
- This command can be slower than `eval run`.
- It should be used in release CI.

## 4. RISKS AND OPEN QUESTIONS

### Technical Risks

- The policy EDSL may obscure the current violation-oriented rule model.
- Composite semantics may surprise users.
- `AnyOf` in particular is counterintuitive by name because it violates only when all children violate.
- `Not` is also counterintuitive because it violates when the inner rule passes.
- Policy compiler bugs can silently weaken safety.
- Loader bugs can invert match semantics.
- Snapshot canonicalization bugs can make different policies hash the same if not designed carefully.
- Snapshot canonicalization bugs can also make identical policies hash differently if ordering is unstable.
- Rule ids may collide.
- Rule instance identity is not currently first-class.
- Custom rules may not be serializable.
- Closure-backed action policies cannot be safely serialized.
- Function-decorated rules may not have enough config metadata for snapshots.
- SAT lint can overstate confidence because it abstracts rule firing as booleans.
- Model-backed rules can be nondeterministic across model versions.
- Model-backed rules can change behavior if model downloads resolve to different revisions.
- Evidence-grounding can fail on long evidence.
- Evidence-grounding can fail on multi-claim outputs.
- Evidence-grounding can produce false confidence.
- Tool-call safety can miss dangerous semantics hidden in nested arguments.
- Memory safety can miss poisoning encoded in metadata or embeddings.
- Audit logging can leak sensitive text.
- OTel attributes can exceed cardinality limits.
- Near-miss threshold suggestions can be gamed by adversarial traffic.
- Registry rollback can restore an insecure old policy if baselines are not checked.
- Policy diffs can miss semantic changes in external files if hashes are not included.
- CLI commands can behave differently depending on optional extras installed.
- Async pipeline guards can introduce race conditions if session state is shared incorrectly.
- Streaming safety can regress if policy wrappers buffer output incorrectly.

### Dependency Risks

- `[classifier]` depends on transformers and torch.
- Torch is heavy and platform-sensitive.
- BART MNLI is large.
- CPU NLI can be slow.
- `[embeddings]` depends on sentence-transformers and numpy.
- sentence-transformers may pull transitive dependencies that vary by platform.
- `[otel]` may introduce version compatibility issues with OTel SDK and API packages.
- `[cli]` depends on Typer and Rich.
- YAML support depends on PyYAML unless using TOML only.
- `z3-solver` wheels can be platform-sensitive.
- LangChain APIs change frequently.
- LlamaIndex APIs change frequently.
- Optional extras can interact poorly in `[all]`.
- Model downloads can fail in offline CI.
- Model revisions can change unless pinned.
- Dataset packaging can bloat wheels if not managed.
- Large built-in eval corpora can increase install size.
- Large evidence corpora should not ship in core unless compressed or optional.
- OpenTelemetry exporters should not be included by default.
- GPG/SSH signing integration can depend on external binaries.

### Scope Creep Risks

- Policy authoring can expand into a full policy language.
- YAML loading can expand into plugins and imports.
- Registry push/pull can expand into a remote service.
- Signing can expand into key management.
- Grounding can expand into generic hallucination detection.
- Eval harness can expand into a benchmark platform.
- Observability can expand into a dashboard.
- Near-miss aggregation can expand into auto-tuning.
- Agentic pipeline safety can expand into an agent framework.
- MemoryGuard can expand into vector database integrations.
- ToolCallGuard can expand into framework-specific adapters for every ecosystem.
- Trust levels can expand into an access-control system.
- Audit logs can expand into compliance product features.
- CLI can expand faster than Python API stability.
- Each of these expansions is tempting.
- Most should be resisted in 0.5.

### API Surface Risks

- `PolicySnapshot` fields chosen now may become hard to change.
- `rules_config` is too vague as a long-term public field.
- `pack_hashes` may need a structured shape, not a flat map.
- `created_at` needs timezone and format clarity.
- Snapshot `id` and `version` semantics need clarity.
- Version may refer to policy author version, not package version.
- Snapshot hash should not include mutable timestamps if used for content addressing.
- `GuardResult.to_otel_span()` may be too coupled.
- `GroundingRule(evidence=...)` may be too simple for real evidence identity.
- `AgentTrustLevel` enum values may be too hard to revise later.
- `PipelineGuard` may freeze an abstraction before enough adapter experience exists.
- `AuditLog` sink protocol must support sync and async without awkward duplication.
- `EvalHarness(policy, dataset)` needs to accept `Guard`, `Rule`, and `PolicySnapshot` carefully.
- `AttackLibrary` name may be too attack-focused if it also stores safe and near-neighbor cases.
- Consider `EvalDatasetLibrary` as the broader name.
- CLI command names should not imply remote features before they exist.

### Backward Compatibility Risks

- Existing users expect any violation to block.
- Policy authoring may imply severity-gated blocking.
- Do not change `GuardResult.blocked` semantics in v0.5 without a major warning.
- Existing rules may not implement serialization.
- Do not require all rules to implement `to_config()`.
- Existing `BenchmarkCase` users should not be broken.
- Keep `BenchmarkRunner` as compatibility layer.
- Existing LangChain callback behavior should remain.
- Adding tool hooks should not change LLM hooks unexpectedly.
- Existing optional extras names should not be removed.
- Existing pack names should remain stable.
- Existing centroid file names should remain stable.
- Existing violation metadata keys should not be removed.
- New audit redaction should not mutate `GuardResult.to_dict()` unexpectedly.
- New policy lint should not require Z3 for basic checks.

### CI Burden Risks

- Full eval baselines can be slow.
- Model-backed baselines can be very slow on CPU.
- Optional dependency matrices can become expensive.
- Release gates can become flaky if they depend on model downloads.
- Large eval output artifacts can clutter CI logs.
- Category-level metrics require enough cases per category.
- Tiny categories produce noisy pass/fail gates.
- Latency gates are noisy across CI runners.
- OTel tests may require special setup.
- Filesystem registry tests need isolation.
- Signing tests need key fixtures.
- LangChain integration tests may break on dependency updates.
- LlamaIndex tests would add another fast-moving dependency.
- Mitigation: tier CI.
- Mitigation: cache model artifacts in release workflows.
- Mitigation: use deterministic test doubles for unit tests.
- Mitigation: reserve full model eval for release candidates.
- Mitigation: pin optional dependency ranges conservatively.

### Community Adoption Risks

- Users may not understand the difference between regex, semantic, classifier, and grounding rules.
- Users may over-trust grounding results.
- Users may under-trust regex rules because they look simple.
- Users may want turnkey policies instead of building their own.
- Users may dislike optional extras complexity.
- Users may expect YAML policies to support custom Python rules.
- Users may expect remote registry features from push/pull names.
- Users may expect LlamaIndex support if advertised.
- Users may expect audit logs to be compliance-ready.
- Users may expect safety guarantees beyond eval coverage.
- Users may avoid the tool if model downloads are required for common examples.
- Users may avoid the tool if docs do not show lean-core workflows.
- Users may distrust baselines unless datasets are transparent.
- Users may contribute poor-quality adversarial datasets if metadata standards are weak.
- The project should be explicit about guarantees and limits.

## 5. RECOMMENDED FINAL STRUCTURE

### Recommended Version Table

| version | title | scope | gate condition |
|---|---|---|---|
| 0.5.0 | Evaluation Foundation And Release Gate | `EvalCase`, `EvalDataset`, `AttackLibrary`, `EvalHarness`, `EvalResult`, `EvalBaseline`, `neurosym eval run/compare`, migrated prompt-injection baseline, rule-class attribution model | Core deterministic eval passes; prompt-injection baseline recorded; CI can fail on recall and false-positive thresholds; no model downloads required for core gate |
| 0.5.1 | Policy Authoring And Snapshot | `PolicySnapshot`, policy AST, built-in `RuleConfig` serialization, Python EDSL, TOML loader, optional YAML loader, `neurosym policy lint`, `neurosym policy explain` | Loader and EDSL compile to identical AST for golden policies; policy authoring eval dataset passes; SAT lint works when `[z3]` installed and degrades without it |
| 0.5.2 | Evidence-Grounded Checks | `Evidence`, `GroundingRule`, grounding dataset, claim-level eval metrics, `[grounding]` or `[classifier]` integration, no-evidence constructor failure | Grounding corpus has FP/FN baselines; unsupported and contradicted labels are separately measured; no evidence raises `TypeError`; no core dependency weight increase |
| 0.5.3 | Observable Safety | `AuditEvent`, `AuditLog`, `AuditSink`, redaction policy, JSONL sink, OTel attributes/helper under `[otel]`, `NearMissAggregator`, `neurosym audit` | Audit events are redacted by default; OTel tests pass only with `[otel]`; near-miss aggregation has deterministic tests; no raw prompt/output logging unless explicitly enabled |
| 0.5.4 | Policy Registry And Diff | local `PolicyRegistry`, content-addressed snapshots, `PolicySnapshot.diff`, `PolicyDiff`, import/export/activate/rollback CLI, hash verification, reserved signature metadata | Registry round-trips snapshots by hash; diff golden tests pass; rollback refuses missing content; activation can require an eval baseline; remote push/pull and full signing are deferred |
| 0.5.5 | Agentic Guard Points | `TrustContext`, `AgentTrustLevel`, `ToolCall`, `ToolResult`, `ToolCallGuard`, `MemoryRecord`, `MemoryGuard`, minimal framework-neutral `PipelineGuard`, LangChain tool-call integration | Tool-call and memory-poisoning eval datasets pass; sync and async APIs tested; no framework dependency in core; LangChain integration remains optional |
| 0.5.6 optional | Pipeline Orchestration And Signatures | full `PipelineGuard` orchestration refinements, optional policy signing verification, possible LlamaIndex adapter | Only ship if 0.5.5 scope is too large; requires separate adapter baselines and key-fixture tests |

### Rationale For Reordering

- Evaluation must move first because it is the claimed release gate.
- The original plan puts policy authoring before the harness that validates policy semantics.
- That creates avoidable risk.
- Reordering makes every later sub-version measurable.
- Policy authoring moves to 0.5.1 because it needs the evaluation vocabulary.
- Grounding stays after policy authoring because snapshots should record evidence and model metadata.
- Observability stays after grounding because audit schemas should cover model-backed evidence checks.
- Registry stays after observability because production rollout needs audit and policy hashes.
- Agentic guard points stay last because they compose every earlier concept.
- The revised order preserves the proposal's intent.
- It changes the dependency direction so each version has the infrastructure it needs.

### Scope Boundaries For 0.5.0

- 0.5.0 should not add a broad policy language.
- 0.5.0 should not add new model-backed safety rules.
- 0.5.0 should not add a registry.
- 0.5.0 should focus on measurement.
- It should upgrade the existing benchmark foundation into a release-grade harness.
- It should retain `BenchmarkCase` compatibility.
- It should add richer `EvalCase` semantics.
- It should add attribution metrics.
- It should add baseline artifacts.
- It should add CLI support for CI.
- It should include built-in deterministic datasets.
- It should include a minimal migration path from `bench/corpus/prompt_injection.py`.
- Gate thresholds should be explicit and versioned.

### Scope Boundaries For 0.5.1

- 0.5.1 should support primitive built-in rules only by default.
- It should not serialize arbitrary custom Python rules by default.
- It should not execute imports from policy files without an explicit trust flag.
- It should not promise round-trip for all existing `Rule` implementations.
- It should define a policy AST.
- It should define canonical serialization.
- It should define stable hashes.
- It should include `PolicySnapshot`.
- It should include `PolicySnapshot.from_guard()` only if unsupported rules are reported honestly.
- It should include `compile_guard(snapshot)`.
- It should include `neurosym policy lint`.
- It should include `neurosym policy explain`.
- It should include golden tests proving EDSL and loader equivalence.

### Scope Boundaries For 0.5.2

- 0.5.2 should be evidence entailment only.
- It should not claim generic hallucination detection.
- It should not perform LLM-based web search.
- It should not fetch evidence.
- It should not decide truth without evidence.
- It should not silently accept empty evidence.
- It should not live in core dependencies.
- It should expose model and evidence hashes.
- It should expose claim-level metadata.
- It should include a grounding corpus.
- It should include false-positive and false-negative baselines.
- It should make unsupported and contradicted cases distinct.

### Scope Boundaries For 0.5.3

- 0.5.3 should make safety decisions observable without leaking raw content by default.
- It should not require OTel in core.
- It should not send audit events over the network by default.
- It should not auto-tune thresholds.
- It should not mutate policies from near-miss aggregation.
- It should define an audit event schema version.
- It should define redaction modes.
- It should include at least one durable local sink.
- It should include OTel attributes or helper functions under `[otel]`.
- It should include CLI inspection of JSONL audit logs.

### Scope Boundaries For 0.5.4

- 0.5.4 should be local-first.
- It should not require a remote service.
- It should not make push/pull imply hosted infrastructure.
- It should not block on full signing.
- It should implement content-addressed storage.
- It should implement structured diffs.
- It should implement rollback by immutable hash.
- It should support active policy pointers.
- It should optionally enforce eval baseline presence on activation.
- It should reserve signature metadata for later.

### Scope Boundaries For 0.5.5

- 0.5.5 should define guard points, not an agent runtime.
- It should not own the agent loop.
- It should not require LangChain in core.
- It should not promise LlamaIndex unless tests and ownership exist.
- It should represent tool calls and tool results explicitly.
- It should represent memory records explicitly.
- It should route policies by trust context.
- It should support sync and async checks.
- It should include structured eval datasets.
- It should integrate with existing `ActionPolicyRule`.
- It should integrate with existing `ConversationGuard` where appropriate.

### Recommended Gate Details

- Every sub-version must add or update at least one eval baseline.
- Every new rule class must ship positive, benign near-neighbor, and safe ordinary cases.
- Every new model-backed rule must report model id and model revision where possible.
- Every new model-backed rule must have CPU-only smoke tests.
- Every new policy compiler feature must have golden compile tests.
- Every CLI command must have failure-mode tests for missing optional extras.
- Every audit feature must have redaction tests.
- Every registry feature must have hash stability tests.
- Every agentic guard feature must have nested-argument tests.
- Release gates should include recall floors and false-positive ceilings.
- Release gates should include category-level minimums.
- Release gates should avoid full model downloads on ordinary pull requests.
- Release gates should run full baselines for release candidates.

### Recommended API Shapes

- `PolicySnapshot(id: str, version: str, document: PolicyDocument, created_at: str, neurosym_version: str, content_hash: str, pack_hashes: dict[str, str])`
- `PolicyDocument(schema_version: str, root: PolicyNode, metadata: dict[str, Any])`
- `RuleConfig(type: str, id: str, params: dict[str, Any], node_id: str | None = None)`
- `load_policy(path: str | Path, *, trusted_python: bool = False) -> PolicySnapshot`
- `compile_policy(snapshot: PolicySnapshot) -> Rule`
- `compile_guard(snapshot: PolicySnapshot, **guard_kwargs: Any) -> Guard`
- `EvalHarness(policy: Guard | Rule | PolicySnapshot, dataset: EvalDataset) -> EvalHarness`
- `EvalHarness.run() -> EvalResult`
- `EvalResult.to_json() -> str`
- `EvalResult.compare_to(baseline: EvalBaseline) -> EvalDelta`
- `Evidence(id: str, text: str, meta: dict[str, Any] | None = None)`
- `GroundingRule(evidence: str | Evidence | list[str | Evidence], *, threshold: float = 0.75, model: str = "facebook/bart-large-mnli")`
- `AuditEvent.from_guard_result(result: GuardResult, *, redaction: str = "summary", context: PolicyContext | None = None) -> AuditEvent`
- `AuditLog(sinks: list[AuditSink], redaction: str = "summary", on_error: str = "drop")`
- `PolicyRegistry(root: Path)`
- `PolicyRegistry.put(snapshot: PolicySnapshot) -> str`
- `PolicyRegistry.get(hash: str) -> PolicySnapshot`
- `PolicyRegistry.activate(hash: str, *, require_baseline: bool = False) -> None`
- `ToolCall(name: str, arguments: dict[str, Any], meta: dict[str, Any] | None = None)`
- `ToolCallGuard(pre_guard: Guard, post_guard: Guard | None = None)`
- `MemoryRecord(id: str, content: str, namespace: str | None = None, meta: dict[str, Any] | None = None)`
- `MemoryGuard(write_guard: Guard, read_guard: Guard)`
- `TrustContext(source: str, trust_level: AgentTrustLevel, channel: str, meta: dict[str, Any] | None = None)`

### Recommended Extras

- Keep core lean.
- Keep deterministic eval core dependency-free if possible.
- Keep CLI under `[cli]`.
- Keep Z3 under `[z3]`.
- Keep embeddings under `[embeddings]`.
- Keep intent classifier under `[classifier]`.
- Add `[otel]` for OpenTelemetry API/SDK helpers.
- Add `[grounding]` only if grounding dependencies diverge from `[classifier]`.
- If grounding uses the same transformers stack, make `[grounding]` an alias-like extra that includes the necessary classifier dependencies.
- Avoid adding PyYAML to core.
- Prefer TOML through the standard library on Python 3.11+.
- For Python 3.10, consider `tomli` only if needed.
- Keep LangChain under `[langchain]`.
- Do not add LlamaIndex extra until an adapter is implemented and tested.

### Recommended Documentation Commitments

- Document violation-oriented semantics prominently.
- Document that any `Violation` blocks under current `Guard` behavior.
- Document `hard_denied` separately.
- Document that grounding is evidence entailment, not truth.
- Document default audit redaction.
- Document optional extras for every rule and CLI path.
- Document registry local-first behavior.
- Document eval datasets and limitations.
- Document how to add custom datasets.
- Document how to author primitive policies without Python code.
- Document how to opt into trusted Python rule loading.
- Document what policy signatures do not yet cover if signing is deferred.

### Final Position

- The roadmap is strong in direction but should be reordered.
- Evaluation must come first.
- Policy authoring must be mediated by an explicit AST and serialization contract.
- Grounding must remain evidence-bound and model-optional.
- Observability must be redacted by default.
- Registry must be local and hash-addressed before it becomes signed or remote.
- Agentic safety must start with concrete guard points rather than a full orchestration framework.
- The revised plan keeps the lean core.
- The revised plan builds on v0.4 primitives.
- The revised plan makes the release gate real instead of aspirational.
- The revised plan reduces the risk of shipping policy features that cannot be measured.
