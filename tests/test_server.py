import dataclasses

from gemini_pro_mcp.config import Settings, load_env_file
from gemini_pro_mcp.flow.browser import FlowError
from gemini_pro_mcp.flow.tools import failure
from gemini_pro_mcp.server import build_server

BASE = {
    "gemini_ask",
    "gemini_research",
    "gemini_models",
    "video_generate",
    "video_edit",
    "video_check",
    "image_generate",
}
FLOW = {"flow_status", "flow_generate", "flow_approve", "flow_reject", "flow_collect"}


async def tool_names(settings):
    return {tool.name for tool in await build_server(settings).list_tools()}


async def test_flow_tools_only_when_enabled():
    settings = Settings.from_env()
    assert await tool_names(dataclasses.replace(settings, flow_enabled=False)) == BASE
    assert await tool_names(dataclasses.replace(settings, flow_enabled=True)) == BASE | FLOW


async def test_paid_tools_say_so():
    server = build_server(dataclasses.replace(Settings.from_env(), flow_enabled=True))
    tools = {tool.name: tool.description or "" for tool in await server.list_tools()}
    for name in ("video_generate", "video_edit", "image_generate"):
        assert "COSTS MONEY" in tools[name]
    assert "SPENDS FLOW CREDITS" in tools["flow_approve"]
    assert "Does NOT spend credits" in tools["flow_generate"]


def test_env_file_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("GEMINI_PRO_TEST_A=from-file\n# comment\nGEMINI_PRO_TEST_B='quoted'\n")
    monkeypatch.setenv("GEMINI_PRO_TEST_A", "from-env")
    monkeypatch.delenv("GEMINI_PRO_TEST_B", raising=False)
    load_env_file(env)
    import os

    assert os.environ["GEMINI_PRO_TEST_A"] == "from-env"
    assert os.environ["GEMINI_PRO_TEST_B"] == "quoted"


def test_flow_failure_messages():
    assert failure(FlowError("Not signed in")) == "Error: Not signed in"
    message = failure(TimeoutError("Locator.click: Timeout 30000ms exceeded.\ncall log..."))
    assert message.startswith("Error (TimeoutError): Locator.click")
    assert "issues" in message
