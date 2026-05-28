"""Constraint Extractor agent — pulls structured site-level constraints from text."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import ValidationError

from src.llm.client import GeminiClient, LLMCallResult
from src.llm.prompts import CONSTRAINT_EXTRACTOR_PROMPT
from src.llm.schemas import ConstraintBatch, LLMTrace
from src.llm.tools import CONSTRAINT_TOOL

logger = logging.getLogger(__name__)


class ConstraintExtractorError(Exception):
    pass


@dataclass
class ConstraintOutcome:
    batch: ConstraintBatch
    trace: LLMTrace


class ConstraintExtractorAgent:
    def __init__(self, client: GeminiClient) -> None:
        self._client = client

    async def extract(
        self,
        user_input: str,
        *,
        known_site_ids: list[str] | None = None,
    ) -> ConstraintOutcome:
        """Extract constraints. `known_site_ids` is used to filter hallucinated IDs."""
        message = user_input
        if known_site_ids:
            sites_list = ", ".join(f"'{s}'" for s in known_site_ids)
            message = (
                f"{user_input}\n\n"
                f"(유효한 site_id 목록: {sites_list}. 이 외 다른 ID는 절대 사용 금지.)"
            )

        result = await self._client.call_with_tool(
            system_prompt=CONSTRAINT_EXTRACTOR_PROMPT,
            user_message=message,
            tool=CONSTRAINT_TOOL,
            force_call=True,
        )

        try:
            batch = self._parse(result)
        except (ValidationError, ConstraintExtractorError) as e:
            logger.warning("constraint.invalid", extra={"err": str(e)})
            # Empty batch is a safe default — caller can decide if missing
            # constraints justifies blocking the run.
            batch = ConstraintBatch(constraints=[])

        if known_site_ids is not None:
            allowed = set(known_site_ids)
            filtered = [c for c in batch.constraints if c.site_id in allowed]
            dropped = len(batch.constraints) - len(filtered)
            if dropped > 0:
                logger.info(
                    "constraint.filtered_unknown_sites",
                    extra={"dropped": dropped, "kept": len(filtered)},
                )
            batch = ConstraintBatch(constraints=filtered)

        return ConstraintOutcome(
            batch=batch,
            trace=LLMTrace(
                agent="constraint_extractor",
                model=self._client.model,
                prompt_chars=len(message),
                response_chars=len(str(result.function_args or "")),
                function_called=result.function_name,
                retried=False,
                used_fallback=False,
                elapsed_ms=result.elapsed_ms,
            ),
        )

    @staticmethod
    def _parse(result: LLMCallResult) -> ConstraintBatch:
        if result.function_name != CONSTRAINT_TOOL["name"]:
            raise ConstraintExtractorError(
                f"Expected '{CONSTRAINT_TOOL['name']}', got {result.function_name!r}"
            )
        if result.function_args is None:
            raise ConstraintExtractorError("Function call carried no arguments")
        return ConstraintBatch(**result.function_args)
