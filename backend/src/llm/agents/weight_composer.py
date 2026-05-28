"""Weight Composer agent — turns user priorities into VRP objective weights."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import ValidationError

from src.llm.client import GeminiClient, LLMCallResult
from src.llm.prompts import WEIGHT_COMPOSER_PROMPT
from src.llm.schemas import LLMTrace, WeightSpec
from src.llm.tools import WEIGHT_TOOL

logger = logging.getLogger(__name__)


class WeightComposerError(Exception):
    """Raised when the composer cannot produce valid weights."""


@dataclass
class WeightOutcome:
    spec: WeightSpec
    trace: LLMTrace
    used_fallback: bool


# Used if Gemini repeatedly fails — balanced weights as safe default
_FALLBACK_SPEC = WeightSpec(
    distance=1 / 3, duration=1 / 3, co2=1 / 3,
    rationale="LLM 호출 실패로 균형 가중치 사용",
)


class WeightComposerAgent:
    def __init__(self, client: GeminiClient) -> None:
        self._client = client

    async def compose(self, user_input: str) -> WeightOutcome:
        last_error: Exception | None = None
        for attempt in (0, 1):
            user_message = user_input
            if attempt == 1 and last_error:
                user_message = (
                    f"{user_input}\n\n"
                    f"(이전 응답이 유효하지 않았습니다: {last_error}. "
                    f"weights의 합이 정확히 1.0이 되도록 compose_weights를 호출해주세요.)"
                )
            result = await self._client.call_with_tool(
                system_prompt=WEIGHT_COMPOSER_PROMPT,
                user_message=user_message,
                tool=WEIGHT_TOOL,
                force_call=True,
            )
            try:
                spec = self._parse(result)
                return WeightOutcome(
                    spec=spec,
                    trace=_make_trace(
                        "weight_composer",
                        self._client.model,
                        user_message,
                        result,
                        retried=attempt > 0,
                        used_fallback=False,
                    ),
                    used_fallback=False,
                )
            except (ValidationError, WeightComposerError) as e:
                logger.warning(
                    "weight_composer.invalid", extra={"attempt": attempt, "err": str(e)}
                )
                last_error = e

        logger.warning("weight_composer.fallback_to_balanced", extra={"err": str(last_error)})
        return WeightOutcome(
            spec=_FALLBACK_SPEC,
            trace=LLMTrace(
                agent="weight_composer",
                model=self._client.model,
                prompt_chars=len(user_input),
                response_chars=0,
                function_called=None,
                retried=True,
                used_fallback=True,
                elapsed_ms=0,
            ),
            used_fallback=True,
        )

    @staticmethod
    def _parse(result: LLMCallResult) -> WeightSpec:
        if result.function_name != WEIGHT_TOOL["name"]:
            raise WeightComposerError(
                f"Expected '{WEIGHT_TOOL['name']}', got {result.function_name!r}"
            )
        if result.function_args is None:
            raise WeightComposerError("Function call carried no arguments")
        return WeightSpec(**result.function_args)


def _make_trace(
    agent: str,
    model: str,
    user_message: str,
    result: LLMCallResult,
    *,
    retried: bool,
    used_fallback: bool,
) -> LLMTrace:
    return LLMTrace(
        agent=agent,
        model=model,
        prompt_chars=len(user_message),
        response_chars=len(str(result.function_args or "")),
        function_called=result.function_name,
        retried=retried,
        used_fallback=used_fallback,
        elapsed_ms=result.elapsed_ms,
    )
