"""Contracts shared by all NCS models.

A model result is an estimate plus provenance, uncertainty, and validity scope.
It is never a statement of geological ground truth by itself.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceRef:
    dataset: str
    path: str
    row: int | None = None
    page: int | None = None
    wellbore: str | None = None
    depth_md: float | None = None
    extraction: str = "direct"
    confidence: str = "measured"


@dataclass
class Prediction:
    target: str
    value: float
    unit: str
    lower90: float | None = None
    upper90: float | None = None
    model_version: str = "unversioned"
    modality: tuple[str, ...] = ()
    evidence: list[SourceRef] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    in_scope: bool = True

    def json(self) -> dict[str, Any]:
        return {**asdict(self), "evidence": [asdict(x) for x in self.evidence]}


@dataclass(frozen=True)
class ModalityBatch:
    """One entity-batched modality. Mask=1 means a measured local value."""

    entity: tuple[str, ...]
    values: Any
    mask: Any
    source: tuple[SourceRef, ...]
    name: str


@dataclass(frozen=True)
class SplitPolicy:
    name: str
    block_km: float | None
    group: str
    seed: int
    hidden_test_used: bool = False

    def json(self) -> dict[str, Any]:
        return asdict(self)
