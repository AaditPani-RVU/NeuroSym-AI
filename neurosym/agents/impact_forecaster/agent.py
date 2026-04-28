import json

from neurosym.agents.impact_forecaster.impact_models import ImpactHypothesis
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
            # If after retries it's still invalid, we might return empty or raise.
            # "Must return structured JSON only".
            # I will return empty list if completely failed to parse,
            # to be safe, or raise an exception?
            # "Must NOT decide severity or final risk" -> The agent doesn't decide risk,
            # but if it fails to output JSON, we can't do anything.
            # I'll log/warn (print) and return empty list.
            # But wait, checking output content...
            pass

        # Try to parse the output into pydantic objects
        try:
            # result.output is the text. If SchemaRule passed, it should be valid JSON.
            # Wait, SchemaRule._ensure_json_any might extract the block.
            # But Guard.generate returns the TEXT output of the LLM.
            # Does Guard return the PARSED output if apply_json was used?
            # No, Guard.generate calls _safe_llm_generate returning string.
            # But SchemaRule validates the string (extracting json if needed).

            # We need to extract the JSON again to parse it into Pydantic.
            # SchemaRule has helpers _extract_first_json_block.
            # I should use those or just try json.loads on result.output or extracted block.
            # Actually, `Guard.apply` returns an artifact with repairs.
            # Let's inspect `GuardResult` again. It has `artifact`.
            # If I used `apply`, `artifact.kind` handles parsing if I implemented it.
            # But `generate` returns `output=text`.

            # Use standard json helper for extraction.
            from neurosym.rules.schema_rule import _ensure_json_any

            parsed, _ = _ensure_json_any(result.output, extract=True)
            if parsed is None:
                return []

            # Validate with Pydantic
            hypotheses = RootModel[list[ImpactHypothesis]].model_validate(parsed)
            return hypotheses.root
        except Exception:
            return []
