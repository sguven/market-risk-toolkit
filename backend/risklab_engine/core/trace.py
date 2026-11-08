"""Calculation trace: an ordered, serialisable record of how a number was produced.

Every RiskLab calculation returns a result *and* a trace so the UI can show "how was this
calculated" and the AI assistant can explain a result without recomputing anything.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidationLabel(str, Enum):
    """How far a feature is from a fully validated regulatory calculation (see docs/ARCHITECTURE.md §11)."""

    EDUCATIONAL = "educational"            # illustrates a concept; not a regulatory number
    SIMPLIFIED = "simplified"              # regulatory logic with explicit simplifications
    PARTIAL = "partial-regulatory"         # follows the Basel text for a sub-scope; gaps listed
    VALIDATED = "validated-regulatory"     # reproduces reference examples; validation record on file


@dataclass
class Step:
    step: int
    label: str
    output: str
    formula: str | None = None          # LaTeX
    inputs: dict[str, Any] = field(default_factory=dict)
    reference: str | None = None        # Basel paragraph, e.g. "MAR33.3"

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "label": self.label,
            "formula": self.formula,
            "inputs": _jsonable(self.inputs),
            "output": self.output,
            "reference": self.reference,
        }


@dataclass
class CalcTrace:
    steps: list[Step] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add(self, label: str, output: Any, *, formula: str | None = None,
            inputs: dict[str, Any] | None = None, reference: str | None = None) -> None:
        self.steps.append(Step(len(self.steps) + 1, label, _fmt(output), formula, inputs or {}, reference))

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def to_list(self) -> list[dict[str, Any]]:
        return [s.to_dict() for s in self.steps]


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        if abs(value) >= 1000:
            return f"{value:,.2f}"
        return f"{value:.6g}"
    return str(value)


def _jsonable(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if hasattr(v, "tolist"):
            v = v.tolist()
        if isinstance(v, float):
            v = round(v, 10)
        out[k] = v
    return out
