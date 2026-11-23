import dataclasses

import httpx
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


async def test_jules_status_reads_every_activity_page(monkeypatch):
    async def fake_call(method, path, body=None, params=None):
        if path == "sessions/9":
            return {"title": "Long task", "state": "IN_PROGRESS"}
        if params.get("pageToken") is None:
            first = [{"progressUpdated": {"title": f"step {i}"}} for i in range(100)]
            return {"activities": first, "nextPageToken": "p2"}
        return {"activities": [{"progressUpdated": {"title": "latest step"}}]}

    monkeypatch.setattr(jules, "call", fake_call)
    mcp = MCPServer("test")
    jules.register(mcp, Settings.from_env())
    out = text_of(await mcp.call_tool("jules_status", {"session": "9", "activities": 2}))
    assert out.splitlines()[-2:] == [
        "-  progressUpdated: step 99",
        "-  progressUpdated: latest step",
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"error": {"code": 400, "message": "Invalid source"}},
        [{"error": {"code": 400, "message": "Invalid source"}}],
        ["Invalid source"],
    ],
)
async def test_call_explains_api_errors_of_any_shape(monkeypatch, body):
    monkeypatch.setenv("JULES_API_KEY", "test")
    transport = httpx.MockTransport(lambda request: httpx.Response(400, json=body))
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        jules.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw)
    )
    with pytest.raises(jules.JulesError, match="Jules API 400: .*Invalid source"):
        await jules.call("GET", "sessions")


@pytest.mark.parametrize(
    "value",
    [
        "123",
        "sessions/123",
        "https://jules.google.com/session/123",
        "https://jules.google.com/session/123/",
        "https://jules.google.com/session/123?tab=plan",
        " https://jules.google.com/session/123#activity\n",
    ],
)
def test_session_id_accepts_ids_names_and_web_links(value):
    assert jules.session_id(value) == "123"


async def test_jules_status_with_zero_activities_shows_none(server):
    mcp, _ = server
    out = text_of(await mcp.call_tool("jules_status", {"session": "123", "activities": 0}))
    assert "COMPLETED" in out
    assert "Recent activity" not in out


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
        return '{"status": "SUCCESS", "response": "changed calc.py"}', ""

    monkeypatch.setattr(agy, "run_agy_capture", fake_run)
    mcp = MCPServer("test")
    agy.register(mcp, dataclasses.replace(Settings.from_env(), agy_path="agy"))
    out = text_of(await mcp.call_tool("gemini_code", {"task": "fix", "folder": str(tmp_path)}))
    assert "changed calc.py" in out
    assert seen["cwd"] == tmp_path.resolve()
    assert seen["args"][seen["args"].index("--mode") + 1] == "accept-edits"


async def test_network_errors_are_reported_as_jules_errors(monkeypatch):
    def offline(request):
        raise httpx.ConnectError("Name or service not known", request=request)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        jules.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(offline), **kwargs),
    )
    monkeypatch.setenv("JULES_API_KEY", "test-key")
    mcp = MCPServer("test")
    jules.register(mcp, Settings.from_env())
    out = text_of(await mcp.call_tool("jules_sessions", {}))
    assert out.startswith("Error: Could not reach the Jules API (ConnectError"), out


async def test_sources_reads_every_page(monkeypatch):
    pages = {
        None: {"sources": [{"id": "github/o/a"}], "nextPageToken": "t2"},
        "t2": {"sources": [{"id": "github/o/b"}]},
    }

    async def fake_call(method, path, body=None, params=None):
        assert path == "sources"
        return pages[params.get("pageToken")]

    monkeypatch.setattr(jules, "call", fake_call)
    mcp = MCPServer("test")
    jules.register(mcp, Settings.from_env())
    text = text_of(await mcp.call_tool("jules_sources", {}))
    assert text.splitlines() == ["github/o/a", "github/o/b"]


async def test_pagination_continues_past_twenty_pages_and_detects_cycles(monkeypatch):
    async def page(method, path, params):
        number = int(params.get("pageToken", 1))
        return {"sources": [{"id": number}], "nextPageToken": str(min(22, number + 1))}

    monkeypatch.setattr(jules, "call", page)
    ids = []
    with pytest.raises(jules.JulesError, match="repeated page token"):
        async for source in jules.paged_items("sources", "sources"):
            ids.append(source["id"])
    assert ids == list(range(1, 23))
