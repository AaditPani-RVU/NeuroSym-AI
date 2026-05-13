# neurosym-ai vs NeMo Guardrails — Performance Notes

> **Important context before reading these numbers.**
>
> neurosym-ai and NeMo Guardrails operate at different abstraction levels.
> neurosym-ai is a symbolic rule engine (regex, keyword filters, schema validation, NLI classification).
> NeMo Guardrails is a conversational orchestration framework built around LLM-driven dialog flows, retrieval rails, and Colang policy authoring.
>
> The numbers below are real, but the gap is *expected* — not a product win. It is the natural cost difference between deterministic matching and LLM-in-loop reasoning. Read the "what this means in practice" section before drawing conclusions.

---

## neurosym-ai measured numbers

Measured on Python 3.13.3 / Windows 11, no GPU. All numbers are reproducible (see below).

| Metric | Value | Notes |
|---|---|---|
| Cold start (import → first call) | **0.65 ms** | Core package only, no optional extras |
| Rule eval p50 (3-rule pipeline) | **20 µs** | RegexRule + 2× DenyIfContains, 64-char input |
| Rule eval p99 (3-rule pipeline) | **43 µs** | Same pipeline |
| ConversationGuard p50 | **31 µs** | `check()` with 5-turn history, window=10 |
| Core install size | **0.4 MB** | `neurosym-ai` wheel only |
| Core install size with classifier | **~500 MB** | Adding `neurosym-ai[classifier]` pulls PyTorch + bart-large-mnli |

---

## NeMo Guardrails reference numbers

These are from published sources. NeMo's actual performance varies significantly depending on which rails are active, whether an LLM is in the loop, and how the service is deployed.

| Metric | Value | Source / caveat |
|---|---|---|
| Cold start (LLM-backed rails) | **~15–25 s** | Community reports when loading transformers locally — [issue #467](https://github.com/NVIDIA/NeMo-Guardrails/issues/467). With pre-warmed API-backed deployments this is much lower. |
| p50 latency (Colang + OpenAI GPT-3.5) | **~120 ms** | [arXiv 2310.10512](https://arxiv.org/abs/2310.10512) Table 2. Applies specifically to LLM-in-loop Colang rails. |
| p99 latency (same config) | **~450 ms** | Same source. |
| Install size (no CUDA) | **~83 MB** | `pip download nemo-guardrails` without GPU wheels |

**What NeMo's numbers reflect:** the cost of LLM-mediated rail evaluation — parsing user intent, routing through dialog flows, and generating responses. NeMo also supports deterministic rails (regex, Python actions) that run much faster. The latency figures above apply only to the LLM-backed flow-control path.

---

## What this means in practice

**The latency gap is real but expected.**
A regex match takes microseconds because it does lexical matching.
An LLM call takes milliseconds because it does semantic reasoning and generation.
Comparing them on latency is like comparing `grep` to a full-text semantic search engine — the faster tool is doing a fundamentally different (and narrower) job.

**"6,000× faster p50" is mathematically correct, practically narrow.**
That multiplier is meaningful for one specific scenario: you have a keyword/regex guard that fully covers your policy and you need it in a hot path. It is not a general claim about safety coverage.

**neurosym-ai does not replace NeMo's LLM-in-loop capabilities.**
Colang rails do things a rule engine cannot: route dialog, enforce conversation goals, handle ambiguous intent with language understanding. If you need those, neurosym-ai does not substitute for NeMo.

**The install size comparison is selective.**
The 0.4 MB figure is the core package without the optional classifier. Adding `neurosym-ai[classifier]` pulls in ~500 MB of PyTorch and model weights — the gap shrinks substantially for semantic-classification workloads.

**GPU / LLM requirements.**
NeMo Guardrails does not require a GPU — it works fine with OpenAI, Anthropic, or any API-backed LLM. GPU acceleration is relevant only if you self-host a large local model. The claim "NeMo requires GPU" in an earlier version of this document was inaccurate.

---

## Where neurosym-ai is the right fit

- You need deterministic, auditable rules with no LLM dependency in the evaluation path
- Rule-based filtering covers your policy (PII, banned topics, injection patterns, schema validation)
- You need sub-millisecond evaluation in a hot path (inline request guard, rate-limited API, etc.)
- You want zero mandatory cloud dependencies — neurosym-ai core runs fully offline
- You want a lightweight addition to an existing LangChain chain without a second LLM call per message

## Where NeMo Guardrails is the right fit

- You need Colang DSL — declarative, branching dialog policies
- Your safety policy requires language understanding to evaluate (ambiguous intent, paraphrase detection)
- You need conversational flow control (topic steering, topic blocking mid-conversation)
- You need NeMo's built-in hallucination or factual grounding rails

---

## Reproducing the neurosym-ai numbers

```bash
pip install neurosym-ai
python -m neurosym.bench.nemo_comparison

# Machine-readable JSON:
python -m neurosym.bench.nemo_comparison --json
```

The benchmark measures:
- **Cold start**: time from first `import` to first `apply_text()` call
- **Latency**: 1000-run timer, 3-rule pipeline (RegexRule + 2× DenyIfContains), 64-char input
- **ConversationGuard**: 500-run timer, `check()` with 5-turn history in window
- **Install size**: on-disk sum of all files in the `neurosym-ai` distribution (core only)
