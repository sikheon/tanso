"""Smoke test for Planner agent — real Gemini call."""

from __future__ import annotations

import asyncio
import sys

from src.core import asyncio_compat  # noqa: F401
from src.core.config import get_settings
from src.llm.agents.planner import PlannerAgent
from src.llm.client import GeminiClient


SCENARIOS = [
    "서울역에서 부산역까지 가는 가장 친환경적인 경로 알려줘",
    "내일 오전 8시 강남 차고지에서 송파 3곳, 강동 2곳 배송, 1톤 디젤. "
    "강남 2번 고객은 점심시간 12-13시 받지 못함, 송파 1번은 후문 진입 필수.",
    "여의도에서 인천공항까지 빨리 가야 함",
]


async def main() -> int:
    settings = get_settings()
    if not settings.gemini_api_key or settings.gemini_api_key.startswith("__"):
        print("SKIP: GEMINI_API_KEY not set")
        return 1

    client = GeminiClient(settings.gemini_api_key, model=settings.gemini_model)
    agent = PlannerAgent(client)

    for i, text in enumerate(SCENARIOS, 1):
        print(f"\n[scenario #{i}]")
        print(f"  input: {text[:80]}{'...' if len(text) > 80 else ''}")
        outcome = await agent.plan(text)
        p = outcome.plan
        print(
            f"  plan : mode={p.mode.value}  engines={p.engines}  "
            f"alt={p.alternatives_per_engine}  "
            f"need_constraints={p.needs_constraint_extraction}  "
            f"need_weights={p.needs_weight_composition}"
        )
        print(
            f"  trace: {outcome.trace.elapsed_ms} ms  "
            f"({'retried' if outcome.trace.retried else 'one-shot'})"
        )

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
