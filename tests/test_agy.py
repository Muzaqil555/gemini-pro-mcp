import dataclasses
import json
import sys
from pathlib import Path

import pytest

from gemini_pro_mcp import agy
from gemini_pro_mcp.config import Settings


@pytest.fixture
def settings(tmp_path):
    return dataclasses.replace(
        Settings.from_env(), agy_path="agy", agy_model=None, output_dir=tmp_path
    )


def test_build_args_is_read_only_and_sandboxed():
    args = agy.build_args("agy", "hi", model="m", conversation_id="c1", effort="high", timeout=90)
    assert args[:3] == ["agy", "--print", "hi"]
    assert args[args.index("--mode") + 1] == "plan"
    assert "--sandbox" in args
    assert args[args.index("--print-timeout") + 1] == "90s"
    assert args[args.index("--model") + 1] == "m"
    assert args[args.index("--conversation") + 1] == "c1"
    assert args[args.index("--effort") + 1] == "high"


def test_parse_output_success():
    out = json.dumps(
        {
            "conversation_id": "abc",
            "status": "SUCCESS",
            "response": "Four\n",
            "duration_seconds": 11.4,
            "usage": {"total_tokens": 5},
        }
    )
    result = agy.parse_output("some log line\n" + out)
    assert result.response == "Four"
    assert result.conversation_id == "abc"
    assert "conversation_id: abc" in agy.format_result(result)


def test_parse_output_failure_and_junk():
    with pytest.raises(agy.AgyError, match="status ERROR"):
        agy.parse_output(json.dumps({"status": "ERROR", "response": "quota"}))
    with pytest.raises(agy.AgyError, match="Unexpected output"):
        agy.parse_output("not json")


def test_parse_models():
    out = "Fetching available models...\ngemini-x-high\tGemini X (High)\nnoise"
    assert agy.parse_models(out) == [("gemini-x-high", "Gemini X (High)")]


def test_workspace_for_files_and_dirs(tmp_path):
    f = tmp_path / "a" / "notes.md"
    f.parent.mkdir()
    f.write_text("x")
    other = tmp_path / "b"
    other.mkdir()
    cwd, extra, files = agy.workspace_for([str(f), str(other)])
    assert cwd == f.parent.resolve()
    assert extra == [other.resolve()]
    assert files == [f.resolve()]
    with pytest.raises(agy.AgyError, match="Path not found"):
        agy.workspace_for([str(tmp_path / "missing")])


async def test_ask_passes_files_and_model(settings, tmp_path, monkeypatch):
    f = tmp_path / "doc.txt"
    f.write_text("hello")
    seen = {}

    async def fake_run(args, cwd, timeout):
        seen["args"], seen["cwd"] = args, cwd
        return json.dumps({"status": "SUCCESS", "response": "ok", "conversation_id": "z"})

    monkeypatch.setattr(agy, "run_agy", fake_run)
    result = await agy.ask(settings, "summarize", model="gemini-q", paths=[str(f)])
    assert result.response == "ok"
    prompt = seen["args"][seen["args"].index("--print") + 1]
    assert str(f.resolve()) in prompt and prompt.endswith("summarize")
    assert seen["args"][seen["args"].index("--model") + 1] == "gemini-q"
    assert seen["cwd"] == tmp_path.resolve()


async def test_ask_rejects_long_prompt_and_missing_cli(settings):
    with pytest.raises(agy.AgyError, match="limit"):
        await agy.ask(settings, "x" * (agy.MAX_PROMPT_CHARS + 1))
    with pytest.raises(agy.AgyError, match="not found"):
        await agy.ask(dataclasses.replace(settings, agy_path=None), "hi")


async def test_run_agy_reads_stdout(tmp_path):
    script = "import json; print(json.dumps({'status': 'SUCCESS', 'response': 'hi'}))"
    out = await agy.run_agy([sys.executable, "-c", script], Path(tmp_path), 30)
    assert agy.parse_output(out).response == "hi"


async def test_run_agy_reports_exit_code(tmp_path):
    script = "import sys; sys.stderr.write('not signed in'); sys.exit(3)"
    with pytest.raises(agy.AgyError, match="code 3: not signed in"):
        await agy.run_agy([sys.executable, "-c", script], Path(tmp_path), 30)
