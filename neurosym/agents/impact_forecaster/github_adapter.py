import json
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any

import yaml

from neurosym.agents.impact_forecaster import arch_map, codeowners

# Import from our new module
from neurosym.agents.impact_forecaster.agent import ImpactAgent
from neurosym.agents.impact_forecaster.impact_models import (
    EvidenceItem,
    ImpactForecast,
    ImpactHypothesis,
)
from neurosym.engine.guard import Artifact, Guard, Violation
from neurosym.llm import LLM
from neurosym.rules.base import Rule


@dataclass
class PrContext:
    diff_text: str
    changed_files: list[str]


@dataclass
class ImpactRule(Rule):
    """
    Symbolic rule wrapper for impact forecasting.
    Implements the Rule protocol for NeuroSym's Guard.
    """

    id: str
    condition: str  # The 'when' clause
    impact_data: dict[str, Any]  # The 'then' clause

    def evaluate(self, output: Any) -> list[Violation]:
        # 'output' is expected to be PrContext via artifact
        if not isinstance(output, PrContext):
            # Fallback if just text is passed (legacy support if needed)
            text = str(output)
            files = []
        else:
            text = output.diff_text
            files = output.changed_files

        violations = []

        # Parse condition
        if self.condition.startswith("path:"):
            regex_str = self.condition[len("path:") :]
            regex = re.compile(regex_str, re.IGNORECASE)

            # Check against file list for precise evidence
            matched_files = [f for f in files if regex.search(f)]

            if matched_files:
                # Create a violation for each match, or aggregated?
                # Aggregated is cleaner, but we want individual evidence.
                # Violation supports ONE message, but meta can hold list.

                # We return one violation per rule, with full evidence list.
                # Wait, Rule returns List[Violation].

                evidence_list = []
                for f in matched_files:
                    evidence_list.append(
                        EvidenceItem(rule_id=self.id, evidence_type="path", value=f).model_dump()
                    )

                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=self.impact_data.get("impact", "Unknown Impact"),
                        meta={
                            "severity": self.impact_data.get("severity", "LOW"),
                            "actions": self.impact_data.get("required_actions", []),
                            "evidence": evidence_list,
                        },
                    )
                )

        elif self.condition == "meta:large_change_without_docs":
            is_large = len(text) > 10000
            has_docs = "docs/" in text or "documentation" in text.lower()  # heuristic

            if is_large and not has_docs:
                evidence = EvidenceItem(
                    rule_id=self.id,
                    evidence_type="diff_snippet",
                    value=f"Diff size: {len(text)} chars, no docs/ found",
                ).model_dump()

                violations.append(
                    Violation(
                        rule_id=self.id,
                        message=self.impact_data.get("impact", "Maintainability"),
                        meta={
                            "severity": self.impact_data.get("severity", "MEDIUM"),
                            "actions": self.impact_data.get("required_actions", []),
                            "evidence": [evidence],
                        },
                    )
                )

        # If it was a generic regex on diff content (not implemented in v1 but easy to add)
        # We would check `text` and return snippet.

        return violations


class GitHubAdapter:
    def __init__(self, llm: LLM | None = None, repo_root: str = "."):
        self.token = os.environ.get("GITHUB_TOKEN")
        self.llm = llm
        self.repo_root = os.path.abspath(repo_root)

    def _fetch_pr_diff(self, api_url: str) -> str:
        req = urllib.request.Request(api_url)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github.v3.diff")

        with urllib.request.urlopen(req) as response:
            return response.read().decode("utf-8")

    def _fetch_pr_files(self, api_url: str) -> list[str]:
        # transform /pulls/123 -> /pulls/123/files
        files_url = f"{api_url}/files"
        req = urllib.request.Request(files_url)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")

        # This returns JSON
        try:
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode("utf-8"))
                # data is list of file objects
                return [f["filename"] for f in data]
        except Exception:
            # Fallback if API fails or rate limited?
            # We can try to extract from diff text but that's harder.
            # Return empty list or raise.
            return []

    def _load_rules(self) -> list[ImpactRule]:
        import pathlib

        current_dir = pathlib.Path(__file__).parent
        rules_path = current_dir / "impact_rules.yaml"

        with open(rules_path) as f:
            data = yaml.safe_load(f)

        rules = []
        for entry in data:
            rules.append(
                ImpactRule(id=entry["id"], condition=entry["when"], impact_data=entry["then"])
            )
        return rules

    def generate_forecast(
        self, pr_url: str, diff_content: str | None = None, file_list: list[str] | None = None
    ) -> ImpactForecast:
        """
        Main entry point.
        """
        # Parse URL
        match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
        if match:
            owner, repo, number = match.groups()
            api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
        else:
            api_url = pr_url  # Assume raw API url

        # 1. Fetch Data
        diff = diff_content if diff_content is not None else self._fetch_pr_diff(api_url)
        changed_files = file_list if file_list is not None else self._fetch_pr_files(api_url)

        pr_context = PrContext(diff_text=diff, changed_files=changed_files)

        # 2. Guard (Symbolic Rules)
        rules = self._load_rules()
        guard = Guard(rules=rules)  # type: ignore

        # We invoke guard on the PrContext object
        # Note: Guard.apply expects Artifact. We can use apply_text/json or generic apply.
        # Since our ImpactRule expects PrContext, we should pass it via Artifact.kind="pr_context"
        # wrapping is handled by creating the artifact.

        # However, Guard.apply(Artifact) passes artifact.content to rules.
        # So content=pr_context.

        result_artifact = Artifact(kind="pr_context", content=pr_context)
        guard_result = guard.apply(result_artifact)

        # 3. Codeowners & Arch Map
        owners = set()

        # Codeowners
        co_path = codeowners.find_codeowners(self.repo_root)
        if co_path:
            with open(co_path) as f:
                co_rules = codeowners.parse_codeowners(f.read())
            owners.update(codeowners.match_owners(changed_files, co_rules))

        # Arch Map
        am = arch_map.load_arch_map(self.repo_root)
        impacted_components = arch_map.resolve_components(changed_files, am)
        impact_chain = arch_map.build_impact_chain(impacted_components, am)
        owners.update(arch_map.owners_from_arch_map(impacted_components, am))

        # 4. Agent (LLM)
        agent_hypotheses: list[ImpactHypothesis] = []
        if self.llm:
            agent = ImpactAgent(self.llm)
            diff_summary = diff[:20000]
            agent_hypotheses = agent.hypothesize(diff_summary)

        # 5. Merge all
        triggered_rules = []
        rule_impacts: list[ImpactHypothesis] = []
        all_actions = set()
        all_evidence = []
        max_severity_score = 0
        severity_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}

        for v in guard_result.violations:
            rule_id = v.get("rule_id", "unknown")
            triggered_rules.append(rule_id)
            meta = v.get("meta") or {}
            severity = meta.get("severity", "LOW")
            actions = meta.get("actions", [])
            evidence_dicts = meta.get("evidence", [])

            score = severity_map.get(severity, 1)
            if score > max_severity_score:
                max_severity_score = score

            all_actions.update(actions)

            for ev in evidence_dicts:
                # ev is dict, convert to class
                all_evidence.append(EvidenceItem(**ev))

            rule_impacts.append(
                ImpactHypothesis(
                    area=v.get("message", "Unknown"),
                    reason=f"Symbolic detection via rule {rule_id}",
                    confidence=1.0,
                )
            )

        combined_impacts = rule_impacts + agent_hypotheses
        risk_score_to_label = {1: "LOW", 2: "MEDIUM", 3: "HIGH", 0: "LOW"}
        final_risk = risk_score_to_label[max_severity_score]

        return ImpactForecast(
            risk=final_risk,  # type: ignore
            impacts=combined_impacts,
            required_actions=sorted(all_actions),
            triggered_rules=triggered_rules,
            owners_to_notify=sorted(owners),
            evidence=all_evidence,
            impact_chain=impact_chain,
        )
