# =============================================================================
# URTC-VISION-TOOL - vision_companion thermal inspection of components: inspection.py
# Copyright (C) 2026 JuanenRac (Electro Hobby 3D) <electrohobby3d@gmail.com>
# GPL-3.0-or-later - see LICENSE
# =============================================================================
# Compares the temperature of each component (a region found in the RGB image) with the profile that is
# expected for its kind: a joint that stayed cold after reflow, a part that runs too hot. The plan is a JSON
# file made by hand or by the placement step (the list of components with their regions and a profile of rules);
# the frame comes from the thermal sensor, from a saved frame or, for a test, from the synthetic generator.
# What is measured is the temperature of the surface the camera sees, not the temperature of the junction
# inside a package; the rules are the user's, and nothing here has been checked on a real board.
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .alignment import BoundingBox, RoiStats, analyze_rgb_roi

SCHEMA = 1
OK, COLD, HOT, NO_DATA = "ok", "cold", "hot", "no_data"
PASS, FAIL, INCOMPLETE = "pass", "fail", "incomplete"
_RULE_KEYS = {"expected_c", "tolerance_c", "min_c", "max_c", "min_rise_c", "max_rise_c"}
_PLAN_KEYS = {"schema", "profile", "components"}


class PlanError(ValueError):
    """The inspection plan is not usable."""


def _num(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise PlanError(f"{name} must be a finite number")
    return float(value)


@dataclass(frozen=True)
class Rule:
    """What a kind of component may read. Every field is optional; the ones that are set must all hold."""
    expected_c: float | None = None     # the temperature the surface should have...
    tolerance_c: float = 5.0            # ...within this many degrees
    min_c: float | None = None          # the mean must not be below
    max_c: float | None = None          # the hottest pixel must not be above
    min_rise_c: float | None = None     # the mean must be at least this far above the ambient (a joint that did not heat)
    max_rise_c: float | None = None     # the hottest pixel must not be further above the ambient than this


@dataclass(frozen=True)
class Component:
    ref: str
    kind: str
    roi: BoundingBox                    # in RGB pixels
    task: str = ""


@dataclass(frozen=True)
class Profile:
    name: str = "profile"
    ambient_c: float | None = None      # None: the median of the frame is taken as the ambient
    rules: dict[str, Rule] = field(default_factory=dict)


@dataclass(frozen=True)
class ComponentResult:
    ref: str
    kind: str
    task: str
    verdict: str
    reasons: tuple[str, ...]
    stats: RoiStats


@dataclass(frozen=True)
class Report:
    profile: str
    ambient_c: float
    overall: str
    results: tuple[ComponentResult, ...]


def plan_from_dict(data: Any) -> tuple[Profile, list[Component]]:
    if not isinstance(data, dict):
        raise PlanError("the plan must be a JSON object")
    unknown = set(data) - _PLAN_KEYS
    if unknown:
        raise PlanError(f"unknown key(s): {', '.join(sorted(unknown))}")
    if data.get("schema") != SCHEMA or isinstance(data.get("schema"), bool):
        raise PlanError(f"schema must be {SCHEMA}")
    raw_profile = data.get("profile")
    if not isinstance(raw_profile, dict):
        raise PlanError("profile must be an object")
    rules: dict[str, Rule] = {}
    for kind, raw in (raw_profile.get("rules") or {}).items():
        if not isinstance(raw, dict):
            raise PlanError(f"rule {kind!r} must be an object")
        extra = set(raw) - _RULE_KEYS
        if extra:
            raise PlanError(f"rule {kind!r}: unknown key(s): {', '.join(sorted(extra))}")
        values = {key: _num(value, f"rule {kind!r} {key}") for key, value in raw.items()}
        if values.get("tolerance_c", 1.0) <= 0:
            raise PlanError(f"rule {kind!r}: tolerance_c must be positive")
        rules[kind] = Rule(**values)
    ambient = raw_profile.get("ambient_c")
    profile = Profile(str(raw_profile.get("name", "profile")), None if ambient is None else _num(ambient, "ambient_c"), rules)
    components: list[Component] = []
    seen: set[str] = set()
    for item in data.get("components") or []:
        if not isinstance(item, dict) or not isinstance(item.get("ref"), str) or not item["ref"]:
            raise PlanError("each component needs a ref")
        if item["ref"] in seen:
            raise PlanError(f"component {item['ref']!r} appears twice")
        seen.add(item["ref"])
        roi = item.get("roi")
        if not isinstance(roi, list) or len(roi) != 4 or not all(isinstance(v, int) and not isinstance(v, bool) for v in roi):
            raise PlanError(f"component {item['ref']!r}: roi must be [x0, y0, x1, y1] in whole pixels")
        try:
            box = BoundingBox(*roi)
        except ValueError as error:
            raise PlanError(f"component {item['ref']!r}: {error}") from error
        kind = item.get("kind", "")
        if not isinstance(kind, str) or kind not in rules:
            raise PlanError(f"component {item['ref']!r}: kind {kind!r} has no rule in the profile")
        components.append(Component(item["ref"], kind, box, str(item.get("task", ""))))
    return profile, components


def _judge(stats: RoiStats, rule: Rule, ambient: float) -> tuple[str, tuple[str, ...]]:
    if stats.is_empty:
        return NO_DATA, ("no thermal data in the region",)
    cold: list[str] = []
    hot: list[str] = []
    if rule.expected_c is not None:
        if stats.mean_c < rule.expected_c - rule.tolerance_c:
            cold.append(f"mean {stats.mean_c:.1f}C is below the expected {rule.expected_c:.1f}C by more than {rule.tolerance_c:.1f}C")
        if stats.max_c > rule.expected_c + rule.tolerance_c:
            hot.append(f"hottest pixel {stats.max_c:.1f}C is above the expected {rule.expected_c:.1f}C by more than {rule.tolerance_c:.1f}C")
    if rule.min_c is not None and stats.mean_c < rule.min_c:
        cold.append(f"mean {stats.mean_c:.1f}C is below the minimum {rule.min_c:.1f}C")
    if rule.max_c is not None and stats.max_c > rule.max_c:
        hot.append(f"hottest pixel {stats.max_c:.1f}C is above the maximum {rule.max_c:.1f}C")
    if rule.min_rise_c is not None and stats.mean_c - ambient < rule.min_rise_c:
        cold.append(f"only {stats.mean_c - ambient:.1f}C above the ambient, at least {rule.min_rise_c:.1f}C expected")
    if rule.max_rise_c is not None and stats.max_c - ambient > rule.max_rise_c:
        hot.append(f"{stats.max_c - ambient:.1f}C above the ambient, at most {rule.max_rise_c:.1f}C allowed")
    if hot:
        return HOT, tuple(hot + cold)
    if cold:
        return COLD, tuple(cold)
    return OK, ()


def inspect(thermal: np.ndarray, components: list[Component], profile: Profile, rgb_width: int, rgb_height: int) -> Report:
    """Measure every component and judge it by the rule of its kind. A region without thermal data is reported as such, never as ok."""
    finite = thermal[np.isfinite(thermal)]
    if profile.ambient_c is not None:
        ambient = profile.ambient_c
    else:
        ambient = float(np.median(finite)) if finite.size else math.nan
    results = []
    for component in components:
        stats = analyze_rgb_roi(thermal, component.roi, rgb_width=rgb_width, rgb_height=rgb_height)
        verdict, reasons = _judge(stats, profile.rules[component.kind], ambient)
        results.append(ComponentResult(component.ref, component.kind, component.task, verdict, reasons, stats))
    if any(r.verdict in (COLD, HOT) for r in results):
        overall = FAIL
    elif any(r.verdict == NO_DATA for r in results) or not results:
        overall = INCOMPLETE
    else:
        overall = PASS
    return Report(profile.name, ambient, overall, tuple(results))


def _clean(value: float) -> float | None:
    return None if isinstance(value, float) and not math.isfinite(value) else value


def report_to_dict(report: Report) -> dict[str, Any]:
    return {
        "schema": SCHEMA, "profile": report.profile, "ambient_c": _clean(report.ambient_c), "overall": report.overall,
        "components": [
            {"ref": r.ref, "kind": r.kind, "task": r.task, "verdict": r.verdict, "reasons": list(r.reasons),
             "min_c": _clean(r.stats.min_c), "max_c": _clean(r.stats.max_c), "mean_c": _clean(r.stats.mean_c),
             "p95_c": _clean(r.stats.p95_c), "pixels": r.stats.pixel_count, "invalid_pixels": r.stats.invalid_pixel_count}
            for r in report.results
        ],
    }
