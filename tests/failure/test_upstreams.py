"""The packaged upstream catalog stays complete and data driven."""

from collections import Counter

from mcpforge.failure.fixtures import load_upstreams


def test_upstreams_have_fifteen_synthetic_scenarios():
    upstreams = load_upstreams()
    assert len(upstreams) == 15
    assert Counter(upstream["mode"] for upstream in upstreams) == {
        "timeout": 5,
        "malformed": 5,
        "cancellation": 5,
    }
    for upstream in upstreams:
        assert upstream["name"]
        assert upstream["mode"] in {"timeout", "malformed", "cancellation"}
        assert set(upstream["contract"]) == {"retryable", "partial_result_allowed"}
        assert set(upstream["expect"]) == {"status", "failure", "items"}
        assert isinstance(upstream["response_schema"], dict)
        assert isinstance(upstream["script"], list)


def test_upstreams_cover_every_contract_combination():
    combinations = {
        (scenario["contract"]["retryable"], scenario["contract"]["partial_result_allowed"])
        for scenario in load_upstreams()
    }
    assert combinations == {(False, False), (False, True), (True, False), (True, True)}
