import pytest
from mcp.server.mcpserver import MCPServer

from gemini_pro_mcp import notebook
from gemini_pro_mcp.config import Settings
from gemini_pro_mcp.notebook import download_path


def text_of(result):
    content = result[0] if isinstance(result, tuple) else result
    if hasattr(content, "content"):
        content = content.content
    return content[0].text


class NoBrowser:
    def __init__(self, *args):
        raise AssertionError("opened the browser")


@pytest.fixture
def mcp(monkeypatch):
    monkeypatch.setattr(notebook, "Tab", NoBrowser)
    server = MCPServer("test")
    notebook.register(server, Settings.from_env())
    return server


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("notebook_create", {}),
        ("notebook_add_sources", {"notebook": "0123abcd-0123-4567-89ab-0123456789ab"}),
    ],
)
async def test_missing_files_fail_before_the_browser_opens(mcp, tmp_path, tool, args):
    files = [str(tmp_path / "missing.pdf")]
    out = text_of(await mcp.call_tool(tool, {**args, "files": files}))
    assert out.startswith("Error: Files not found")
    assert "missing.pdf" in out


def test_download_path_keeps_earlier_downloads(tmp_path):
    folder = tmp_path / "out"
    first = download_path(folder, "Overview.m4a")
    assert first == folder / "Overview.m4a"
    first.write_bytes(b"first")
    second = download_path(folder, "Overview.m4a")
    assert second == folder / "Overview-2.m4a"
    second.write_bytes(b"second")
    assert download_path(folder, "Overview.m4a") == folder / "Overview-3.m4a"


def test_download_path_ignores_folders_in_the_suggested_name(tmp_path):
    assert download_path(tmp_path, "../x/Overview.mp4") == tmp_path / "Overview.mp4"
    assert download_path(tmp_path, "") == tmp_path / "notebook-download"
