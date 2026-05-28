"""Natural-language parsing service — Planner + WeightComposer + ConstraintExtractor."""

from __future__ import annotations

import asyncio
import logging

from src.api.schemas import ParsedJobOutline, ParseRequest, ParseResponse, WeightsDTO
from src.core.config import get_settings
from src.llm import (
    ConstraintExtractorAgent,
    GeminiClient,
    PlannerAgent,
    WeightComposerAgent,
)

logger = logging.getLogger(__name__)


class ParseError(Exception):
    pass


async def parse_natural_language(payload: ParseRequest) -> ParseResponse:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise ParseError("GEMINI_API_KEY not configured")

    client = GeminiClient(settings.gemini_api_key, model=settings.gemini_model)
    planner = PlannerAgent(client)

    # 1. Planner determines workflow
    plan_out = await planner.plan(payload.text)
    plan = plan_out.plan
    llm_trace: dict[str, int] = {"planner_ms": plan_out.trace.elapsed_ms}

    # 2. Constraint + Weight in parallel (independent)
    tasks = []
    if plan.needs_constraint_extraction:
        extractor = ConstraintExtractorAgent(client)
        tasks.append(("constraint", extractor.extract(payload.text)))
    if plan.needs_weight_composition:
        composer = WeightComposerAgent(client)
        tasks.append(("weights", composer.compose(payload.text)))

    constraints: list[dict] = []
    weights_dto: WeightsDTO | None = None

    if tasks:
        results = await asyncio.gather(*(t[1] for t in tasks), return_exceptions=True)
        for (name, _), res in zip(tasks, results, strict=True):
            if isinstance(res, Exception):
                logger.warning("parse.subagent_failed", extra={"agent": name, "err": str(res)})
                continue
            if name == "constraint":
                constraints = [c.model_dump() for c in res.batch.constraints]
                llm_trace["constraint_ms"] = res.trace.elapsed_ms
            elif name == "weights":
                spec = res.spec
                weights_dto = WeightsDTO(
                    distance=spec.distance, duration=spec.duration, co2=spec.co2
                )
                llm_trace["weights_ms"] = res.trace.elapsed_ms

    return ParseResponse(
        mode=plan.mode.value,
        vehicle_hint=None,
        depot_hint=None,
        jobs_outline=[],
        deadline_hint=None,
        weights=weights_dto,
        constraints=constraints,
        llm_trace=llm_trace,
    )
