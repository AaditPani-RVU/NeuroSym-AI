# NeuroSym-AI

> **Neuro-symbolic guardrails for arbitrary information**
>
> Validate, sanitize, and enforce policies on text, JSON, and LLM outputs using
> symbolic rules with optional language-model-based repair loops.

---

## Overview

NeuroSym is an **information-first guardrail engine** designed to enforce
explicit, auditable constraints on unstructured and semi-structured data.

Unlike LLM-specific guardrail tools, NeuroSym operates **independently of model providers**
and treats language models as _optional adapters_, not core dependencies.

It is suitable for:

- AI agents and tool pipelines
- Structured LLM extraction
- Compliance-sensitive systems
- Research on neuro-symbolic AI and AI safety

---

## Key Capabilities

Input (Text / JSON / Tool Output)
↓
Deterministic Repairs (Offline)
↓
Symbolic Rule Evaluation
↓
Optional LLM Repair Loop
↓
Validated, Audited Output

### Highlights

- Provider-agnostic (no lock-in)
- Deterministic by default (no keys required)
- Symbolic core (rules, schemas, constraints)
- Optional neuro repair loops
- Full traceability and audit logs

---

## Design Philosophy

> **Principle 1 — Information First**
>
> NeuroSym guards _information_, not prompts.
> Inputs may come from humans, tools, databases, or models.

> **Principle 2 — Determinism by Default**
>
> Validation and repair should work offline.
> LLMs are used only when explicitly configured.

> **Principle 3 — Symbolic Core**
>
> Rules are explicit, testable, inspectable, and explainable.

> **Principle 4 — Auditability**
>
> Every decision produces a structured trace suitable for compliance and debugging.

---

## Installation

```bash
pip install neurosym-ai
pip install neurosym-ai[z3]         # SMT / formal constraints
pip install neurosym-ai[providers]  # Gemini / OpenAI adapters
```
