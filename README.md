# NeuroSym-AI

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Type%20Checked](https://img.shields.io/badge/mypy-strict-success)
![Linting](https://img.shields.io/badge/lint-ruff-blueviolet)
![Formatting](https://img.shields.io/badge/format-black-black)
![Status](https://img.shields.io/badge/status-stable-brightgreen)

> **Neuro-symbolic guardrails for arbitrary information**
>
> Validate, sanitize, and enforce policies on text, JSON, and LLM outputs using
> symbolic rules with optional language-model-based repair loops.

---

## Overview

**NeuroSym** is an **information-first guardrail engine** designed to enforce
explicit, auditable constraints on unstructured and semi-structured data.

Unlike LLM-specific guardrail tools, NeuroSym operates **independently of model providers**
and treats language models as _optional adapters_, not core dependencies.

It is suitable for:

- AI agents and tool pipelines
- Structured LLM extraction
- Compliance-sensitive systems
- Research in neuro-symbolic AI and AI safety

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

- Provider-agnostic (no model lock-in)
- Deterministic by default (no API keys required)
- Symbolic core (rules, schemas, constraints)
- Optional neuro-symbolic repair loops
- Full traceability with structured audit logs

---

## Design Philosophy

### Principle 1 — Information First

NeuroSym guards **information**, not prompts.  
Inputs may originate from humans, tools, databases, or language models.

### Principle 2 — Determinism by Default

Validation and repair operate fully offline.  
Language models are invoked only when explicitly configured.

### Principle 3 — Symbolic Core

Rules are explicit, testable, inspectable, and explainable.

### Principle 4 — Auditability

Every decision produces a structured execution trace suitable for
compliance, debugging, and research.

---

## Installation

```bash
pip install neurosym-ai
pip install neurosym-ai[z3]          # SMT / formal constraints
pip install neurosym-ai[providers]   # Gemini / OpenAI adapters
```
