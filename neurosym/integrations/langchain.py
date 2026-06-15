"""LangChain adapter — NeurosymCallbackHandler."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from neurosym.engine.guard import Guard, GuardResult


def _import_base_callback_handler() -> type:
    """Return BaseCallbackHandler from whatever LangChain version is installed, or object."""
    try:
        from langchain_core.callbacks import BaseCallbackHandler  # type: ignore[import]

        return BaseCallbackHandler  # type: ignore[return-value]
    except ImportError:
        pass
    try:
        from langchain.callbacks.base import BaseCallbackHandler  # type: ignore[import]

        return BaseCallbackHandler  # type: ignore[return-value]
    except ImportError:
        pass
    return object


def _make_handler_class(_Base: type) -> type:
    """Build NeurosymCallbackHandler inheriting from _Base at import time."""

    class NeurosymCallbackHandler(_Base):  # type: ignore[misc,valid-type]
        """
        LangChain callback handler that runs neurosym-ai guards on LLM I/O.

        Plug into any LangChain chain with two lines::

            from neurosym.integrations.langchain import NeurosymCallbackHandler
            from neurosym import Guard, PromptInjectionRule, BanTopicsRule

            handler = NeurosymCallbackHandler(
                input_guard=Guard(rules=[PromptInjectionRule()]),
                output_guard=Guard(rules=[BanTopicsRule()]),
            )
            llm = ChatOpenAI(callbacks=[handler])

        Args:
            input_guard:         Guard evaluated against the LLM prompt(s).
            output_guard:        Guard evaluated against the LLM response text.
            raise_on_violation:  When ``True`` (default), a blocked result raises
                                 ``ValueError`` so LangChain propagates it as an
                                 error. Set to ``False`` to record the result
                                 silently and check ``last_input_result`` /
                                 ``last_output_result`` yourself.
        """

        def __init__(
            self,
            input_guard: Guard | None = None,
            output_guard: Guard | None = None,
            raise_on_violation: bool = True,
        ) -> None:
            if _Base is object:
                raise ImportError(
                    "NeurosymCallbackHandler requires LangChain: "
                    "pip install langchain-core   # or: pip install langchain"
                )
            super().__init__()
            self._input_guard = input_guard
            self._output_guard = output_guard
            self._raise = raise_on_violation
            self.last_input_result: GuardResult | None = None
            self.last_output_result: GuardResult | None = None

        # ------------------------------------------------------------------ #
        # LangChain callback hooks                                             #
        # ------------------------------------------------------------------ #

        def on_llm_start(
            self,
            serialized: dict[str, Any],
            prompts: list[str],
            *,
            run_id: UUID | None = None,
            **kwargs: Any,
        ) -> None:
            if self._input_guard is None:
                return
            combined = "\n".join(prompts)
            result = self._input_guard.apply_text(combined)
            self.last_input_result = result
            if result.blocked and self._raise:
                msgs = "; ".join(v.get("message", "violation") for v in result.violations)
                raise ValueError(f"[neurosym-ai] Input blocked: {msgs}")

        def on_llm_end(
            self,
            response: Any,
            *,
            run_id: UUID | None = None,
            **kwargs: Any,
        ) -> None:
            if self._output_guard is None:
                return
            text = self._extract_text(response)
            result = self._output_guard.apply_text(text)
            self.last_output_result = result
            if result.blocked and self._raise:
                msgs = "; ".join(v.get("message", "violation") for v in result.violations)
                raise ValueError(f"[neurosym-ai] Output blocked: {msgs}")

        def on_llm_error(
            self,
            error: Exception | KeyboardInterrupt,
            *,
            run_id: UUID | None = None,
            **kwargs: Any,
        ) -> None:
            pass  # nothing to guard on error

        def on_chain_start(self, *args: Any, **kwargs: Any) -> None:
            pass

        def on_chain_end(self, *args: Any, **kwargs: Any) -> None:
            pass

        def on_chain_error(self, *args: Any, **kwargs: Any) -> None:
            pass

        def on_tool_start(self, *args: Any, **kwargs: Any) -> None:
            pass

        def on_tool_end(self, *args: Any, **kwargs: Any) -> None:
            pass

        def on_tool_error(self, *args: Any, **kwargs: Any) -> None:
            pass

        # ------------------------------------------------------------------ #
        # Internals                                                            #
        # ------------------------------------------------------------------ #

        @staticmethod
        def _extract_text(response: Any) -> str:
            """Best-effort extraction of text from a LangChain LLMResult.

            Scans all generations so batched or multi-generation responses are
            fully covered rather than only the first generation.
            """
            try:
                parts: list[str] = []
                for batch in response.generations:
                    for gen in batch:
                        try:
                            parts.append(str(gen.text))
                        except Exception:
                            try:
                                parts.append(str(gen.message.content))
                            except Exception:
                                pass
                if parts:
                    return "\n".join(parts)
            except Exception:
                pass
            return str(response)

    return NeurosymCallbackHandler


NeurosymCallbackHandler: type = _make_handler_class(_import_base_callback_handler())
