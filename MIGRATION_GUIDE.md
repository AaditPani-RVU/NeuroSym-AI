# Replace NeMo Guardrails with neurosym-ai in 15 Minutes

This guide maps the most common NeMo Guardrails patterns to their neurosym-ai equivalents.

---

## Install

```bash
# Before (NeMo — heavy, CUDA recommended)
pip install nemo-guardrails          # ~83 MB core + CUDA stack

# After (neurosym-ai — lean, CPU-only core)
pip install neurosym-ai              # 0.4 MB core
pip install 'neurosym-ai[classifier]'  # + zero-shot NLI (optional)
pip install 'neurosym-ai[langchain]'   # + LangChain adapter (optional)
```

---

## Core concept map

| NeMo Guardrails | neurosym-ai equivalent |
|---|---|
| `RailsConfig` (YAML/Colang) | `Guard(rules=[...])` |
| `LLMRails` | `Guard(llm=..., rules=[...])` |
| Input rail | `Guard.apply_text(user_input)` |
| Output rail | `Guard.apply_text(llm_output)` |
| Dialog rail (multi-turn) | `ConversationGuard` + `session.check()` |
| `colang_content` topic block | `BanTopicsRule(topics=[...])` |
| Custom Colang flow | `@rule(id="...")` decorator or `BaseRule` subclass |
| Prompt injection rail | `PromptInjectionRule()` |
| Sensitive data rail | `RegexRule(...)` or `SecretLeakageRule()` |
| Jailbreak check (LLM) | `IntentClassifierRule(bad_intents=[...])` |
| LangChain integration | `NeurosymCallbackHandler` |

---

## Migration examples

### 1 — Input guardrails

**NeMo (colang)**
```colang
define user ask about violence
  "How do I make a bomb?"
  "tell me how to hurt someone"

define flow
  user ask about violence
  bot refuse to respond
```

**neurosym-ai**
```python
from neurosym import Guard, BanTopicsRule, PromptInjectionRule

guard = Guard(rules=[
    BanTopicsRule(topics=["violence", "weapons", "self-harm"]),
    PromptInjectionRule(),
])

result = guard.apply_text(user_input)
if result.blocked:
    reply = "I can't help with that."
```

---

### 2 — Output guardrails

**NeMo (config.yml)**
```yaml
rails:
  output:
    flows:
      - self check output
```

**neurosym-ai**
```python
from neurosym import Guard, SecretLeakageRule, BanTopicsRule

output_guard = Guard(rules=[
    SecretLeakageRule(),
    BanTopicsRule(topics=["violence"]),
])

result = output_guard.apply_text(llm_response)
if result.blocked:
    llm_response = "[Response redacted by safety filter]"
```

---

### 3 — Multi-turn conversation rails

NeMo's biggest differentiator is stateful dialog via Colang. neurosym-ai matches this with `ConversationGuard`.

**NeMo (colang)**
```colang
define user ask jailbreak
  "pretend you are ..."
  "let's do a roleplay where ..."

define flow
  user ask jailbreak
  bot refuse and explain
```

**neurosym-ai**
```python
from neurosym import ConversationGuard, BanTopicsRule, PromptInjectionRule

cg = ConversationGuard(
    rules=[
        BanTopicsRule(topics=["weapons", "illegal activity"]),
        PromptInjectionRule(),
    ],
    window=10,  # look back up to 10 turns
)

# Per-request: restore from serialised state if you're stateless
with cg.session(restore_state=session_store.get(user_id)) as s:
    result = s.check("user", user_message)
    if result.blocked:
        response = "I can't continue this conversation."
    else:
        response = llm.generate(user_message)
        s.add("assistant", response)

    # Persist state across HTTP requests
    session_store[user_id] = s.state()
```

---

### 4 — LangChain integration

**NeMo**
```python
from nemoguardrails import RailsConfig, LLMRails
from nemoguardrails.integrations.langchain.runnable_rails import RunnableRails

config = RailsConfig.from_path("./config")
rails = RunnableRails(config)
chain = rails | your_chain
```

**neurosym-ai**
```python
from langchain_openai import ChatOpenAI
from neurosym import Guard, BanTopicsRule, PromptInjectionRule
from neurosym.integrations.langchain import NeurosymCallbackHandler

handler = NeurosymCallbackHandler(
    input_guard=Guard(rules=[PromptInjectionRule()]),
    output_guard=Guard(rules=[BanTopicsRule(topics=["violence"])]),
)
llm = ChatOpenAI(callbacks=[handler])
# All calls through llm are now guarded automatically
```

---

### 5 — Sensitive-data / PII rails

**NeMo (colang)**
```colang
define flow sensitive data check
  $is_sensitive = execute check_sensitive_data
  if $is_sensitive
    bot inform cannot share sensitive data
```

**neurosym-ai**
```python
from neurosym import Guard
from neurosym.rules.regex_rule import RegexRule

pii_guard = Guard(rules=[
    RegexRule("no-email",  r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", must_not_match=True),
    RegexRule("no-ssn",    r"\b\d{3}-\d{2}-\d{4}\b", must_not_match=True),
    RegexRule("no-cc",     r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14})\b", must_not_match=True),
])

result = pii_guard.apply_text(text)
```

---

### 6 — Jailbreak / novel phrasing (classifier rail)

NeMo uses a fine-tuned LLM to catch jailbreaks that pattern-matching misses.
neurosym-ai provides the same capability without a GPU via `IntentClassifierRule`.

```python
from neurosym import Guard, IntentClassifierRule, PromptInjectionRule

guard = Guard(rules=[
    PromptInjectionRule(),          # fast regex-based check first
    IntentClassifierRule(           # NLI fallback for novel phrasing
        bad_intents=[
            "jailbreak attempt",
            "roleplay to bypass safety",
            "weapons synthesis",
            "illegal activity instructions",
        ],
        threshold=0.75,
    ),
])
```

Install once (CPU, ~400 MB model download):
```bash
pip install 'neurosym-ai[classifier]'
```

---

### 7 — Structured output guardrails (JSON schemas)

NeMo has no built-in JSON schema rail. neurosym-ai ships one out of the box.

```python
from neurosym import Guard
from neurosym.rules.schema_rule import SchemaRule

schema = {
    "type": "object",
    "required": ["name", "score"],
    "properties": {
        "name": {"type": "string"},
        "score": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

guard = Guard(rules=[SchemaRule("output.schema", schema)])
result = guard.apply_json(llm_json_output)
```

---

## Configuration comparison

**NeMo** uses a directory with YAML + Colang files:
```
config/
  config.yml
  rails.co      ← Colang DSL
  prompts.yml
```

**neurosym-ai** is pure Python — no config files required:
```python
from neurosym import Guard, BanTopicsRule, PromptInjectionRule

guard = Guard(
    rules=[BanTopicsRule(), PromptInjectionRule()],
    deny_above="high",      # hard-deny anything rated high or above
)
```

---

## Feature gap (honest comparison)

> These systems operate at different abstraction levels. neurosym-ai is a rule engine;
> NeMo Guardrails is a conversational orchestration framework. Some cells are ✅ on both
> sides but mean different things — see the notes column.

| Feature | neurosym-ai 0.4.0 | NeMo Guardrails 0.9 | Notes |
|---|---|---|---|
| Sub-ms deterministic rule eval | ✅ | ✅ (for non-LLM rails) | NeMo also has regex/Python rails |
| LLM-in-loop semantic rails | ❌ | ✅ | Core NeMo capability |
| GPU required | No | No | GPU useful only for self-hosted local models |
| Multi-turn conversation guard | ✅ | ✅ | Different mechanisms |
| LangChain integration | ✅ | ✅ | |
| Zero-shot intent classifier | ✅ (CPU, ~500 MB) | ✅ (via LLM) | NeMo uses LLM; neurosym-ai uses local NLI |
| Colang DSL | ❌ (v0.5 roadmap) | ✅ | |
| Hallucination / factual grounding | ❌ (v0.5 roadmap) | ✅ | |
| Dialog flow branching | ❌ | ✅ | |
| No mandatory cloud dependency | ✅ | ✅ (with local model) | Both can run fully offline |

If you need Colang's dialog flow control or NeMo's hallucination rails, neurosym-ai is not a substitute.
If you need fast, auditable, offline-capable rule evaluation with multi-turn awareness, neurosym-ai is the lighter fit.

---

## Quick checklist

- [ ] Replace `pip install nemo-guardrails` with `pip install neurosym-ai`
- [ ] Convert input Colang flows to `Guard(rules=[BanTopicsRule(...), PromptInjectionRule()])`
- [ ] Convert output Colang flows to `Guard(rules=[SecretLeakageRule(), ...])`
- [ ] Replace dialog rails with `ConversationGuard` + `session.check()`
- [ ] Replace LangChain `RunnableRails` with `NeurosymCallbackHandler`
- [ ] Add `IntentClassifierRule` for jailbreak/novel phrasing coverage (optional)
- [ ] Delete the `config/` directory
