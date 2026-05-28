"""End-to-end LLM agent integration test (real Gemini calls).

Walks through PRD scenario S-2:
  Planner → ConstraintExtractor → WeightComposer → Narrative
"""

from __future__ import annotations

import asyncio
import sys

from src.core import asyncio_compat  # noqa: F401
from src.core.config import get_settings
from src.llm import (
    ConstraintExtractorAgent,
    GeminiClient,
    NarrativeAgent,
    PlannerAgent,
    WeightComposerAgent,
)

SCENARIO_VRP = (
    "내일 오전 8시 강남구청 차고지에서 출발해서 송파 3곳(site_1, site_2, site_3)과 "
    "강동 2곳(site_4, site_5) 배송, 12시까지 복귀. 1톤 디젤 트럭이고 친환경적으로 가고 싶음. "
    "site_2 고객은 점심시간 12:00-13:00에 받지 못함, "
    "site_3는 차고 높이 2.1m 제한, "
    "site_5는 후문으로 진입해야 함."
)

NARRATIVE_PAYLOAD = {
    "recommended": {
        "engine": "ors",
        "objective": "recommend",
        "distance_km": 398.4,
        "duration_min": 269,
        "co2_g": 60489,
    },
    "alternatives": [
        {"engine": "kakao", "objective": "recommend",
         "distance_km": 398.4, "duration_min": 280, "co2_g": 60679},
        {"engine": "kakao", "objective": "alternative",
         "distance_km": 405.5, "duration_min": 281, "co2_g": 62593},
    ],
    "co2_saved_g": 2104,
    "saved_vs": "kakao alternative",
    "vehicle": "diesel / truck_1t",
}


async def main() -> int:
    settings = get_settings()
    if not settings.gemini_api_key or settings.gemini_api_key.startswith("__"):
        print("SKIP: GEMINI_API_KEY not set")
        return 1

    client = GeminiClient(settings.gemini_api_key, model=settings.gemini_model)

    planner = PlannerAgent(client)
    composer = WeightComposerAgent(client)
    extractor = ConstraintExtractorAgent(client)
    narrator = NarrativeAgent(client)

    # 1. Planner
    print("[1/4] Planner...")
    plan_outcome = await planner.plan(SCENARIO_VRP)
    p = plan_outcome.plan
    print(
        f"  mode={p.mode.value}  engines={p.engines}  "
        f"need_constraints={p.needs_constraint_extraction}  "
        f"need_weights={p.needs_weight_composition}  "
        f"({plan_outcome.trace.elapsed_ms} ms)"
    )

    # 2. Constraint Extractor
    if p.needs_constraint_extraction:
        print("\n[2/4] Constraint Extractor...")
        known_sites = ["site_1", "site_2", "site_3", "site_4", "site_5"]
        ce_outcome = await extractor.extract(SCENARIO_VRP, known_site_ids=known_sites)
        print(f"  extracted {len(ce_outcome.batch.constraints)} constraints  "
              f"({ce_outcome.trace.elapsed_ms} ms)")
        for c in ce_outcome.batch.constraints:
            print(f"    - [{c.site_id}] {c.type}: range={c.range} value={c.value} reason={c.reason}")
    else:
        print("\n[2/4] Constraint Extractor — skipped (plan says not needed)")

    # 3. Weight Composer
    if p.needs_weight_composition:
        print("\n[3/4] Weight Composer...")
        wc_outcome = await composer.compose(SCENARIO_VRP)
        w = wc_outcome.spec
        print(
            f"  weights: dist={w.distance:.3f}  time={w.duration:.3f}  co2={w.co2:.3f}  "
            f"(fallback={wc_outcome.used_fallback}, {wc_outcome.trace.elapsed_ms} ms)"
        )
        print(f"  rationale: {w.rationale}")
    else:
        print("\n[3/4] Weight Composer — skipped (plan says not needed)")

    # 4. Narrative
    print("\n[4/4] Narrative Generator (with hallucination guard)...")
    nar = await narrator.generate(NARRATIVE_PAYLOAD)
    print(
        f"  retried={nar.retried}  used_fallback={nar.used_fallback}  "
        f"({nar.trace.elapsed_ms} ms, {len(nar.text)} chars)"
    )
    print("\n----- NARRATIVE -----")
    print(nar.text)
    print("---------------------")

    print("\n[OK] LLM end-to-end smoke passed.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
