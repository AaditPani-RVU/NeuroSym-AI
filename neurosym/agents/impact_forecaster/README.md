# Change-Impact Forecasting Agent

## Overview

The Change-Impact Forecasting module predicts the architectural and system-wide impact of a GitHub Pull Request before it is merged. 

It combines **Symbolic AI** (deterministic rules, CODEOWNERS, Architecture Maps) and **Neuro AI** (LLM-based reasoning) to provide a comprehensive risk forecast.

## Neuro-Symbolic Philosophy

1.  **Symbolic Rules (The Guard)**: 
    *   Serve as the authoritative source of truth.
    *   Enforce safety policies (e.g., "Touching `auth/` is always HIGH RISK").
    *   **Always override** the agent in case of conflict.
    
2.  **LLM Agent (The Scout)**:
    *   Analyzes the diff summary to hypothesize potential impacts that aren't captured by strict file-path rules.
    *   Proposes "hypotheses" but does not set the final Risk rating.

## Advanced Features (New!)

### 1. Evidence Tracing
The forecaster now reports exactly **why** a rule triggered.
- `evidence`: List of specific files or diff snippets that caused the alert.

### 2. CODEOWNERS Integration
Standard `CODEOWNERS` (or `.github/CODEOWNERS`) files are parsed to automatically determine `owners_to_notify`.
- Follows GitHub's "last match wins" logic.
- No external git dependencies required.

### 3. Architecture Map Support
Optionally define an `arch_map.yaml` in your repo root (or pass via config) to model system dependencies.

**`arch_map.yaml` example:**
```yaml
components:
  - name: "auth_service"
    paths: ["auth/.*", "lib/security/.*"]
    depends_on: []
    owners: ["@security-team"]
    
  - name: "billing_worker"
    paths: ["workers/billing.*"]
    depends_on: ["auth_service"] # Depends on auth
    owners: ["@billing-team"]
```
If you modify `auth_service`, the forecaster builds an **Impact Chain**: `auth_service -> billing_worker`.

## Usage

### Programmatic

```python
import os
from neurosym.agents.impact_forecaster import GitHubAdapter
from neurosym.llm import OpenAI_LLM 

# Initialize (repo_root defaults to current dir)
adapter = GitHubAdapter(llm=OpenAI_LLM(), repo_root=".")

# Forecast
forecast = adapter.generate_forecast("https://github.com/myorg/myrepo/pull/123")

print(f"Risk: {forecast.risk}")
print(f"Owners: {forecast.owners_to_notify}")

# Inspect Evidence
for item in forecast.evidence:
    print(f"Rule {item.rule_id} triggered by {item.evidence_type}: {item.value}")

# Inspect Chains
for edge in forecast.impact_chain:
    print(f"Impact flows from {edge.src} to {edge.dst}")
```

### Running the Demo

A full demonstration using `dummy-repo-1` is available in `neurosym/examples/run_demo.py`.

1. Ensure you have the dummy repo set up (or let the script use the provided one).
2. Run:
   ```bash
   python neurosym/examples/run_demo.py
   ```
   This simulates a PR change to `auth/` and `api/` files, showing how:
   - Rules trigger (Security, API)
   - Owners are resolved (`@security-team` from CODEOWNERS)
   - Impact propagates (`auth_service` changes -> `payment_service` impacted)

## Example Output (JSON)

```json
{
  "risk": "HIGH",
  "impacts": [
    {
      "area": "Security/Auth Layer",
      "reason": "Symbolic detection via rule security.auth",
      "confidence": 1.0
    }
  ],
  "required_actions": ["Security Review"],
  "owners_to_notify": ["@security-team"],
  "evidence": [
    {
      "rule_id": "security.auth",
      "evidence_type": "path",
      "value": "auth/login_handler.py"
    }
  ],
  "impact_chain": [
    {
      "src": "auth_service",
      "dst": "billing_worker",
      "reason": "billing_worker depends on auth_service"
    }
  ]
}
```
