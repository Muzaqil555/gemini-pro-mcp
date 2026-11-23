import itertools

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
    with download_path(folder, "Overview.m4a") as first:
        with download_path(folder, "Overview.m4a") as second:
            assert first == folder / "Overview.m4a"
            assert second == folder / "Overview-2.m4a"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
    with download_path(folder, "Overview.m4a") as third:
        assert third == folder / "Overview-3.m4a"


def test_download_path_ignores_folders_in_the_suggested_name(tmp_path):
    with download_path(tmp_path, "../x/Overview.mp4") as path:
        assert path == tmp_path / "Overview.mp4"
    with download_path(tmp_path, "") as path:
        assert path == tmp_path / "notebook-download"


class StreamingPage:
    """A notebook whose answer is still being written on every check."""

    def __init__(self):
        self.calls = 0

    def locator(self, selector):
        return self

    @property
    def first(self):
        return self

    async def fill(self, text):
        pass

    async def press(self, key):
        pass

    async def wait_for_timeout(self, ms):
        pass

    async def evaluate(self, script):
        self.calls += 1
        if self.calls == 1:
            return {"count": 0, "last": ""}
        return {"count": 1, "last": "The answer " + "is long " * self.calls}


class FakeTab:
    def __init__(self, settings, host):
        self.page = StreamingPage()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    async def goto(self, url, settle_ms=0):
        pass


async def test_ask_says_when_the_answer_is_cut_off(monkeypatch, tmp_path):
    monkeypatch.setattr(notebook, "Tab", FakeTab)
    clock = itertools.count(0, 10)
    monkeypatch.setattr(notebook.time, "monotonic", lambda: next(clock))
    mcp = MCPServer("test")
    settings = Settings(
        output_dir=tmp_path,
        agy_path=None,
        agy_model=None,
        agy_timeout=1,
        flow_enabled=True,
        flow_profile_dir=tmp_path,
        flow_cdp_port=9,
        flow_project=None,
    )
    notebook.register(mcp, settings)
    result = await mcp.call_tool(
        "notebook_ask", {"notebook": "12345678-1234-1234-1234-123456789abc", "question": "Why?"}
    )
    content = result[0] if isinstance(result, tuple) else result
    text = (content.content if hasattr(content, "content") else content)[0].text
    assert text.startswith("The answer is long")
    assert "still being written" in text
