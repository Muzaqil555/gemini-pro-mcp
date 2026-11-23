import asyncio
import dataclasses
import json
import os
import subprocess
import sys
import time
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
    # Print mode can't ask before an MCP tool runs: it ends the turn with no answer.
    session = json.loads(args[args.index("--settings") + 1])
    assert session["permissions"]["deny"] == ["mcp(*)", "command(*)"]


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
        return json.dumps({"status": "SUCCESS", "response": "ok", "conversation_id": "z"}), ""

    monkeypatch.setattr(agy, "run_agy_capture", fake_run)
    result = await agy.ask(settings, "summarize", model="gemini-q", paths=[str(f)])
    assert result.response == "ok"
    prompt = seen["args"][seen["args"].index("--print") + 1]
    assert str(f.resolve()) in prompt and prompt.endswith("summarize")
    assert "\nhello\n" in prompt  # the file text itself, so Gemini needs no file access
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


async def test_run_agy_returns_once_the_result_is_printed(tmp_path, monkeypatch):
    """agy can hang for minutes after its answer while it stops its MCP servers."""
    monkeypatch.setattr(agy, "EXIT_GRACE_SECONDS", 0.5)
    pid_file = tmp_path / "child.pid"
    script = (
        "import json, os, subprocess, sys, time\n"
        # A child that would outlive agy if only agy itself were stopped.
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
        f"open({str(pid_file)!r}, 'w').write(str(child.pid))\n"
        "print(json.dumps({'status': 'SUCCESS', 'response': 'done'}), flush=True)\n"
        "time.sleep(120)\n"
    )
    started = time.monotonic()
    out = await agy.run_agy([sys.executable, "-c", script], Path(tmp_path), 300)
    assert time.monotonic() - started < 60
    assert agy.parse_output(out).response == "done"
    assert not _running(int(pid_file.read_text()))


def _running(pid: int) -> bool:
    """Whether a process is still alive, without signalling it."""
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True
        ).stdout
        return str(pid) in out
    for _ in range(50):  # the killed child may take a moment to be reaped
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        try:
            waited, _status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            waited = 0
        if waited:
            return False
        time.sleep(0.1)
    return True


async def test_run_agy_stops_agy_when_the_call_is_cancelled(tmp_path):
    """A cancelled tool call must not leave agy running (and editing files) for minutes."""
    pid_file = tmp_path / "agy.pid"
    script = (
        f"import os, time; open({str(pid_file)!r}, 'w').write(str(os.getpid())); time.sleep(120)"
    )
    task = asyncio.ensure_future(agy.run_agy([sys.executable, "-c", script], Path(tmp_path), 300))
    for _ in range(100):
        if pid_file.exists() and pid_file.read_text():
            break
        await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not _running(int(pid_file.read_text()))


async def test_run_agy_still_waits_for_plain_text_output(tmp_path):
    script = (
        "import time; print('gemini-4-argon-high  Gemini 4 Argon'); time.sleep(1); print('end')"
    )
    out = await agy.run_agy([sys.executable, "-c", script], Path(tmp_path), 30)
    assert "end" in out


def test_format_result_says_when_gemini_returned_no_text():
    result = agy.parse_output(
        json.dumps(
            {
                "status": "SUCCESS",
                "response": "",
                "conversation_id": "c1",
                "finished_reason": "interrupted",
            }
        )
    )
    text = agy.format_result(result)
    assert "Gemini returned no text (finished_reason: interrupted)" in text
    assert "conversation_id: c1" in text


async def test_ask_explains_an_empty_answer_with_what_agy_said(settings, monkeypatch):
    async def fake_run(args, cwd, timeout):
        out = json.dumps({"status": "SUCCESS", "response": "", "conversation_id": "e1"})
        return out, "jetski: no output produced - a tool required a permission"

    monkeypatch.setattr(agy, "run_agy_capture", fake_run)
    text = agy.format_result(await agy.ask(settings, "hi"))
    assert text.startswith("Gemini returned no text.")
    assert "agy said: jetski: no output produced" in text


def test_with_files_includes_small_text_files_and_lists_the_rest(tmp_path):
    small = tmp_path / "small.py"
    small.write_bytes(b"print('hi')\n")  # bytes: Windows would write \r\n
    big = tmp_path / "big.txt"
    big.write_text("x" * (agy.EMBED_FILE_MAX_CHARS + 1), encoding="utf-8")
    binary = tmp_path / "image.png"
    binary.write_bytes(b"\x89PNG\x00\x00data")
    prompt = agy.with_files("Review it.", [small, big, binary])
    assert f"<file path=\"{small}\">\nprint('hi')\n\n</file>" in prompt
    assert f"- {big}" in prompt and f"- {binary}" in prompt
    assert "x" * 100 not in prompt
    assert prompt.endswith("Review it.")
    assert len(prompt) < agy.MAX_PROMPT_CHARS
