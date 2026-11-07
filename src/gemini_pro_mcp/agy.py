"""Gemini through the Antigravity CLI (`agy`), on the user's Google AI Pro quota.

`agy -p` is Google's official non-interactive mode. Every request runs in plan
mode with the terminal sandbox on, so the agent can read files and search the
web but not change anything on the user's machine.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from .config import Settings

# Windows limits a command line to 32 767 characters; keep room for the rest.
MAX_PROMPT_CHARS = 24_000

Effort = Literal["low", "medium", "high", "xhigh", "max"]

INSTALL_HINT = (
    "The Antigravity CLI (agy) was not found. Install it from "
    "https://antigravity.google, sign in with your Google AI Pro account by "
    "running `agy` once, or set AGY_PATH to the executable."
)

RESEARCH_PROMPT = """Research the question below using web search.
- Prefer primary and official sources; cross-check key facts in more than one source.
- Say plainly when sources disagree or when something could not be verified.
- End with a "Sources" list of the URLs you used.

Question: {question}"""


class AgyError(RuntimeError):
    pass


@dataclass
class AgyResult:
    response: str
    conversation_id: str | None = None
    status: str = ""
    duration_seconds: float | None = None
    usage: dict = field(default_factory=dict)


def build_args(
    agy: str,
    prompt: str,
    *,
    model: str | None = None,
    conversation_id: str | None = None,
    add_dirs: list[Path] | None = None,
    effort: str | None = None,
    timeout: int = 600,
    mode: str = "plan",
    agent: str | None = None,
) -> list[str]:
    args = [
        agy,
        "--print",
        prompt,
        "--output-format",
        "json",
        "--mode",
        mode,
        "--sandbox",
        "--print-timeout",
        f"{timeout}s",
    ]
    if model:
        args += ["--model", model]
    if conversation_id:
        args += ["--conversation", conversation_id]
    if effort:
        args += ["--effort", effort]
    if agent:
        args += ["--agent", agent]
    for directory in add_dirs or []:
        args += ["--add-dir", str(directory)]
    return args


def parse_output(stdout: str) -> AgyResult:
    """Reads agy's JSON result (the last JSON object it printed)."""
    text = stdout.strip()
    start = text.rfind("\n{")
    candidates = [text] if start == -1 else [text, text[start + 1 :]]
    data = None
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(data, dict):
        raise AgyError(f"Unexpected output from agy: {text[:500] or '(empty)'}")
    result = AgyResult(
        response=str(data.get("response") or "").strip(),
        conversation_id=data.get("conversation_id"),
        status=str(data.get("status") or ""),
        duration_seconds=data.get("duration_seconds"),
        usage=data.get("usage") or {},
    )
    if result.status and result.status.upper() != "SUCCESS":
        raise AgyError(f"agy finished with status {result.status}: {result.response[:500]}")
    return result


def workspace_for(paths: list[str] | None) -> tuple[Path, list[Path], list[Path]]:
    """Returns (working dir, dirs to add, files mentioned) for the given paths."""
    files: list[Path] = []
    dirs: list[Path] = []
    for raw in paths or []:
        path = Path(raw).expanduser().resolve()
        if path.is_file():
            files.append(path)
            if path.parent not in dirs:
                dirs.append(path.parent)
        elif path.is_dir():
            if path not in dirs:
                dirs.append(path)
        else:
            raise AgyError(f"Path not found: {path}")
    if dirs:
        return dirs[0], dirs[1:], files
    scratch = Path(tempfile.gettempdir()) / "gemini-pro-mcp"
    scratch.mkdir(parents=True, exist_ok=True)
    return scratch, [], files


async def run_agy(args: list[str], cwd: Path, timeout: int) -> str:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout + 30)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise AgyError(f"agy did not answer within {timeout} s.") from None
    out = stdout.decode("utf-8", errors="replace")
    if process.returncode != 0 and not out.strip():
        err = stderr.decode("utf-8", errors="replace").strip()
        raise AgyError(f"agy exited with code {process.returncode}: {err[:800]}")
    return out


async def ask(
    settings: Settings,
    prompt: str,
    *,
    model: str | None = None,
    conversation_id: str | None = None,
    paths: list[str] | None = None,
    effort: str | None = None,
    mode: str = "plan",
    agent: str | None = None,
    cwd: Path | None = None,
) -> AgyResult:
    if not settings.agy_path:
        raise AgyError(INSTALL_HINT)
    workdir, extra_dirs, files = workspace_for(paths)
    cwd = cwd or workdir
    if files:
        listed = "\n".join(f"- {f}" for f in files)
        prompt = f"Files to use:\n{listed}\n\n{prompt}"
    if len(prompt) > MAX_PROMPT_CHARS:
        raise AgyError(
            f"Prompt is {len(prompt)} characters (limit {MAX_PROMPT_CHARS}). Save the "
            "long text to a file and pass its path in `paths` instead."
        )
    args = build_args(
        settings.agy_path,
        prompt,
        model=model or settings.agy_model,
        conversation_id=conversation_id,
        add_dirs=extra_dirs,
        effort=effort,
        timeout=settings.agy_timeout,
        mode=mode,
        agent=agent,
    )
    return parse_output(await run_agy(args, cwd, settings.agy_timeout))


def format_result(result: AgyResult) -> str:
    footer = []
    if result.conversation_id:
        footer.append(f"conversation_id: {result.conversation_id} (pass it to continue)")
    if result.duration_seconds is not None:
        footer.append(f"took {result.duration_seconds:.0f} s")
    return result.response + ("\n\n---\n" + " · ".join(footer) if footer else "")


def parse_models(stdout: str) -> list[tuple[str, str]]:
    models = []
    for line in stdout.splitlines():
        if "\t" in line:
            model_id, name = line.split("\t", 1)
            models.append((model_id.strip(), name.strip()))
    return models


READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)


def register(mcp: MCPServer, settings: Settings) -> None:
    @mcp.tool(annotations=READ_ONLY)
    async def gemini_ask(
        prompt: str,
        model: str | None = None,
        paths: list[str] | None = None,
        conversation_id: str | None = None,
        effort: Effort | None = None,
    ) -> str:
        """Ask Gemini a question or give it a reading task, through the Antigravity
        CLI on the user's Google AI Pro plan (no API cost; uses the plan's limits).

        Good for a second opinion on code or a design, reviewing local files or
        folders passed in `paths`, and long reasoning. Gemini runs read-only in a
        sandbox: it can read those paths and search the web but cannot change
        files or run commands. For web research with cited sources use
        gemini_research; to let Gemini edit a folder use gemini_code.

        Args:
            prompt: The question or task.
            model: Model id from gemini_models (e.g. "gemini-3.8-flash-medium");
                default is agy's (or GEMINI_PRO_AGY_MODEL).
            paths: Local files or folders Gemini may read.
            conversation_id: Continue an earlier gemini_ask/gemini_research chat.
            effort: Reasoning effort: low, medium, high, xhigh or max.

        Returns:
            Gemini's answer and a conversation_id for follow-ups.
        """
        try:
            return format_result(
                await ask(
                    settings,
                    prompt,
                    model=model,
                    conversation_id=conversation_id,
                    paths=paths,
                    effort=effort,
                )
            )
        except AgyError as e:
            return f"Error: {e}"

    @mcp.tool(annotations=READ_ONLY)
    async def gemini_research(
        question: str,
        model: str | None = None,
        effort: Effort | None = None,
    ) -> str:
        """Research a question on the live web with Gemini and Google Search, and
        get an answer that cites its sources. Use it for current facts, releases,
        prices, docs or comparisons that may be newer than your training data.

        Runs through the Antigravity CLI on the user's Google AI Pro plan: no API
        cost, uses the plan's limits. Read-only. Gemini prefers official sources,
        cross-checks key facts and says when sources disagree. Usually takes about
        a minute. For questions about local files use gemini_ask instead.

        Args:
            question: What to find out, with context that narrows it, e.g.
                "What changed in Flutter 3.47 for Android builds?".
            model: Model id from gemini_models, e.g. "gemini-4-argon-high";
                omit for agy's default (or GEMINI_PRO_AGY_MODEL).
            effort: Reasoning effort: "low", "medium", "high", "xhigh" or "max".

        Returns:
            The answer followed by a "Sources" list of URLs, and a conversation_id;
            pass it to gemini_ask to ask follow-up questions in the same chat.
        """
        try:
            return format_result(
                await ask(
                    settings,
                    RESEARCH_PROMPT.format(question=question),
                    model=model,
                    effort=effort,
                )
            )
        except AgyError as e:
            return f"Error: {e}"

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True
        )
    )
    async def gemini_code(
        task: str,
        folder: str,
        model: str | None = None,
        agent: str | None = None,
        effort: Effort | None = None,
        conversation_id: str | None = None,
    ) -> str:
        """Delegate a coding task to Gemini, which reads and EDITS files in one
        local folder through the Antigravity agent on the user's Google AI Pro plan
        (no API cost). This changes files: tell the user, and review the result
        afterwards, e.g. with `git diff`. Terminal commands run in a sandbox and
        only the given folder is writable.

        Good for a well-defined change: fix a bug, add tests, refactor a module.
        For read-only questions use gemini_ask; for a task on a GitHub repo that
        should end in a pull request use jules_start.

        Args:
            task: What to change and how to know it is done, e.g. "Add unit tests
                for parse_date in utils/dates.py; all tests must pass".
            folder: Absolute path of the project folder Gemini may edit.
            model: Model id from gemini_models; omit for agy's default.
            agent: Name of an Antigravity agent from gemini_agents to run the task.
            effort: Reasoning effort: "low", "medium", "high", "xhigh" or "max".
            conversation_id: Continue an earlier gemini_code or gemini_ask chat, e.g.
                to ask for fixes to the previous change.

        Returns:
            Gemini's summary of what it changed, and a conversation_id for follow-up
            requests; or an error if the folder does not exist.
        """
        try:
            path = Path(folder).expanduser().resolve()
            if not path.is_dir():
                return f"Error: folder not found: {path}"
            return format_result(
                await ask(
                    settings,
                    task,
                    model=model,
                    conversation_id=conversation_id,
                    effort=effort,
                    mode="accept-edits",
                    agent=agent,
                    cwd=path,
                )
            )
        except AgyError as e:
            return f"Error: {e}"

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def gemini_agents() -> str:
        """List the custom Antigravity agents the user has made or installed, such
        as a "reviewer" or "test-writer" agent with its own instructions.
        Read-only, free and quick. Call it before gemini_code when the user wants
        a task done by a specific agent.

        Returns:
            The agent names and descriptions as the Antigravity CLI prints them; pass
            a name as `agent` to gemini_code. "No custom agents." if there are none.
        """
        if not settings.agy_path:
            return f"Error: {INSTALL_HINT}"
        try:
            out = await run_agy([settings.agy_path, "agents"], Path.cwd(), 60)
        except AgyError as e:
            return f"Error: {e}"
        return out.strip() or "No custom agents."

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def gemini_models() -> str:
        """List the models the user's Google account can use through the Antigravity
        CLI, e.g. Gemini 4 Argon and Gemini 3.8 Flash at several thinking levels.
        Read-only, free and quick. Call it when the user asks for a specific or
        stronger model; otherwise the gemini_* tools use agy's default.

        Returns:
            One "id — name" line per model, e.g. "gemini-4-argon-high — Gemini 4
            Argon (High)". Pass the id as `model` to gemini_ask, gemini_research or
            gemini_code.
        """
        if not settings.agy_path:
            return f"Error: {INSTALL_HINT}"
        try:
            out = await run_agy([settings.agy_path, "models"], Path.cwd(), 60)
        except AgyError as e:
            return f"Error: {e}"
        models = parse_models(out)
        if not models:
            return f"No models listed. agy said: {out.strip()[:500]}"
        return "\n".join(f"{model_id} — {name}" for model_id, name in models)
