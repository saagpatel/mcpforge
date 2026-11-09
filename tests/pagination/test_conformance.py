"""MCP pagination 2025-06-18 rules supplied in the packet."""

import pytest

from mcpforge.pagination import CursorCodec, InvalidCursorError
from mcpforge.pagination.harness import DEMO_KEY, MutatingUpstream


@pytest.mark.parametrize("pattern", ["cursor", "offset", "page_token"])
def test_conformance_opaque_cursors_and_absent_next_cursor_on_last_page(pattern):
    rows = [{"id": n, "order": n} for n in range(6)]
    source = MutatingUpstream(rows)
    adapter = source.adapter(pattern, 2)
    collected = []
    for number in range(3):
        page = adapter.fetch_page(adapter.initial_state)
        response = page.to_mcp(adapter)
        collected.extend(response["items"])
        if number == 2:
            assert "nextCursor" not in response
            assert adapter.next_state(page) is None
        else:
            cursor = response["nextCursor"]
            assert isinstance(cursor, str)
            for field in ("version", "position", "configuration", "after", "offset", "token"):
                assert field not in cursor
            adapter = source.adapter(pattern, 2, resume_cursor=cursor)
    assert collected == rows


@pytest.mark.parametrize("pattern", ["cursor", "offset", "page_token"])
def test_conformance_empty_page_has_no_next_cursor(pattern):
    adapter = MutatingUpstream([]).adapter(pattern, 2)
    assert adapter.fetch_page(adapter.initial_state).to_mcp(adapter) == {"items": []}


@pytest.mark.parametrize(
    "invalid", ["", "garbage", ".", "e30.tag", "é.é", "a.b.c", "a" * 65537, None]
)
def test_conformance_invalid_cursor_maps_to_invalid_params(invalid):
    with pytest.raises(InvalidCursorError) as raised:
        CursorCodec(DEMO_KEY).decode(invalid)
    assert raised.value.to_jsonrpc_error() == {
        "code": -32602,
        "message": "Invalid params: invalid pagination cursor",
    }


def test_conformance_tamper_wrong_version_and_another_session_key_rejected():
    codec = CursorCodec(DEMO_KEY)
    valid = codec.encode({"offset": 7})
    body, tag = valid.split(".")
    wrong_version = CursorCodec(DEMO_KEY)
    wrong_version.version = 2
    invalids = [
        ("A" if body[0] != "A" else "B") + body[1:] + "." + tag,
        body + "." + ("A" if tag[0] != "A" else "B") + tag[1:],
        wrong_version.encode({"offset": 7}),
        CursorCodec(b"another-session-key").encode({"offset": 7}),
        body + "=." + tag,
    ]
    assert codec.decode(valid) == {"offset": 7}
    for invalid in invalids:
        with pytest.raises(InvalidCursorError) as raised:
            codec.decode(invalid)
        assert raised.value.code == -32602


def test_conformance_cursor_is_bound_to_adapter_and_configuration():
    source = MutatingUpstream([{"id": n, "order": n} for n in range(4)])
    adapter = source.adapter("cursor", 2)
    cursor = adapter.fetch_page(adapter.initial_state).to_mcp(adapter)["nextCursor"]
    for pattern, size in [("offset", 2), ("page_token", 2), ("cursor", 3)]:
        with pytest.raises(InvalidCursorError):
            source.adapter(pattern, size, resume_cursor=cursor)


@pytest.mark.parametrize(
    "pattern,position",
    [
        ("cursor", {"after": [1]}),
        ("cursor", {"generation": "bad"}),
        ("offset", {"offset": 10}),
        ("offset", {"offset": -1}),
        ("offset", {"offset": 1, "last_item": {}}),
        ("page_token", {"token": 12}),
        ("page_token", {"token": "next"}),
        ("page_token", {"version": 1}),
        ("page_token", {"unexpected": 1}),
    ],
)
def test_conformance_signed_but_invalid_adapter_state(pattern, position):
    source = MutatingUpstream([])
    adapter = source.adapter(pattern, 2)
    envelope = adapter.codec.decode(adapter.encode_state(adapter.initial_state))
    envelope["position"] = position
    cursor = adapter.codec.encode(envelope)
    with pytest.raises(InvalidCursorError) as raised:
        source.adapter(pattern, 2, resume_cursor=cursor)
    assert raised.value.code == -32602


@pytest.mark.parametrize("pattern", ["cursor", "offset", "page_token"])
@pytest.mark.parametrize("boundary", [[1], [1, 2, 3], [True, 1], [{}, 1], [None, 1]])
def test_conformance_invalid_resume_boundary_maps_to_invalid_params(pattern, boundary):
    source = MutatingUpstream([])
    adapter = source.adapter(pattern, 2)
    envelope = adapter.codec.decode(adapter.encode_state(adapter.initial_state))
    envelope["position"] = {"boundary": boundary}
    cursor = adapter.codec.encode(envelope)
    with pytest.raises(InvalidCursorError) as raised:
        source.adapter(pattern, 2, resume_cursor=cursor)
    assert raised.value.code == -32602
