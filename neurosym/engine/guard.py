from typing import Any, List, Dict
from neurosym.rules.base import Rule, Violation

class GuardResult:
    def __init__(self, output: Any, trace: List[Dict]):
        self.output = output
        self.trace = trace
    def report(self) -> str:
        return "\n".join([f"try {t['attempt']}: {t['violations']}" for t in self.trace])

class Guard:
    def __init__(self, llm, rules: List[Rule], max_retries: int = 2):
        self.llm = llm
        self.rules = rules
        self.max_retries = max_retries

    def _validate(self, output: Any) -> List[Violation]:
        out: List[Violation] = []
        for r in self.rules:
            out.extend(r.evaluate(output))
        return out

    def _repair_prompt(self, prompt: str, violations: List[Violation]) -> str:
        msgs = "\n".join([f"- [{v.rule_id}] {v.message}" for v in violations])
        return (f"{prompt}\n\nYour previous answer violated these rules:\n{msgs}\n"
                "Please return a corrected answer that satisfies all rules.")

    def generate(self, prompt: str, **gen_kwargs) -> GuardResult:
        attempt, trace = 0, []
        text = self.llm.generate(prompt, **gen_kwargs)
        while True:
            viol = self._validate(text)
            trace.append({"attempt": attempt, "violations": [v.rule_id for v in viol]})
            if not viol or attempt >= self.max_retries:
                return GuardResult(text, trace)
            attempt += 1
            text = self.llm.generate(self._repair_prompt(prompt, viol), **gen_kwargs)
