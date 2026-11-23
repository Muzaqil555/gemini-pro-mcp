from mcp.server.mcpserver import MCPServer

from gemini_pro_mcp import google_web
from gemini_pro_mcp.config import Settings


def text_of(result):
    content = result[0] if isinstance(result, tuple) else result
    if hasattr(content, "content"):
        content = content.content
    return content[0].text


class NoBrowser:
    def __init__(self, *args):
        raise AssertionError("opened the browser")


async def test_gemini_app_reports_missing_files_before_opening_the_browser(tmp_path, monkeypatch):
    monkeypatch.setattr(google_web, "Tab", NoBrowser)
    mcp = MCPServer("test")
    google_web.register(mcp, Settings.from_env())
    files = [str(tmp_path / "missing.png")]
    out = text_of(await mcp.call_tool("gemini_app", {"prompt": "Describe it", "files": files}))
    assert out.startswith("Error: Files not found")
    assert "missing.png" in out


async def test_gemini_app_result_refuses_urls_of_other_sites(monkeypatch):
    monkeypatch.setattr(google_web, "Tab", NoBrowser)
    mcp = MCPServer("test")
    google_web.register(mcp, Settings.from_env())
    url = "https://docs.google.com/document/d/abc"
    out = text_of(await mcp.call_tool("gemini_app_result", {"chat_url": url}))
    assert out.startswith("Error: chat_url must be a Gemini app chat"), out
