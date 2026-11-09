"""Independent correctness oracle over all forty authored mutation datasets."""

import json
from pathlib import Path
from runpy import run_path

import pytest

from mcpforge.contracts import FailureContract
from mcpforge.pagination import traverse
from mcpforge.pagination.datasets import count_datasets, load_datasets
from mcpforge.pagination.harness import MutatingUpstream

DATASETS = load_datasets()
ALLOW_PARTIAL = FailureContract(retryable=True, partial_result_allowed=True)


def assert_ordered_unique(items):
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids))
    keys = [(item["order"], item["id"]) for item in items]
    assert keys == sorted(keys)


@pytest.mark.parametrize("dataset", DATASETS, ids=lambda dataset: dataset.id)
def test_fixtures_patterns_oracle(dataset):
    source = MutatingUpstream(dataset.items, dataset.mutations)
    initial = source.items
    result = traverse(source.adapter(dataset.pattern, dataset.page_size), ALLOW_PARTIAL, 100)
    assert_ordered_unique(result.items)
    if dataset.expect == "complete":
        assert result.outcome.status == "complete"
        assert result.outcome.failure is None
        assert result.resume_cursor is None
        common_ids = {item["id"] for item in initial} & {item["id"] for item in source.items}
        assert common_ids <= {item["id"] for item in result.items}
    else:
        assert result.outcome.status == dataset.expect.status
        assert result.outcome.failure.kind == dataset.expect.kind
        assert result.outcome.failure.partial_result == (dataset.expect.status == "incomplete")


def test_fixtures_count_coverage_and_reproducibility():
    assert len(DATASETS) == count_datasets() == 40
    assert len({dataset.id for dataset in DATASETS}) == 40
    scenarios = {
        "stable",
        "insert-before-cursor",
        "insert-after-cursor",
        "delete-before-cursor",
        "delete-after-cursor",
        "delete-boundary-item",
        "expired-cursor",
        "version-bump",
        "empty",
        "single-page",
        "exact-page-multiple",
        "page-size-one",
        "tied-order-keys",
    }
    for pattern in ("cursor", "offset", "page_token"):
        actual = {
            dataset.id.split(f"-{pattern}-", 1)[1]
            for dataset in DATASETS
            if dataset.pattern == pattern
        }
        assert scenarios <= actual
    root = Path(__file__).resolve().parents[2]
    authored = run_path(str(root / "scripts/gen_pagination_datasets.py"))["authored_datasets"]()
    fixture_dir = root / "src/mcpforge/pagination/datasets"
    for dataset in authored:
        assert (fixture_dir / f"{dataset['id']}.json").read_text() == json.dumps(
            dataset, indent=2
        ) + "\n"


@pytest.mark.parametrize(
    "dataset", [d for d in DATASETS if d.expect != "complete"], ids=lambda d: d.id
)
def test_fixtures_incomplete_contract_disallows_partial(dataset):
    source = MutatingUpstream(dataset.items, dataset.mutations)
    result = traverse(
        source.adapter(dataset.pattern, dataset.page_size),
        FailureContract(retryable=False, partial_result_allowed=False),
        100,
    )
    assert result.outcome.status == "failed"
    assert result.items == []
    assert result.outcome.failure.kind == dataset.expect.kind
    assert not result.outcome.failure.retryable
    assert not result.outcome.failure.partial_result
