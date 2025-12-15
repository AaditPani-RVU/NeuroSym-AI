# neurosym/cli_tui.py
# ruff: noqa: B008

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from neurosym.engine.guard import Guard
from neurosym.pre.redaction import Redactor
from neurosym.rules.policies import DenyIfContains, MaxLengthRule
from neurosym.rules.regex_rule import RegexRule
from neurosym.rules.schema_rule import SchemaRule

console = Console()
app = typer.Typer(no_args_is_help=True, add_completion=False, rich_markup_mode="rich")


# ---- LLM selection ---------------------------------------------------------
class EchoLLM:
    def generate(self, prompt: str, **_):
        return "Acknowledged. (fallback response)"


def get_llm(use_ollama: bool, model: str = "phi3:mini"):
    if not use_ollama:
        return EchoLLM()
    try:
        from neurosym.llm.ollama import OllamaLLM

        return OllamaLLM(model=model)
    except Exception as e:
        console.print(f"[yellow]Using EchoLLM fallback[/yellow] — Ollama unavailable: {e}")
        return EchoLLM()


# ---- Rules builder ---------------------------------------------------------
def build_rules(include_schema: dict | None = None) -> list[Any]:
    rules: list[Any] = [
        RegexRule(
            id="safety.no_email",
            pattern=r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
            must_not_match=True,
            flags=re.IGNORECASE,
        ),
        DenyIfContains(id="policy.no_abuse", banned=["wire fraud", "malware"]),
        MaxLengthRule(id="fmt.max_len", max_len=8000),
    ]
    if include_schema is not None:
        rules.append(SchemaRule(id="schema.user", schema=include_schema))
    return rules


# ---- Pretty printers -------------------------------------------------------
def render_trace_table(result) -> Table:
    table = Table(title="Decision Trace", expand=True)
    table.add_column("Attempt", justify="right", style="cyan", no_wrap=True)
    table.add_column("Violations", style="magenta")
    for t in result.trace:
        v_ids = ", ".join(v.get("rule_id", "?") for v in t.violations) or "none"
        table.add_row(str(t.attempt), v_ids)
    return table


def render_violations_detail(attempt) -> Panel | None:
    if not attempt.violations:
        return None
    lines = []
    for v in attempt.violations:
        lines.append(f"[bold]{v['rule_id']}[/bold]: {v['message']}")
        if v.get("meta"):
            meta_json = json.dumps(v["meta"], ensure_ascii=False, indent=2)
            lines.append(f"[dim]{meta_json}[/dim]")
    return Panel("\n".join(lines), title="Last Attempt Violations (detailed)", border_style="red")


def load_schema(path: Path | None) -> dict | None:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        console.print(f"[red]Failed to read schema:[/red] {e}")
        raise typer.Exit(2) from e


# ---- Commands --------------------------------------------------------------
@app.command(help="One-shot guarded generation (pretty output).")
def run(
    task: str = typer.Option(..., "--task", "-t", help="e.g., 'Summarize' or 'Extract JSON'."),
    text: str = typer.Option(..., "--text", "-x", help="Input text."),
    ollama: bool = typer.Option(False, "--ollama", help="Use local Ollama (phi3:mini)."),
    retries: int = typer.Option(1, "--retries", "-r", min=0, help="Max repair retries."),
    redact: bool = typer.Option(True, "--redact/--no-redact", help="Pre & post PII redaction."),
    schema_path: Path | None = typer.Option(None, "--schema", "-s", help="Path to JSON Schema."),
    deny_email_hard: bool = typer.Option(
        True,
        "--deny-email-hard/--no-deny-email-hard",
        help="Stop early if email detected.",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON {output, trace} only."),
):
    # LLM + rules
    llm = get_llm(ollama)
    schema = load_schema(schema_path)
    rules = build_rules(schema)
    guard = Guard(
        llm=llm,
        rules=rules,
        max_retries=retries,
        deny_rule_ids={"safety.no_email"} if deny_email_hard else set(),
    )

    # redact input
    effective_text = text
    red_in_hits = 0
    if redact:
        red = Redactor().apply(text)
        effective_text = red.text
        red_in_hits = len(red.hits)

    prompt = f"{task}.\nInput: '''{effective_text}'''"
    result = guard.generate(prompt, temperature=0.2, max_tokens=512)

    # redact output
    out_text = result.output
    red_out_hits = 0
    if redact:
        red_o = Redactor().apply(out_text)
        out_text = red_o.text
        red_out_hits = len(red_o.hits)

    payload = {"output": out_text, "trace": result.to_dict()["trace"]}

    if json_out:
        console.print_json(data=payload)
        raise typer.Exit()

    # pretty print
    console.print(Panel(f"[bold]{task}[/bold]", subtitle="NeuroSym-AI", border_style="green"))
    console.print(Panel(out_text, title="Output", border_style="cyan"))
    if red_in_hits or red_out_hits:
        console.print(f"[dim]Redactions — input: {red_in_hits}, output: {red_out_hits}[/dim]")

    console.print(render_trace_table(result))
    detail = render_violations_detail(result.trace[-1])
    if detail:
        console.print(detail)


@app.command(help="Interactive REPL with guardrails.")
def chat(
    ollama: bool = typer.Option(False, "--ollama", help="Use local Ollama (phi3:mini)."),
    redact: bool = typer.Option(True, "--redact/--no-redact", help="Pre & post PII redaction."),
    retries: int = typer.Option(1, "--retries", "-r", min=0),
    schema_path: Path | None = typer.Option(None, "--schema", "-s"),
):
    llm = get_llm(ollama)
    schema = load_schema(schema_path)
    rules = build_rules(schema)
    guard = Guard(llm=llm, rules=rules, max_retries=retries, deny_rule_ids={"safety.no_email"})

    console.print(Panel("NeuroSym-AI Interactive", border_style="green"))
    console.print("[dim]Type 'exit' to quit.[/dim]\n")

    while True:
        task = console.input("[bold cyan]Task[/bold cyan]: ").strip()
        if task.lower() == "exit":
            break
        text = console.input("[bold cyan]Input[/bold cyan]: ").strip()
        if text.lower() == "exit":
            break

        effective_text = text
        red_in_hits = 0
        if redact:
            red = Redactor().apply(text)
            effective_text = red.text
            red_in_hits = len(red.hits)

        res = guard.generate(f"{task}.\nInput: '''{effective_text}'''")
        out_text = res.output
        red_out_hits = 0
        if redact:
            ro = Redactor().apply(out_text)
            out_text = ro.text
            red_out_hits = len(ro.hits)

        console.print(Panel(out_text, title="Output", border_style="cyan"))
        if red_in_hits or red_out_hits:
            console.print(f"[dim]Redactions — input: {red_in_hits}, output: {red_out_hits}[/dim]")
        console.print(render_trace_table(res))
        detail = render_violations_detail(res.trace[-1])
        if detail:
            console.print(detail)
        console.print("")  # spacing
