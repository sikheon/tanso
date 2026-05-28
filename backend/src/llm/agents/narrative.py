"""Narrative Generator agent + hallucination guard."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from src.llm.client import GeminiClient
from src.llm.prompts import NARRATIVE_PROMPT
from src.llm.schemas import LLMTrace
from src.llm.validator import validate_narrative

logger = logging.getLogger(__name__)

# Constants the LLM is allowed to cite (PRD §14.2 reference values)
_REFERENCE_CONSTANTS: dict[str, float] = {
    "pine_30y_daily_g": 18.0,
    "pine_30y_yearly_kg": 6.6,
    "home_daily_kg": 4.0,
    "pine_age_years": 30.0,
}


@dataclass
class NarrativeOutcome:
    text: str
    used_fallback: bool
    retried: bool
    trace: LLMTrace


class NarrativeAgent:
    def __init__(self, client: GeminiClient) -> None:
        self._client = client

    async def generate(self, payload: dict[str, Any]) -> NarrativeOutcome:
        """`payload` should contain every number the LLM is allowed to mention."""
        # Pre-compute common derived values so the LLM never has to do
        # arithmetic that would produce a "new" number the guard rejects.
        enriched = _enrich_with_derived_metrics(payload)

        user_message = (
            "다음 JSON에 담긴 수치만 사용해서 친환경 추천 경로 설명을 작성하세요. "
            "JSON에 있는 derived 필드(환산값)도 그대로 인용해도 됩니다.\n"
            f"```json\n{json.dumps(enriched, ensure_ascii=False, indent=2)}\n```"
        )
        allowed_source = {**enriched, "_constants": _REFERENCE_CONSTANTS}

        first = await self._client.call_text(
            system_prompt=NARRATIVE_PROMPT,
            user_message=user_message,
            temperature=0.4,
            max_output_tokens=2000,  # thinking models consume tokens internally
        )
        text = first.text or ""
        ok, offending = validate_narrative(text, allowed_source)
        if ok and text.strip():
            return NarrativeOutcome(
                text=text.strip(),
                used_fallback=False,
                retried=False,
                trace=_trace_text("narrative", self._client.model, user_message, first, retried=False),
            )

        # Retry once with explicit complaint
        logger.warning(
            "narrative.hallucination_detected",
            extra={"offending": offending, "first_text": text[:160]},
        )
        warning = (
            f"\n\n주의: 이전 응답에서 입력에 없는 숫자({offending})가 발견되었습니다. "
            "JSON에 명시된 수치(또는 _constants)만 인용하고 새 숫자를 만들지 마세요."
        )
        second = await self._client.call_text(
            system_prompt=NARRATIVE_PROMPT + warning,
            user_message=user_message,
            temperature=0.2,
            max_output_tokens=2000,
        )
        text2 = (second.text or "").strip()
        ok2, off2 = validate_narrative(text2, allowed_source)
        if ok2 and text2:
            return NarrativeOutcome(
                text=text2,
                used_fallback=False,
                retried=True,
                trace=_trace_text("narrative", self._client.model, user_message, second, retried=True),
            )

        # Template fallback
        logger.warning("narrative.fallback_template", extra={"offending": off2})
        return NarrativeOutcome(
            text=_template_fallback(payload),
            used_fallback=True,
            retried=True,
            trace=_trace_text(
                "narrative", self._client.model, user_message, second, retried=True, used_fallback=True
            ),
        )


def _trace_text(
    agent: str,
    model: str,
    user_message: str,
    result,
    *,
    retried: bool,
    used_fallback: bool = False,
) -> LLMTrace:
    return LLMTrace(
        agent=agent,
        model=model,
        prompt_chars=len(user_message),
        response_chars=len(result.text or ""),
        function_called=None,
        retried=retried,
        used_fallback=used_fallback,
        elapsed_ms=result.elapsed_ms,
    )


def _enrich_with_derived_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute environmental/savings conversions so the LLM cites them
    verbatim instead of inventing similar-but-different numbers.

    Adds a top-level `derived` dict only if the relevant inputs exist.
    """
    out: dict[str, Any] = dict(payload)
    derived: dict[str, Any] = {}

    saved = payload.get("co2_saved_g")
    if isinstance(saved, (int, float)) and saved > 0:
        # Pine equivalents
        derived["pine_30y_days_equivalent"] = round(saved / _REFERENCE_CONSTANTS["pine_30y_daily_g"], 1)
        derived["pine_30y_trees_yearly"] = round(saved / (_REFERENCE_CONSTANTS["pine_30y_yearly_kg"] * 1000), 2)

    rec = payload.get("recommended") or {}
    alts = payload.get("alternatives") or []
    if alts and "co2_g" in rec:
        worst = max((a.get("co2_g", 0) for a in alts if isinstance(a.get("co2_g"), (int, float))), default=0)
        if worst and worst > 0:
            saved_pct = (worst - rec["co2_g"]) / worst * 100
            if saved_pct > 0:
                derived["co2_saved_pct_vs_worst"] = round(saved_pct, 1)

        # Best alternative for context
        best_alt = min(
            (a for a in alts if isinstance(a.get("co2_g"), (int, float))),
            key=lambda a: a["co2_g"],
            default=None,
        )
        if best_alt and "co2_g" in best_alt:
            diff = best_alt["co2_g"] - rec["co2_g"]
            if diff > 0:
                derived["co2_saved_vs_best_alt_g"] = diff

    if derived:
        out["derived"] = derived
    return out


def _template_fallback(payload: dict[str, Any]) -> str:
    """Deterministic fallback when LLM keeps hallucinating."""
    best = payload.get("recommended") or {}
    lines = ["## 추천 경로"]
    if best.get("engine") and best.get("objective"):
        lines.append(f"- 엔진/목적: **{best['engine']} / {best['objective']}**")
    if "distance_km" in best:
        lines.append(f"- 거리: **{best['distance_km']} km**")
    if "duration_min" in best:
        lines.append(f"- 시간: **{best['duration_min']} 분**")
    if "co2_g" in best:
        lines.append(f"- CO₂: **{best['co2_g']} g**")
    if (delta := payload.get("co2_saved_g")) is not None:
        pine_days = float(delta) / 18.0
        lines.append(
            f"\n절감 CO₂ {delta} g — 30년생 소나무 1그루 {pine_days:.1f}일치 흡수량."
        )
    lines.append("\n(LLM 생성 실패 — 템플릿 fallback)")
    return "\n".join(lines)
