"""Domain models for PRISMA 2020 flow presentation model (v0.6.1 Slice 3).

Strictly separated presentation-neutral layer between authoritative PRISMA
metrics and concrete renderers (SVG, PDF). Carries zero layout coordinates or
persistence bindings.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PrismaStage = Literal["identification", "screening_tasft", "included"]


class PrismaFlowNode(BaseModel):
    """Presentation-neutral node in the PRISMA 2020 flow model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str
    stage: PrismaStage
    label_key: str
    values: dict[str, int]
    annotations: dict[str, str] = Field(default_factory=dict)


class PrismaFlowEdge(BaseModel):
    """Directed connection between flow nodes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_node: str
    to_node: str


class PrismaFlowMetadata(BaseModel):
    """Provenance and audit metadata for the PRISMA flow model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    project_title: str
    protocol_version: str | None = None
    application_version: str
    generated_at: str
    counts_echo: dict[str, int] = Field(default_factory=dict)


class PrismaFlowModel(BaseModel):
    """Complete presentation-neutral PRISMA 2020 flow model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str
    metadata: PrismaFlowMetadata
    nodes: list[PrismaFlowNode]
    edges: list[PrismaFlowEdge]
    removed: dict[str, int] = Field(default_factory=dict)
