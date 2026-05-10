"""Tests for the Safe Workspace File Reader MCP server."""

import json
import os
import tempfile
from pathlib import Path

import pytest

# We must set WORKSPACE_ROOT before importing server
_tmp_workspace = tempfile.mkdtemp()
os.environ["WORKSPACE_ROOT"] = _tmp_workspace

from fastmcp import Client  # noqa: E402
from server import mcp  # noqa: E402

WORKSPACE = Path(_tmp_workspace)


def _read_json_resource(result):
    """Decode FastMCP resource content into a JSON object."""
    if isinstance(result, list):
        return json.loads(result[0].text)
    return result.data if isinstance(result.data, dict) else json.loads(result.data)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_workspace():
    """Remove all files/dirs inside the workspace before each test."""
    # Tear down
    for item in list(WORKSPACE.iterdir()):
        if item.is_dir():
            import shutil

            shutil.rmtree(item)
        else:
            item.unlink()
    yield
    # Tear down again after test
    for item in list(WORKSPACE.iterdir()):
        if item.is_dir():
            import shutil

            shutil.rmtree(item)
        else:
            item.unlink()


def make_file(relative: str, content: str = "hello world", encoding: str = "utf-8") -> Path:
    """Helper: create a file inside the workspace."""
    p = WORKSPACE / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding=encoding)
    return p


def make_dir(relative: str) -> Path:
    """Helper: create a directory inside the workspace."""
    p = WORKSPACE / relative
    p.mkdir(parents=True, exist_ok=True)
    return p


# ===========================================================================
# list_files
# ===========================================================================


async def test_list_files_success_root_empty():
    async with Client(mcp) as client:
        result = await client.call_tool("list_files", {})
        assert result.data["total"] == 0
        assert result.data["entries"] == []


async def test_list_files_success_with_files():
    make_file("alpha.txt", "aaa")
    make_file("beta.txt", "bbb")
    async with Client(mcp) as client:
        result = await client.call_tool("list_files", {})
        assert result.data["total"] == 2
        names = {e["name"] for e in result.data["entries"]}
        assert "alpha.txt" in names
        assert "beta.txt" in names


async def test_list_files_subpath():
    make_dir("subdir")
    make_file("subdir/file1.txt", "x")
    make_file("subdir/file2.txt", "y")
    async with Client(mcp) as client:
        result = await client.call_tool("list_files", {"subpath": "subdir"})
        assert result.data["total"] == 2
        names = {e["name"] for e in result.data["entries"]}
        assert "file1.txt" in names
        assert "file2.txt" in names


async def test_list_files_recursive():
    make_file("a/b/deep.txt", "deep")
    make_file("a/shallow.txt", "shallow")
    async with Client(mcp) as client:
        result = await client.call_tool("list_files", {"recursive": True})
        names = {e["name"] for e in result.data["entries"]}
        assert "deep.txt" in names
        assert "shallow.txt" in names


async def test_list_files_hidden_excluded_by_default():
    make_file(".hidden_file", "secret")
    make_file("visible.txt", "visible")
    async with Client(mcp) as client:
        result = await client.call_tool("list_files", {})
        names = {e["name"] for e in result.data["entries"]}
        assert ".hidden_file" not in names
        assert "visible.txt" in names


async def test_list_files_hidden_included():
    make_file(".hidden_file", "secret")
    make_file("visible.txt", "visible")
    async with Client(mcp) as client:
        result = await client.call_tool("list_files", {"include_hidden": True})
        names = {e["name"] for e in result.data["entries"]}
        assert ".hidden_file" in names
        assert "visible.txt" in names


async def test_list_files_path_traversal():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)traversal|escape"):
            await client.call_tool("list_files", {"subpath": "../../etc"})


async def test_list_files_subpath_not_exist():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)does not exist|not found"):
            await client.call_tool("list_files", {"subpath": "nonexistent_dir"})


async def test_list_files_subpath_not_a_directory():
    make_file("myfile.txt", "content")
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)not a directory"):
            await client.call_tool("list_files", {"subpath": "myfile.txt"})


async def test_list_files_entries_have_expected_fields():
    make_file("check.txt", "data")
    async with Client(mcp) as client:
        result = await client.call_tool("list_files", {})
        entry = result.data["entries"][0]
        assert "name" in entry
        assert "relative_path" in entry
        assert "type" in entry
        assert "modified_at" in entry


# ===========================================================================
# read_file
# ===========================================================================


async def test_read_file_success():
    make_file("hello.txt", "Hello, World!")
    async with Client(mcp) as client:
        result = await client.call_tool("read_file", {"filepath": "hello.txt"})
        assert result.data["content"] == "Hello, World!"
        assert result.data["relative_path"] == "hello.txt"
        assert result.data["encoding"] == "utf-8"
        assert result.data["size_bytes"] == len(b"Hello, World!")


async def test_read_file_custom_encoding():
    content = "café"
    p = WORKSPACE / "latin.txt"
    p.write_bytes(content.encode("latin-1"))
    async with Client(mcp) as client:
        result = await client.call_tool(
            "read_file", {"filepath": "latin.txt", "encoding": "latin-1"}
        )
        assert result.data["content"] == content
        assert result.data["encoding"] == "latin-1"


async def test_read_file_path_traversal():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)traversal|escape"):
            await client.call_tool("read_file", {"filepath": "../../etc/passwd"})


async def test_read_file_not_found():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)not found|does not exist"):
            await client.call_tool("read_file", {"filepath": "ghost.txt"})


async def test_read_file_exceeds_max_bytes():
    make_file("big.txt", "x" * 200)
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)exceed|limit|max"):
            await client.call_tool("read_file", {"filepath": "big.txt", "max_bytes": 10})


async def test_read_file_points_to_directory():
    make_dir("mydir")
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)directory"):
            await client.call_tool("read_file", {"filepath": "mydir"})


async def test_read_file_invalid_encoding():
    # Write UTF-8 content with a multi-byte character, then try to read as ascii
    make_file("unicode.txt", "こんにちは")
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)encoding|not valid|decode"):
            await client.call_tool("read_file", {"filepath": "unicode.txt", "encoding": "ascii"})


async def test_read_file_returns_full_content():
    text = "line1\nline2\nline3\n"
    make_file("multiline.txt", text)
    async with Client(mcp) as client:
        result = await client.call_tool("read_file", {"filepath": "multiline.txt"})
        assert result.data["content"] == text


# ===========================================================================
# search_file_contents
# ===========================================================================


async def test_search_file_contents_success_plain():
    make_file("doc.txt", "foo bar\nbaz qux\nfoo again")
    async with Client(mcp) as client:
        result = await client.call_tool("search_file_contents", {"pattern": "foo"})
        assert result.data["total_matches"] == 2
        assert result.data["truncated"] is False
        assert result.data["pattern"] == "foo"
        lines = [m["line"] for m in result.data["matches"]]
        assert any("foo" in line for line in lines)


async def test_search_file_contents_no_match():
    make_file("doc.txt", "nothing here")
    async with Client(mcp) as client:
        result = await client.call_tool("search_file_contents", {"pattern": "zzznomatch"})
        assert result.data["total_matches"] == 0
        assert result.data["matches"] == []


async def test_search_file_contents_regex():
    make_file("code.py", "def foo():\n    pass\ndef bar():\n    pass")
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_file_contents",
            {"pattern": r"def \w+\(\):", "use_regex": True},
        )
        assert result.data["total_matches"] == 2
        assert result.data["use_regex"] is True


async def test_search_file_contents_case_insensitive():
    make_file("notes.txt", "Hello World\nhello world\nHELLO WORLD")
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_file_contents",
            {"pattern": "hello", "case_sensitive": False},
        )
        assert result.data["total_matches"] == 3
        assert result.data["case_sensitive"] is False


async def test_search_file_contents_case_sensitive():
    make_file("notes.txt", "Hello World\nhello world\nHELLO WORLD")
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_file_contents",
            {"pattern": "hello", "case_sensitive": True},
        )
        assert result.data["total_matches"] == 1


async def test_search_file_contents_file_glob():
    make_file("script.py", "import os\nprint('hello')")
    make_file("readme.txt", "hello from readme")
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_file_contents",
            {"pattern": "hello", "file_glob": "*.py"},
        )
        for match in result.data["matches"]:
            assert match["relative_path"].endswith(".py")


async def test_search_file_contents_max_results_truncation():
    # Create a file with many matching lines
    lines = "\n".join(f"match line {i}" for i in range(50))
    make_file("many.txt", lines)
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_file_contents",
            {"pattern": "match", "max_results": 10},
        )
        assert result.data["total_matches"] == 10
        assert result.data["truncated"] is True


async def test_search_file_contents_subpath():
    make_file("subdir/target.txt", "find me here")
    make_file("other.txt", "find me here too")
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_file_contents",
            {"pattern": "find me", "subpath": "subdir"},
        )
        for match in result.data["matches"]:
            assert "subdir" in match["relative_path"]


async def test_search_file_contents_path_traversal():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)traversal|escape"):
            await client.call_tool(
                "search_file_contents",
                {"pattern": "foo", "subpath": "../../etc"},
            )


async def test_search_file_contents_subpath_not_exist():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)does not exist|not found"):
            await client.call_tool(
                "search_file_contents",
                {"pattern": "foo", "subpath": "no_such_dir"},
            )


async def test_search_file_contents_invalid_regex():
    make_file("file.txt", "some content")
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)invalid|regex|pattern"):
            await client.call_tool(
                "search_file_contents",
                {"pattern": "[invalid(regex", "use_regex": True},
            )


async def test_search_file_contents_match_has_expected_fields():
    make_file("data.txt", "alpha\nbeta\nalpha again")
    async with Client(mcp) as client:
        result = await client.call_tool("search_file_contents", {"pattern": "alpha"})
        assert result.data["total_matches"] > 0
        match = result.data["matches"][0]
        assert "relative_path" in match
        assert "line_number" in match
        assert "line" in match


# ===========================================================================
# get_file_metadata
# ===========================================================================


async def test_get_file_metadata_success_file():
    make_file("info.txt", "some content")
    async with Client(mcp) as client:
        result = await client.call_tool("get_file_metadata", {"filepath": "info.txt"})
        assert result.data["name"] == "info.txt"
        assert result.data["type"] == "file"
        assert result.data["relative_path"] == "info.txt"
        assert result.data["size_bytes"] is not None
        assert "modified_at" in result.data
        assert "mode" in result.data


async def test_get_file_metadata_success_directory():
    make_dir("mysubdir")
    async with Client(mcp) as client:
        result = await client.call_tool("get_file_metadata", {"filepath": "mysubdir"})
        assert result.data["name"] == "mysubdir"
        assert result.data["type"] == "directory"
        assert result.data["size_bytes"] is None


async def test_get_file_metadata_path_traversal():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)traversal|escape"):
            await client.call_tool("get_file_metadata", {"filepath": "../../etc/passwd"})


async def test_get_file_metadata_not_found():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)not found|does not exist"):
            await client.call_tool("get_file_metadata", {"filepath": "ghost_file.txt"})


async def test_get_file_metadata_size_bytes_correct():
    content = "exactly this content"
    make_file("sized.txt", content)
    async with Client(mcp) as client:
        result = await client.call_tool("get_file_metadata", {"filepath": "sized.txt"})
        assert result.data["size_bytes"] == len(content.encode("utf-8"))


# ===========================================================================
# summarize_file_metadata
# ===========================================================================


async def test_summarize_file_metadata_success_empty():
    async with Client(mcp) as client:
        result = await client.call_tool("summarize_file_metadata", {})
        assert result.data["total_files"] == 0
        assert result.data["total_size_bytes"] == 0
        assert result.data["type_breakdown"] == []
        assert result.data["most_recently_modified"] == []


async def test_summarize_file_metadata_success_with_files():
    make_file("a.txt", "hello")
    make_file("b.txt", "world")
    make_file("c.py", "print('hi')")
    async with Client(mcp) as client:
        result = await client.call_tool("summarize_file_metadata", {})
        assert result.data["total_files"] == 3
        assert result.data["total_size_bytes"] > 0
        extensions = {tb["extension"] for tb in result.data["type_breakdown"]}
        assert ".txt" in extensions
        assert ".py" in extensions


async def test_summarize_file_metadata_subpath():
    make_file("sub/x.txt", "xxx")
    make_file("sub/y.txt", "yyy")
    make_file("root_only.txt", "rrr")
    async with Client(mcp) as client:
        result = await client.call_tool("summarize_file_metadata", {"subpath": "sub"})
        assert result.data["total_files"] == 2
        assert result.data["subpath"] == "sub"


async def test_summarize_file_metadata_top_n_recent():
    for i in range(10):
        make_file(f"file{i}.txt", f"content {i}")
    async with Client(mcp) as client:
        result = await client.call_tool("summarize_file_metadata", {"top_n_recent": 3})
        assert len(result.data["most_recently_modified"]) <= 3


async def test_summarize_file_metadata_type_breakdown_fields():
    make_file("doc.txt", "text")
    async with Client(mcp) as client:
        result = await client.call_tool("summarize_file_metadata", {})
        assert result.data["total_files"] == 1
        breakdown = result.data["type_breakdown"]
        assert len(breakdown) == 1
        entry = breakdown[0]
        assert "extension" in entry
        assert "count" in entry
        assert "total_size_bytes" in entry


async def test_summarize_file_metadata_path_traversal():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)traversal|escape"):
            await client.call_tool("summarize_file_metadata", {"subpath": "../../etc"})


async def test_summarize_file_metadata_subpath_not_exist():
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)does not exist|not found"):
            await client.call_tool("summarize_file_metadata", {"subpath": "no_such_subdir"})


async def test_summarize_file_metadata_subpath_not_a_directory():
    make_file("notadir.txt", "content")
    async with Client(mcp) as client:
        with pytest.raises(Exception, match="(?i)not a directory"):
            await client.call_tool("summarize_file_metadata", {"subpath": "notadir.txt"})


async def test_summarize_file_metadata_most_recently_modified_fields():
    make_file("recent.txt", "data")
    async with Client(mcp) as client:
        result = await client.call_tool("summarize_file_metadata", {})
        assert len(result.data["most_recently_modified"]) == 1
        rec = result.data["most_recently_modified"][0]
        assert "relative_path" in rec
        assert "size_bytes" in rec
        assert "modified_at" in rec


# ===========================================================================
# Resource: workspace://summary
# ===========================================================================


async def test_workspace_summary_resource_empty():
    async with Client(mcp) as client:
        result = await client.read_resource("workspace://summary")
        data = _read_json_resource(result)
        assert data["total_files"] == 0
        assert data["total_size_bytes"] == 0


async def test_workspace_summary_resource_with_files():
    make_file("r1.txt", "aaa")
    make_file("r2.py", "bbb")
    async with Client(mcp) as client:
        result = await client.read_resource("workspace://summary")
        data = _read_json_resource(result)
        assert data["total_files"] == 2
        assert "workspace_root" in data
        assert "type_breakdown" in data
        assert "most_recently_modified" in data


# ===========================================================================
# Prompt: review_file_safely
# ===========================================================================


async def test_review_file_safely_prompt_contains_filepath():
    async with Client(mcp) as client:
        result = await client.get_prompt("review_file_safely", {"filepath": "mycode.py"})
        # The prompt messages should reference the filepath
        prompt_text = str(result)
        assert "mycode.py" in prompt_text


async def test_review_file_safely_prompt_contains_safety_instructions():
    async with Client(mcp) as client:
        result = await client.get_prompt("review_file_safely", {"filepath": "anything.txt"})
        prompt_text = str(result)
        # Should contain safety-oriented language
        assert any(
            keyword in prompt_text.lower()
            for keyword in ["do not execute", "not execute", "do not suggest", "read_file"]
        )
