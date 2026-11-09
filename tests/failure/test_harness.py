"""All failure modes are exercised by the three generated server handlers."""

import json
import shutil

import pytest

from mcpforge.failure.fixtures import load_upstreams, run_all_fixtures

SERVER_TYPES = ("python-single", "python-multi", "typescript")


def test_harness_node_is_required_for_typescript():
    if shutil.which("node") is None:
        pytest.fail("Node.js 22.6+ is required to run the TypeScript failure harness")


@pytest.mark.parametrize("server_type", SERVER_TYPES)
def test_harness_matches_expected_for_all_upstreams(server_type):
    outcomes = run_all_fixtures(server_type)
    assert len(outcomes) == 15
    assert {name: result for name, result in outcomes.items()} == {
        upstream["name"]: upstream["expect"] for upstream in load_upstreams()
    }


@pytest.mark.parametrize("mode", ("timeout", "malformed", "cancellation"))
def test_harness_mode_cases(mode):
    from mcpforge.failure.fixtures import run_python_fixture

    for upstream in load_upstreams():
        if upstream["mode"] == mode:
            assert run_python_fixture(upstream) == upstream["expect"]


def test_consistency_across_server_types():
    normalized = {server_type: run_all_fixtures(server_type) for server_type in SERVER_TYPES}
    assert normalized["python-single"] == normalized["python-multi"]
    assert normalized["python-single"] == normalized["typescript"]
    serialized = {
        server_type: json.dumps(results, sort_keys=True, separators=(",", ":"))
        for server_type, results in normalized.items()
    }
    assert len(set(serialized.values())) == 1
