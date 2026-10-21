import dataclasses

import pytest
from mcp.server.mcpserver import MCPServer

from gemini_pro_mcp import agy, jules
from gemini_pro_mcp.config import Settings


def text_of(result):
    content = result[0] if isinstance(result, tuple) else result
    if hasattr(content, "content"):
        content = content.content
    return content[0].text


@pytest.fixture
def server(monkeypatch):
    calls = []

    async def fake_call(method, path, body=None, params=None):
        calls.append((method, path, body, params))
        if path == "sessions" and method == "POST":
            return {"name": "sessions/123", "title": "Fix login"}
        if path == "sessions/123":
            return {
                "title": "Fix login",
                "state": "COMPLETED",
                "outputs": [
                    {"pullRequest": {"url": "https://github.com/o/r/pull/7", "title": "Fix"}}
                ],
            }
        if path == "sessions/123/activities":
            return {
                "activities": [
                    {
                        "createTime": "2026-10-21T10:00:00Z",
                        "planGenerated": {"plan": {"steps": [{"title": "Read code"}]}},
                    },
                    {"createTime": "2026-10-21T10:05:00Z", "sessionCompleted": {}},
                ]
            }
        return {}

    monkeypatch.setattr(jules, "call", fake_call)
    mcp = MCPServer("test")
    jules.register(mcp, Settings.from_env())
    return mcp, calls


async def test_jules_start_builds_the_session(server):
    mcp, calls = server
    out = text_of(
        await mcp.call_tool(
            "jules_start", {"prompt": "Fix login", "repo": "github/o/r", "create_pr": True}
        )
    )
    assert "sessions" not in out.split("\n")[0] or "123" in out
    method, path, body, _ = calls[0]
    assert (method, path) == ("POST", "sessions")
    assert body["sourceContext"]["source"] == "sources/github/o/r"
    assert body["sourceContext"]["githubRepoContext"]["startingBranch"] == "main"
    assert body["automationMode"] == "AUTO_CREATE_PR"


async def test_jules_status_shows_pr_and_activity(server):
    mcp, _ = server
    out = text_of(await mcp.call_tool("jules_status", {"session": "sessions/123"}))
    assert "COMPLETED" in out
    assert "https://github.com/o/r/pull/7" in out
    assert "planGenerated: Read code" in out


def test_jules_needs_a_key(monkeypatch):
    monkeypatch.delenv("JULES_API_KEY", raising=False)
    with pytest.raises(jules.JulesError, match="jules.google.com/settings"):
        jules.key()


def test_gemini_code_edits_with_accept_edits_mode():
    args = agy.build_args("agy", "fix it", mode="accept-edits", agent="reviewer")
    assert args[args.index("--mode") + 1] == "accept-edits"
    assert args[args.index("--agent") + 1] == "reviewer"
    assert "--sandbox" in args


async def test_gemini_code_runs_in_the_folder(tmp_path, monkeypatch):
    seen = {}

    async def fake_run(args, cwd, timeout):
        seen["args"], seen["cwd"] = args, cwd
        return '{"status": "SUCCESS", "response": "changed calc.py"}'

    monkeypatch.setattr(agy, "run_agy", fake_run)
    mcp = MCPServer("test")
    agy.register(mcp, dataclasses.replace(Settings.from_env(), agy_path="agy"))
    out = text_of(await mcp.call_tool("gemini_code", {"task": "fix", "folder": str(tmp_path)}))
    assert "changed calc.py" in out
    assert seen["cwd"] == tmp_path.resolve()
    assert seen["args"][seen["args"].index("--mode") + 1] == "accept-edits"
