"""Script timing, mutation isolation, and snapshot behaviour."""

import pytest
from pydantic import ValidationError

from mcpforge.pagination.harness import MutatingUpstream

ROWS = [{"id": n, "order": n} for n in range(6)]


def test_harness_mutations_are_deterministic_and_between_requests():
    script = [
        {"after_page": 1, "op": "insert", "item": {"id": 9, "order": 9}},
        {"after_page": 1, "op": "delete", "id": 0},
        {"after_page": 2, "op": "expire_cursors"},
        {"after_page": 2, "op": "bump_version"},
    ]
    sources = [MutatingUpstream(ROWS, script) for _ in range(2)]
    for source in sources:
        assert source.fetch_offset(0, 2).items == ROWS[:2]
        assert source.items == ROWS
        source.fetch_offset(0, 2)
        assert source.items == ROWS[1:] + [{"id": 9, "order": 9}]
        assert source.generation == source.version == 0
        source.fetch_offset(0, 2)
        assert source.generation == source.version == 1
        source.fetch_offset(0, 2)
        assert source.generation == source.version == 1
    assert sources[0].items == sources[1].items
    assert sources[0].requests == sources[1].requests


def test_harness_snapshot_is_immutable_and_input_output_are_isolated():
    source = MutatingUpstream(ROWS)
    first = source.fetch_token(None, 2)
    source.delete(3)
    source.insert({"id": 10, "order": 10})
    second = source.fetch_token(first.next_token, 4)
    assert second.items == ROWS[2:]
    assert second.next_token is None
    exposed = source.items
    exposed[0]["order"] = -100
    first.items[0]["order"] = -200
    assert source.items[0]["order"] == ROWS[0]["order"]


@pytest.mark.parametrize(
    "mutation",
    [
        {"after_page": 0, "op": "expire_cursors"},
        {"after_page": 1, "op": "unknown"},
        {"after_page": 1, "op": "insert"},
        {"after_page": 1, "op": "delete"},
        {"after_page": 1, "op": "bump_version", "id": 1},
    ],
)
def test_harness_invalid_scripts_rejected(mutation):
    with pytest.raises(ValidationError):
        MutatingUpstream(ROWS, [mutation])
