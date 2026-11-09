"""Packaged deterministic datasets for tests and future examples."""

import json
from importlib.resources import files
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mcpforge.pagination.adapter import Item, PaginationKind, Pattern
from mcpforge.pagination.harness import Mutation


class ExpectedFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["incomplete", "failed"]
    kind: PaginationKind


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    pattern: Pattern
    items: list[Item]
    page_size: int = Field(ge=1)
    mutations: list[Mutation]
    expect: Literal["complete"] | ExpectedFailure


def load_datasets() -> list[Dataset]:
    """Load fixtures from package resources, including installed wheels."""
    resources = sorted(
        (entry for entry in files(__package__).iterdir() if entry.name.endswith(".json")),
        key=lambda entry: entry.name,
    )
    return [
        Dataset.model_validate(json.loads(entry.read_text(encoding="utf-8"))) for entry in resources
    ]


def count_datasets() -> int:
    return sum(entry.name.endswith(".json") for entry in files(__package__).iterdir())
