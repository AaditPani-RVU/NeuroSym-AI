# neurosym/__main__.py — run: python -m neurosym check --rule email --text "..."
import argparse, sys
from neurosym.llm.gemini import GeminiLLM
from neurosym.llm.ollama import OllamaLLM
from neurosym.llm.fallback import FallbackLLM
from neurosym.engine.guard import Guard
from neurosym.rules.regex_rule import RegexRule

def cmd_check(args):
    rules = []
    if args.rule == "email":
        rules.append(RegexRule("no-email", r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"))
    # add more short-hands as you like

    llm = FallbackLLM(GeminiLLM("gemini-1.5-flash"), OllamaLLM("phi3:mini"))
    res = Guard(llm, rules, max_retries=2).generate(args.text, temperature=0.2)
    print(res.output)
    print("\nTRACE:\n" + res.report())

def main(argv=None):
    p = argparse.ArgumentParser(prog="neurosym")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("check", help="Generate text then validate/repair with simple rules")
    pc.add_argument("--rule", choices=["email"], default="email")
    pc.add_argument("--text", required=True)
    pc.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    args.func(args)

if __name__ == "__main__":
    main()
