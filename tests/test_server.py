import dataclasses

from gemini_pro_mcp.config import ASK_FIRST, PRE_APPROVED, Settings, load_env_file
from gemini_pro_mcp.flow.browser import FlowError
from gemini_pro_mcp.flow.tools import clip_lengths, failure, parse_shots
from gemini_pro_mcp.server import build_server

BASE = {
    "gemini_ask",
    "gemini_research",
    "gemini_models",
    "video_generate",
    "video_edit",
    "video_check",
    "image_generate",
    "video_stitch",
}
FLOW = {
    "flow_status",
    "flow_generate",
    "flow_approve",
    "flow_reject",
    "flow_collect",
    "flow_make_video",
    "flow_job",
    "flow_tools",
    "flow_open_tool",
    "flow_page",
    "flow_act",
}


async def tool_names(settings):
    return {tool.name for tool in await build_server(settings).list_tools()}


async def test_flow_tools_only_when_enabled():
    settings = Settings.from_env()
    assert await tool_names(dataclasses.replace(settings, flow_enabled=False)) == BASE
    assert await tool_names(dataclasses.replace(settings, flow_enabled=True)) == BASE | FLOW


PAID = ("video_generate", "video_edit", "image_generate", "flow_approve", "flow_generate")


async def descriptions(**changes):
    settings = dataclasses.replace(Settings.from_env(), flow_enabled=True, **changes)
    return {tool.name: tool.description or "" for tool in await build_server(settings).list_tools()}


async def test_paid_tools_say_so_and_ask_by_default():
    tools = await descriptions()
    for name in ("video_generate", "video_edit", "image_generate"):
        assert "COSTS MONEY" in tools[name]
    assert "SPENDS FLOW CREDITS" in tools["flow_approve"]
    assert "SPENDS FLOW CREDITS" in tools["flow_make_video"]
    for name in (*PAID, "flow_make_video"):
        assert ASK_FIRST in tools[name], name


async def test_pre_approved_tools_do_not_ask():
    tools = await descriptions(auto_approve=True)
    for name in (*PAID, "flow_make_video"):
        assert ASK_FIRST not in tools[name] and PRE_APPROVED in tools[name], name


def test_clip_lengths():
    assert clip_lengths(120) == [8] * 15
    assert clip_lengths(10) == [8, 4]
    assert clip_lengths(14) == [8, 8]
    assert clip_lengths(3) == [4]


def test_parse_shots():
    text = 'Sure:\n```json\n["a red tram", "the tram stops"]\n```'
    assert parse_shots(text, 2) == ["a red tram", "the tram stops"]
    assert parse_shots(text, 3) is None
    assert parse_shots("no json", 1) is None


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
