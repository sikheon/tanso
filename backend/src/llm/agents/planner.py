"""Planner agent — decides routing workflow shape via Gemini function call."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import ValidationError

from src.llm.client import GeminiClient, LLMCallResult
from src.llm.prompts import PLANNER_PROMPT
from src.llm.schemas import ExecutionPlan, LLMTrace
from src.llm.tools import PLANNER_TOOL

logger = logging.getLogger(__name__)


class PlannerError(Exception):
    """Raised when planner cannot produce a valid execution plan."""


@dataclass
class PlannerOutcome:
    plan: ExecutionPlan
    trace: LLMTrace


class PlannerAgent:
    def __init__(self, client: GeminiClient) -> None:
        self._client = client

    async def plan(self, user_input: str) -> PlannerOutcome:
        """Convert user input -> ExecutionPlan via forced function call.

        Retries once on validation failure with a clarifying suffix.
        """
        last_error: Exception | None = None
        for attempt in (0, 1):
            user_message = user_input
            if attempt == 1 and last_error:
                user_message = (
                    f"{user_input}\n\n"
                    f"(이전 응답은 유효하지 않았습니다: {last_error}. "
                    f"create_execution_plan 함수를 정확히 호출해주세요.)"
                )
            result = await self._client.call_with_tool(
                system_prompt=PLANNER_PROMPT,
                user_message=user_message,
                tool=PLANNER_TOOL,
                force_call=True,
            )
            try:
                plan = self._parse(result)
                return PlannerOutcome(
                    plan=plan,
                    trace=_to_trace(
                        agent="planner",
                        model=self._client.model,
                        user_message=user_message,
                        result=result,
                        function_name=result.function_name,
                        retried=attempt > 0,
                    ),
                )
            except (ValidationError, PlannerError) as e:
                logger.warning("planner.invalid_response", extra={"attempt": attempt, "err": str(e)})
                last_error = e

        raise PlannerError(f"Planner failed after retry: {last_error}")

    @staticmethod
    def _parse(result: LLMCallResult) -> ExecutionPlan:
        if result.function_name != PLANNER_TOOL["name"]:
            raise PlannerError(
                f"Expected function '{PLANNER_TOOL['name']}', got {result.function_name!r}"
            )
        if result.function_args is None:
            raise PlannerError("Function call carried no arguments")
        return ExecutionPlan(**result.function_args)


def _to_trace(
    *,
    agent: str,
    model: str,
    user_message: str,
    result: LLMCallResult,
    function_name: str | None,
    retried: bool,
) -> LLMTrace:
    return LLMTrace(
        agent=agent,
        model=model,
        prompt_chars=len(user_message),
        response_chars=len(str(result.function_args or "")),
        function_called=function_name,
        retried=retried,
        used_fallback=False,
        elapsed_ms=result.elapsed_ms,
    )
