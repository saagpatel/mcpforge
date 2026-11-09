"""Author the fixed pagination corpus. No randomness or runtime-derived expectations.

Run from any directory: python scripts/gen_pagination_datasets.py
"""

import json
from pathlib import Path
from typing import Any

DESTINATION = Path(__file__).resolve().parents[1] / "src/mcpforge/pagination/datasets"
PATTERNS = ("cursor", "offset", "page_token")
SCENARIOS = (
    "stable",
    "insert-before-cursor",
    "insert-after-cursor",
    "delete-before-cursor",
    "delete-after-cursor",
    "delete-boundary-item",
    "expired-cursor",
    "version-bump",
)


def authored_datasets() -> list[dict[str, Any]]:
    """24 pattern/scenario combinations, 15 edges, and one invalid upstream."""
    datasets: list[dict[str, Any]] = []

    def add(pattern: str, scenario: str, items: list[dict], size: int, mutations: list) -> None:
        expect: str | dict[str, str] = "complete"
        if pattern == "offset" and scenario in {"delete-before-cursor", "delete-boundary-item"}:
            expect = {"status": "incomplete", "kind": "page_shifted"}
        elif pattern != "offset" and scenario == "expired-cursor":
            expect = {"status": "incomplete", "kind": "cursor_expired"}
        elif pattern == "page_token" and scenario == "version-bump":
            expect = {"status": "incomplete", "kind": "page_shifted"}
        elif scenario == "duplicate-id":
            expect = {"status": "failed", "kind": "page_shifted"}
        datasets.append(
            {
                "id": f"{len(datasets) + 1:02d}-{pattern}-{scenario}",
                "pattern": pattern,
                "items": items,
                "page_size": size,
                "mutations": mutations,
                "expect": expect,
            }
        )

    for pattern in PATTERNS:
        for scenario in SCENARIOS:
            mutation: dict[str, Any] | None = None
            if scenario.startswith("insert"):
                value = 15 if scenario == "insert-before-cursor" else 35
                mutation = {"op": "insert", "item": {"id": value, "order": value}}
            elif scenario.startswith("delete"):
                identity = {
                    "delete-before-cursor": 10,
                    "delete-after-cursor": 50,
                    "delete-boundary-item": 30,
                }[scenario]
                mutation = {"op": "delete", "id": identity}
            elif scenario == "expired-cursor":
                mutation = {"op": "expire_cursors"}
            elif scenario == "version-bump":
                mutation = {"op": "bump_version"}
            mutations = [{"after_page": 1, **mutation}] if mutation else []
            add(pattern, scenario, [{"id": n, "order": n} for n in range(10, 81, 10)], 3, mutations)

    for pattern in PATTERNS:
        add(pattern, "empty", [], 3, [])
        add(pattern, "single-page", [{"id": 1, "order": 1}], 3, [])
        add(pattern, "exact-page-multiple", [{"id": n, "order": n} for n in range(6)], 2, [])
        add(pattern, "page-size-one", [{"id": n, "order": n} for n in range(5)], 1, [])
        add(pattern, "tied-order-keys", [{"id": n, "order": n // 3} for n in range(9)], 2, [])
    add("cursor", "duplicate-id", [{"id": 1, "order": 1}, {"id": 1, "order": 1}], 3, [])
    assert len(datasets) == 40
    return datasets


def main() -> None:
    datasets = authored_datasets()
    expected_names = {f"{dataset['id']}.json" for dataset in datasets}
    # Never delete files on regeneration; unexpected names signal corpus drift.
    unexpected = {path.name for path in DESTINATION.glob("*.json")} - expected_names
    if unexpected:
        raise ValueError(f"unexpected dataset files: {sorted(unexpected)}")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    for dataset in datasets:
        (DESTINATION / f"{dataset['id']}.json").write_text(
            json.dumps(dataset, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
