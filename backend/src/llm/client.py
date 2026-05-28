"""Async Gemini client wrapper for E.L.O.

Encapsulates the google-genai SDK with:
  - System prompt + tool injection
  - Function-call extraction
  - Plain-text output extraction
  - Timing + retry hooks

The SDK is synchronous; we wrap each call with asyncio.to_thread so it
plays nicely inside FastAPI's event loop.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types as gtypes

logger = logging.getLogger(__name__)


@dataclass
class LLMCallResult:
    function_name: str | None
    function_args: dict[str, Any] | None
    text: str | None
    elapsed_ms: int
    raw: Any  # GenerateContentResponse


class GeminiClient:
    def __init__(self, api_key: str, model: str = "gemini-3.5-flash") -> None:
        if not api_key:
            raise ValueError("GeminiClient requires an API key")
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    async def call_with_tool(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tool: dict,
        force_call: bool = True,
        temperature: float = 0.2,
    ) -> LLMCallResult:
        """Call Gemini forcing a specific function tool. Returns parsed args."""
        function_declaration = gtypes.FunctionDeclaration(**tool)
        tool_obj = gtypes.Tool(function_declarations=[function_declaration])
        config = gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[tool_obj],
            tool_config=gtypes.ToolConfig(
                function_calling_config=gtypes.FunctionCallingConfig(
                    mode="ANY" if force_call else "AUTO"
                ),
            ),
            temperature=temperature,
            thinking_config=_no_thinking_config(),
        )
        t0 = time.perf_counter()
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model,
            contents=user_message,
            config=config,
        )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        fn_name, fn_args = _extract_function_call(response)
        return LLMCallResult(
            function_name=fn_name,
            function_args=fn_args,
            text=None,
            elapsed_ms=elapsed_ms,
            raw=response,
        )

    async def call_text(
        self,
        *,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.4,
        max_output_tokens: int | None = None,
    ) -> LLMCallResult:
        """Call Gemini for plain text output (no tools)."""
        config = gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            thinking_config=_no_thinking_config(),
        )
        if max_output_tokens is not None:
            config.max_output_tokens = max_output_tokens
        t0 = time.perf_counter()
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model,
            contents=user_message,
            config=config,
        )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return LLMCallResult(
            function_name=None,
            function_args=None,
            text=_extract_text(response),
            elapsed_ms=elapsed_ms,
            raw=response,
        )


def _extract_function_call(response: Any) -> tuple[str | None, dict | None]:
    try:
        for cand in response.candidates or []:
            for part in cand.content.parts or []:
                fc = getattr(part, "function_call", None)
                if fc and fc.name:
                    # fc.args is a Mapping-like object; convert to plain dict
                    args = dict(fc.args) if fc.args else {}
                    return fc.name, args
    except Exception as e:  # noqa: BLE001
        logger.warning("llm.extract_fn_call_failed", extra={"err": str(e)})
    return None, None


def _extract_text(response: Any) -> str | None:
    """Concatenate every non-thinking text part across all candidates.

    Gemini 2.5+ "thinking" models emit two kinds of text parts: ones with
    `thought=True` (internal reasoning) and ones with `thought=False` /
    None (the actual answer). We only want the latter. We also belt-and-
    suspenders by setting thinking_budget=0 in the request config.
    """
    chunks: list[str] = []
    try:
        for cand in response.candidates or []:
            content = getattr(cand, "content", None)
            if content is None:
                continue
            for part in getattr(content, "parts", None) or []:
                if getattr(part, "thought", False):
                    continue  # skip internal reasoning
                t = getattr(part, "text", None)
                if t:
                    chunks.append(t)
    except Exception as e:  # noqa: BLE001
        logger.warning("llm.extract_text_failed", extra={"err": str(e)})
        return None
    if chunks:
        return "".join(chunks).strip() or None
    try:
        return getattr(response, "text", None) or None
    except Exception:  # noqa: BLE001
        return None


def _no_thinking_config() -> gtypes.ThinkingConfig | None:
    """Try to disable thinking. SDK accepts thinking_budget=0 on supported models."""
    try:
        return gtypes.ThinkingConfig(thinking_budget=0)
    except Exception:  # noqa: BLE001
        # Older SDK or model w/o thinking — config is optional
        return None
