"""SAT/SMT-backed policy linter using Z3.

Translates composite rule algebra (AllOf, AnyOf, Not, Implies) into Z3
boolean formulas and checks for unsatisfiable, tautological, and subsumed
policies.

Requires: pip install z3-solver
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, fields, is_dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from neurosym.rules.base import Rule

try:
    import z3

    HAS_Z3 = True
except ImportError:
    HAS_Z3 = False


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class LintIssue:
    """A logical inconsistency detected in a composite policy."""

    kind: str  # "unsatisfiable" | "tautology" | "subsumed"
    message: str
    rules_involved: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        rules_str = ", ".join(self.rules_involved) if self.rules_involved else "n/a"
        return f"[{self.kind.upper()}] {self.message}  (rules: {rules_str})"


# ---------------------------------------------------------------------------
# Rule → Z3 formula translation
# ---------------------------------------------------------------------------

# Semantics:
#   fires(rule) = True  ↔  rule produces ≥1 violation for some input
#
# Composite mappings (matching the neurosym composite.py implementation):
#   AllOf   fires = OR  of children  (any child firing causes AllOf to fire)
#   AnyOf   fires = AND of children  (all children must fire)
#   Not(r)  fires = NOT fires(r)
#   Implies(cond, cons) fires = NOT fires(cond) AND fires(cons)
#   Atomic rule → Z3 Bool keyed by semantic rule configuration


_IDENTITY_FIELD_NAMES = {"id", "name", "label", "display_name"}


def _is_identity_field(field_name: str) -> bool:
    return field_name.lstrip("_") in _IDENTITY_FIELD_NAMES


def _semantic_config(rule: Any) -> dict[str, Any]:
    """Return inspectable rule attributes with display/identity fields removed."""
    config: dict[str, Any] = {}

    try:
        config.update(vars(rule))
    except TypeError:
        pass

    if is_dataclass(rule):
        for dataclass_field in fields(rule):
            name = dataclass_field.name
            if hasattr(rule, name):
                config.setdefault(name, getattr(rule, name))

    for cls in type(rule).__mro__:
        slots = getattr(cls, "__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for name in slots:
            if name in {"__dict__", "__weakref__"} or not hasattr(rule, name):
                continue
            config.setdefault(name, getattr(rule, name))

    return {key: value for key, value in config.items() if not _is_identity_field(key)}


def _atomic_fingerprint(rule: Any) -> str:
    """Semantic key for an atomic rule: explicit key or stable config hash.

    Rules with the same class and configuration share a fingerprint so that
    logical contradictions between equivalent separate instances are detected.
    Display/identity fields are excluded so labels do not affect Z3 identity.
    """
    explicit_key = getattr(rule, "__sat_key__", None)
    if explicit_key is not None:
        raw = f"sat_key::{explicit_key}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    cls = f"{type(rule).__module__}.{type(rule).__qualname__}"
    config = _semantic_config(rule)
    config = {key: value for key, value in config.items() if not callable(value)}
    cfg = json.dumps(config, sort_keys=True, default=repr)
    raw = f"{cls}::{cfg}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _collect_atomic_rule_ids(rule: Rule) -> list[str]:
    """Collect atomic rule ids for reporting without affecting solver identity."""
    from neurosym.rules.composite import AllOf, AnyOf, Implies, Not

    ids: list[str] = []

    def visit(current: Rule) -> None:
        if isinstance(current, (AllOf, AnyOf)):
            for child in current._rules:
                visit(child)
            return
        if isinstance(current, Not):
            visit(current._rule)
            return
        if isinstance(current, Implies):
            visit(current._condition)
            visit(current._consequence)
            return

        rule_id = getattr(current, "id", str(id(current)))
        if rule_id not in ids:
            ids.append(rule_id)

    visit(rule)
    return ids


def _rule_fires(rule: Rule, variables: dict[str, Any]) -> Any:
    """Return a Z3 expression for 'this rule fires (produces a violation)'."""
    from neurosym.rules.composite import AllOf, AnyOf, Implies, Not

    if isinstance(rule, AllOf):
        children = [_rule_fires(r, variables) for r in rule._rules]
        return z3.Or(*children)
    if isinstance(rule, AnyOf):
        children = [_rule_fires(r, variables) for r in rule._rules]
        return z3.And(*children)
    if isinstance(rule, Not):
        return z3.Not(_rule_fires(rule._rule, variables))
    if isinstance(rule, Implies):
        cond = _rule_fires(rule._condition, variables)
        cons = _rule_fires(rule._consequence, variables)
        return z3.And(z3.Not(cond), cons)

    # Atomic rule — one boolean variable per semantic fingerprint.
    # Rules with the same class and configuration share a variable so that
    # contradictions between equivalent separate instances are detected.
    # Rules with the same rule.id but different configurations get independent
    # variables so they are not falsely reported as subsumed.
    rule_id = getattr(rule, "id", str(id(rule)))
    fp = _atomic_fingerprint(rule)
    if fp not in variables:
        existing_names = {v.decl().name() for v in variables.values()}
        z3_name = rule_id
        counter = 0
        while z3_name in existing_names:
            counter += 1
            z3_name = f"{rule_id}#{counter}"
        variables[fp] = z3.Bool(z3_name)
    return variables[fp]


# ---------------------------------------------------------------------------
# Linting checks
# ---------------------------------------------------------------------------


def _is_tautology(expr: Any) -> bool:
    """Return True if expr is always True (unsatisfiable negation)."""
    s = z3.Solver()
    s.add(z3.Not(expr))
    return s.check() == z3.unsat


def _is_unsatisfiable(expr: Any) -> bool:
    """Return True if expr is always False (no satisfying assignment)."""
    s = z3.Solver()
    s.add(expr)
    return s.check() == z3.unsat


def _check_subsumption(
    rules: list[Any], variables: dict[str, Any], issues: list[LintIssue]
) -> None:
    """Check for subsumed rules inside an AllOf."""
    n = len(rules)
    for i in range(n):
        for j in range(i + 1, n):
            ri_fires = _rule_fires(rules[i], variables)
            rj_fires = _rule_fires(rules[j], variables)
            ri_id = getattr(rules[i], "id", f"rule[{i}]")
            rj_id = getattr(rules[j], "id", f"rule[{j}]")

            # Check equivalence: ri ↔ rj  (both are redundant / one can be removed)
            if _is_tautology(ri_fires == rj_fires):
                issues.append(
                    LintIssue(
                        kind="subsumed",
                        message=(
                            f"Rules '{ri_id}' and '{rj_id}' are logically equivalent — "
                            "one of them is redundant in this AllOf."
                        ),
                        rules_involved=[ri_id, rj_id],
                    )
                )
                continue

            # Check ri → rj: ri fires ⇒ rj fires → ri is redundant in AllOf
            if _is_tautology(z3.Implies(ri_fires, rj_fires)):
                issues.append(
                    LintIssue(
                        kind="subsumed",
                        message=(
                            f"Rule '{ri_id}' is subsumed by '{rj_id}' in AllOf — "
                            f"'{ri_id}' adds no blocking case not already covered by '{rj_id}'."
                        ),
                        rules_involved=[ri_id, rj_id],
                    )
                )
                continue

            # Check rj → ri: rj fires ⇒ ri fires → rj is redundant
            if _is_tautology(z3.Implies(rj_fires, ri_fires)):
                issues.append(
                    LintIssue(
                        kind="subsumed",
                        message=(
                            f"Rule '{rj_id}' is subsumed by '{ri_id}' in AllOf — "
                            f"'{rj_id}' adds no blocking case not already covered by '{ri_id}'."
                        ),
                        rules_involved=[ri_id, rj_id],
                    )
                )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def lint(policy: Rule) -> list[LintIssue]:
    """
    Analyse a composite policy for logical issues using Z3 SAT/SMT.

    Requires z3-solver (``pip install z3-solver``).

    Detects:

    - **unsatisfiable** — policy always fires; nothing can ever pass it.
    - **tautology** — policy never fires; it is a no-op guardrail.
    - **subsumed** — a rule inside an AllOf is made redundant by another child.

    Example::

        from neurosym.rules.composite import AllOf, Not
        from neurosym.rules.adversarial import PromptInjectionRule
        from neurosym.policy import lint

        issues = lint(AllOf([PromptInjectionRule(), Not(PromptInjectionRule())]))
        # → [LintIssue(kind='unsatisfiable', ...)]

    Returns:
        List of :class:`LintIssue` objects. Empty list means no issues found.
    """
    if not HAS_Z3:
        raise ImportError(
            "z3-solver is required for policy linting. Install it with: pip install z3-solver"
        )

    variables: dict[str, Any] = {}
    fires_expr = _rule_fires(policy, variables)
    issues: list[LintIssue] = []
    all_ids = _collect_atomic_rule_ids(policy)

    # ── Unsatisfiable: policy fires for ALL inputs (nothing can pass) ──
    if _is_unsatisfiable(z3.Not(fires_expr)):
        issues.append(
            LintIssue(
                kind="unsatisfiable",
                message="Policy always blocks — no input can ever pass it.",
                rules_involved=all_ids,
            )
        )

    # ── Tautology: policy never fires (everything passes) ──
    if _is_unsatisfiable(fires_expr):
        issues.append(
            LintIssue(
                kind="tautology",
                message="Policy never blocks — always passes every input (guardrail is a no-op).",
                rules_involved=all_ids,
            )
        )

    # ── Subsumption within AllOf ──
    from neurosym.rules.composite import AllOf

    if isinstance(policy, AllOf):
        _check_subsumption(policy._rules, variables, issues)

    return issues
