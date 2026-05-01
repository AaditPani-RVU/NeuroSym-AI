import json

from neurosym.agents.impact_forecaster.impact_models import (
    ImpactForecastUnavailable,
    ImpactHypothesis,
)
from neurosym.engine.guard import Guard, GuardResult
from neurosym.llm import LLM
from neurosym.rules.schema_rule import SchemaRule


class ImpactAgent:
    def __init__(self, llm: LLM):
        self.llm = llm

    def hypothesize(self, diff_summary: str) -> list[ImpactHypothesis]:
        """
        Uses the LLM to propose *possible* impact areas.
        """
        # 1. Define schema for List[ImpactHypothesis]
        # Pydantic's root_model can help generate schema for a list,
        # or we manually construct the wrapper schema.
        from pydantic import RootModel

        schema = RootModel[list[ImpactHypothesis]].model_json_schema()

        # 2. Create the prompt
        prompt = (
            "You are a Senior Software Architect. Analyze this PR diff summary "
            "and hypothesize POTENTIAL impact areas.\n"
            "Be conservative: no speculation. If impact is unsure, do not list it.\n"
            f"Diff Summary:\n{diff_summary}\n\n"
            f"You MUST output valid JSON only, following this schema:\n"
            f"{json.dumps(schema, indent=2)}\n"
        )

        # 3. Use Guard for validation and retry
        rule = SchemaRule("impact.schema", schema)
        guard = Guard(rules=[rule], llm=self.llm, max_retries=2)

        # 4. Generate
        result: GuardResult = guard.generate(prompt)

        # 5. Extract output
        # Guard applies repairs, but if it fails validation, result.ok is False.
        # We process whatever we got if it's valid, or return empty list if failed?
        # The requirements say "Add retry-on-JSON-failure". Guard does this internally.

        if not result.ok:
            raise ImpactForecastUnavailable("LLM response failed schema validation after retries")

        try:
            from neurosym.rules.schema_rule import _ensure_json_any

            parsed, _ = _ensure_json_any(result.output, extract=True)
            if parsed is None:
                raise ImpactForecastUnavailable("could not extract JSON from LLM response")

            hypotheses = RootModel[list[ImpactHypothesis]].model_validate(parsed)
            return hypotheses.root
        except ImpactForecastUnavailable:
            raise
        except Exception as exc:
            raise ImpactForecastUnavailable(str(exc)) from exc
