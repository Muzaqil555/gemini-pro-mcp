import itertools

from mcp.server.mcpserver import MCPServer

from gemini_pro_mcp import notebook
from gemini_pro_mcp.config import Settings


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
