"""Function-calling tool schemas for Gemini.

Schema syntax: Gemini accepts a subset of OpenAPI / JSON Schema. Property
types are STRING / NUMBER / INTEGER / BOOLEAN / ARRAY / OBJECT (uppercase).
"""

from __future__ import annotations

# Planner: returns ExecutionPlan
PLANNER_TOOL: dict = {
    "name": "create_execution_plan",
    "description": (
        "Decide the routing workflow shape based on the user's request. "
        "Choose mode (p2p/vrp), which engines to call, and whether to "
        "extract constraints from free text."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "enum": ["p2p", "vrp"],
                "description": (
                    "p2p = single origin/destination. vrp = multi-stop "
                    "delivery (depot + 2+ jobs)."
                ),
            },
            "engines": {
                "type": "ARRAY",
                "items": {"type": "STRING", "enum": ["kakao", "ors"]},
                "description": (
                    "Routing engines to call. Use 'kakao' for Korean "
                    "domestic with live traffic. Add 'ors' for benchmark."
                ),
            },
            "needs_constraint_extraction": {
                "type": "BOOLEAN",
                "description": (
                    "True if the user's text contains delivery notes, "
                    "time windows, access restrictions, or vehicle limits."
                ),
            },
            "needs_weight_composition": {
                "type": "BOOLEAN",
                "description": (
                    "True if the user expressed preferences (eco/fast/cheap). "
                    "False if balanced default is fine."
                ),
            },
            "alternatives_per_engine": {
                "type": "INTEGER",
                "description": "Number of alternative routes per engine (1-3).",
            },
        },
        "required": ["mode", "engines", "needs_constraint_extraction"],
    },
}


# Weight Composer: returns WeightSpec
WEIGHT_TOOL: dict = {
    "name": "compose_weights",
    "description": (
        "Convert the user's priorities into a weighted-sum objective for VRP. "
        "Weights must each be in [0,1] and SUM TO 1.0."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "distance": {
                "type": "NUMBER",
                "description": "Weight for total distance minimization (0-1).",
            },
            "duration": {
                "type": "NUMBER",
                "description": "Weight for total time minimization (0-1).",
            },
            "co2": {
                "type": "NUMBER",
                "description": "Weight for CO₂ emissions minimization (0-1).",
            },
            "rationale": {
                "type": "STRING",
                "description": "One-sentence Korean explanation of the chosen weights.",
            },
        },
        "required": ["distance", "duration", "co2", "rationale"],
    },
}


# Constraint Extractor: returns ConstraintBatch
CONSTRAINT_TOOL: dict = {
    "name": "extract_constraints",
    "description": (
        "Extract structured delivery-site constraints from free-text notes. "
        "Each constraint must reference a site_id supplied in the user's input."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "constraints": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "site_id": {
                            "type": "STRING",
                            "description": "Use only site IDs from the input.",
                        },
                        "type": {
                            "type": "STRING",
                            "enum": [
                                "time_window_exclusion",
                                "vehicle_dimension",
                                "access_note",
                                "contact_constraint",
                                "note",
                            ],
                        },
                        "range": {
                            "type": "STRING",
                            "description": "Time range in 'HH:MM-HH:MM' for time_window_exclusion.",
                        },
                        "value": {
                            "type": "STRING",
                            "description": "Concrete value (e.g., '2.1m', 'rear gate').",
                        },
                        "reason": {
                            "type": "STRING",
                            "description": "Why this constraint exists.",
                        },
                    },
                    "required": ["site_id", "type"],
                },
            }
        },
        "required": ["constraints"],
    },
}
