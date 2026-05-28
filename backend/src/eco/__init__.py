"""Eco-Analyzer: CO₂ calculation + Min-Max normalization for multi-objective scoring."""

from src.eco.calculator import EmissionCalculator, RouteEmission, SegmentEmission
from src.eco.factors import EcoFactorBook, EmissionFactorView, SpeedBinView
from src.eco.normalizer import (
    NormalizedRoute,
    Weights,
    rank_recommend,
    score_candidates,
)

__all__ = [
    "EmissionCalculator",
    "RouteEmission",
    "SegmentEmission",
    "EcoFactorBook",
    "EmissionFactorView",
    "SpeedBinView",
    "NormalizedRoute",
    "Weights",
    "rank_recommend",
    "score_candidates",
]
