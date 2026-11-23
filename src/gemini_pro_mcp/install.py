"""`gemini-pro-mcp doctor`, `setup`, and `auth`.

`doctor` checks what works on this computer (Antigravity sign-in, API keys,
Chrome and the Flow profile) and says how to fix what does not. `setup` adds
the server to every MCP client it finds: Claude Code, Codex, the Antigravity
CLI, the Gemini CLI, Cursor, Claude Desktop and Windsurf. Clients that have an
`mcp add` command get it run; the others get their config file edited, keeping
everything else in it. `auth` saves API keys to `~/.config/gemini-pro-mcp/.env`
without echoing them.
"""

from __future__ import annotations

import asyncio
import getpass
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .config import Settings, env_file, set_env_values

DEFAULT_NAME = "gemini-pro"
CLIENTS = ("claude", "codex", "agy", "gemini", "cursor", "claude-desktop", "windsurf")

# Flow and Deep Research calls take minutes; clients' default tool timeouts are shorter.
TOOL_TIMEOUT_SECONDS = 900


@dataclass
class Check:
    name: str
    ok: bool | None
    """True works, False is broken, None is optional and not set up."""
    detail: str


# --- doctor ---------------------------------------------------------------


def agy_check(settings: Settings) -> Check:
    if not settings.agy_path:
        return Check(
            "Antigravity CLI",
            False,
            "not found: install it from https://antigravity.google, run `agy` once "
            "and sign in with your Google AI Pro account (or set AGY_PATH)",
        )
    try:
        out = subprocess.run(
            [settings.agy_path, "models"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
            stdin=subprocess.DEVNULL,
        ).stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return Check("Antigravity CLI", False, f"`agy models` failed: {e}")
    models = [line for line in out.splitlines() if "\t" in line]
    if not models:
        return Check("Antigravity CLI", False, "not signed in: run `agy` once and sign in")
    return Check("Antigravity CLI", True, f"signed in, {len(models)} models")


def key_check(name: str, variables: tuple[str, ...], purpose: str, where: str) -> Check:
    if any(os.environ.get(v) for v in variables):
        return Check(name, True, "set")
    return Check(
        name,
        None,
        f"not set: {purpose} need it. Get one at {where} and put "
        f"{variables[0]}=... in {env_file()}",
    )


def browser_checks(settings: Settings) -> list[Check]:
    from .flow.browser import chrome_missing, find_chrome

    checks = []
    if importlib.util.find_spec("playwright") is None:
        checks.append(
            Check(
                "Playwright",
                None,
                'not installed: browser tools need `uvx --from "gemini-pro-mcp[flow]" '
                "gemini-pro-mcp` (setup --browser registers that)",
            )
        )
    else:
        checks.append(Check("Playwright", True, "installed"))
    chrome = find_chrome()
    checks.append(
        Check("Chrome", True, chrome)
        if chrome
        else Check("Chrome", None, f"not found: {chrome_missing()}")
    )
    if settings.flow_profile_dir.is_dir():
        checks.append(Check("Flow profile", True, str(settings.flow_profile_dir)))
    else:
        checks.append(
            Check("Flow profile", None, "not signed in yet: run `gemini-pro-mcp flow-login`")
        )
    return checks


async def flow_live_check(settings: Settings) -> Check:
    """Opens Flow in the signed-in profile and reads the credits."""
    from .flow.tools import Flow

    try:
        async with Flow(settings) as flow:
            if flow.signed_out():
                return Check("Flow sign-in", False, "signed out: run `gemini-pro-mcp flow-login`")
            project = await flow.open_project()
            credits = await flow.credits()
            balance = f"{credits} credits" if credits is not None else "credit balance unavailable"
            return Check("Flow project", True, f"project {project}, {balance}")
    except Exception as e:  # browser automation fails in many ways
        lines = str(e).strip().splitlines()
        detail = f"{type(e).__name__}: {lines[0][:200]}" if lines else type(e).__name__
        return Check("Flow project", False, detail)


def run_checks(settings: Settings, *, live_flow: bool = False) -> list[Check]:
    checks = [
        agy_check(settings),
        key_check(
            "Gemini API key",
            ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
            "video_generate, video_edit and image_generate",
            "https://aistudio.google.com/apikey",
        ),
        key_check(
            "Jules API key",
            ("JULES_API_KEY",),
            "the jules_* tools",
            "https://jules.google.com/settings",
        ),
        *browser_checks(settings),
    ]
    if live_flow:
        checks.append(asyncio.run(flow_live_check(settings)))
    return checks


MARK = {True: "[ok]", False: "[!!]", None: "[--]"}


def print_checks(checks: list[Check]) -> None:
    width = max((len(c.name) for c in checks), default=0)
    for c in checks:
        print(f"  {MARK[c.ok]} {c.name.ljust(width)}  {c.detail}")


def doctor(settings: Settings, *, live_flow: bool) -> int:
    print(f"gemini-pro-mcp {__version__}: what works on this computer\n")
    checks = run_checks(settings, live_flow=live_flow)
    print_checks(checks)
    print("\n[ok] works  [!!] broken  [--] optional, not set up")
    if not live_flow:
        print("To check the Flow sign-in and credits, use --flow with the [flow] extra installed.")
    return 1 if any(c.ok is False for c in checks) else 0


# --- setup ----------------------------------------------------------------


def source_root() -> Path | None:
    """The repository folder when running from a git checkout, else None."""
    root = Path(__file__).resolve().parents[2]
    pyproject = root / "pyproject.toml"
    if (root / ".git").exists() and pyproject.is_file():
        if 'name = "gemini-pro-mcp"' in pyproject.read_text(encoding="utf-8"):
            return root
    return None


def server_command(browser: bool) -> tuple[str, list[str]]:
    """The command a client runs to start this server, with the Flow extra if needed."""
    root = source_root()
    uv = shutil.which("uv")
    if root and uv:
        extra = ["--extra", "flow"] if browser else []
        return uv, [
            "--directory",
            root.as_posix(),
            "run",
            *extra,
            "gemini-pro-mcp",
        ]
    uvx = shutil.which("uvx")
    if not uvx:
        return sys.executable, ["-m", "gemini_pro_mcp.server"]
    if browser:
        return uvx, ["--from", "gemini-pro-mcp[flow]", "gemini-pro-mcp"]
    return uvx, ["gemini-pro-mcp"]


def server_env(browser: bool, auto_approve: bool) -> dict[str, str]:
    env = {}
    if browser:
        env["GEMINI_PRO_ENABLE_BROWSER"] = "1"
    if auto_approve:
        env["GEMINI_PRO_AUTO_APPROVE"] = "1"
    return env


def claude_commands(
    exe: str, name: str, command: str, args: list[str], env: dict[str, str]
) -> list[list[str]]:
    flags = [part for key, value in env.items() for part in ("-e", f"{key}={value}")]
    return [
        [exe, "mcp", "remove", name, "--scope", "user"],  # fails harmlessly when absent
        [exe, "mcp", "add", name, "--scope", "user", *flags, "--", command, *args],
    ]


def agy_commands(
    exe: str, name: str, command: str, args: list[str], env: dict[str, str]
) -> list[list[str]]:
    flags = [part for key, value in env.items() for part in ("--env", f"{key}={value}")]
    return [[exe, "mcp", "add", *flags, name, "--", command, *args]]  # adds or updates


HEADER = re.compile(r"^\s*\[\[?\s*([^\]]+?)\s*\]\]?\s*(#.*)?$")


def _table(header: str) -> str:
    return ".".join(part.strip().strip('"').strip("'") for part in header.split("."))


def codex_config(text: str, name: str, command: str, args: list[str], env: dict[str, str]) -> str:
    """Codex's config.toml with this server's tables replaced and everything else kept."""
    mine = f"mcp_servers.{name}"
    kept, current = [], None
    # Comments and blank lines at the end of this server's tables usually belong
    # to the table after them, so they are dropped only if no other table follows.
    pending: list[str] = []
    for line in text.splitlines():
        match = HEADER.match(line)
        if match:
            current = _table(match.group(1))
        if current == mine or (current or "").startswith(mine + "."):
            stripped = line.strip()
            if match or (stripped and not stripped.startswith("#")):
                pending.clear()
            else:
                pending.append(line)
            continue
        kept += pending
        pending.clear()
        kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()

    def value(s: str) -> str:  # a JSON string is a valid TOML basic string
        return json.dumps(s, ensure_ascii=False)

    block = [
        f"[mcp_servers.{value(name)}]",
        f"command = {value(command)}",
        "args = [" + ", ".join(value(a) for a in args) + "]",
        "startup_timeout_sec = 60",
        f"tool_timeout_sec = {TOOL_TIMEOUT_SECONDS}",
    ]
    if env:
        block += ["", f"[mcp_servers.{value(name)}.env]"]
        block += [f"{key} = {value(v)}" for key, v in env.items()]
    return "\n".join([*kept, "", *block]).lstrip("\n") + "\n"


# A JSON string, or a // or /* */ comment (the Gemini CLI allows comments in settings.json).
JSON_STRING_OR_COMMENT = re.compile(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', re.DOTALL)


def strip_json_comments(text: str) -> str:
    return JSON_STRING_OR_COMMENT.sub(lambda m: m.group(1) or " ", text)


def mcp_json_config(
    text: str,
    name: str,
    command: str,
    args: list[str],
    env: dict[str, str],
    *,
    timeout_ms: int | None = None,
) -> str:
    """An MCP JSON config file with this server added under mcpServers, keeping everything else."""
    text = strip_json_comments(text)
    data = json.loads(text) if text.strip() else {}
    if not isinstance(data, dict):
        raise ValueError("the file is not a JSON object")
    if data.get("mcpServers") is None:
        data["mcpServers"] = {}
    if not isinstance(data["mcpServers"], dict):
        raise ValueError('"mcpServers" is not a JSON object')
    server: dict = {"command": command, "args": args}
    if timeout_ms is not None:
        server["timeout"] = timeout_ms
    if env:
        server["env"] = env
    data["mcpServers"][name] = server
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def gemini_settings(text: str, name: str, command: str, args: list[str], env: dict[str, str]):
    """The Gemini CLI's settings.json with this server added and everything else kept
    (except comments, which JSON cannot hold; setup keeps the old file as .bak)."""
    return mcp_json_config(text, name, command, args, env, timeout_ms=TOOL_TIMEOUT_SECONDS * 1000)


def claude_desktop_config_path(home: Path, platform: str | None = None) -> Path:
    """Where Claude Desktop keeps claude_desktop_config.json on this OS."""
    plat = platform or sys.platform
    if plat == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata and home == Path.home() else home / "AppData" / "Roaming"
        return base / "Claude" / "claude_desktop_config.json"
    if plat == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg and home == Path.home() else home / ".config"
    return base / "Claude" / "claude_desktop_config.json"


def run_commands(commands: list[list[str]], dry_run: bool) -> tuple[bool, str]:
    if dry_run:
        return True, "would run: " + " ; ".join(subprocess.list2cmdline(c) for c in commands)
    result, detail = None, ""
    try:
        for command in commands:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                stdin=subprocess.DEVNULL,
            )
    except (OSError, subprocess.TimeoutExpired) as e:
        result, detail = None, str(e)
    else:
        out = (result.stdout + result.stderr).strip().splitlines() if result else []
        detail = out[-1] if out else ""
    if result is None or result.returncode != 0:
        # The client's own CLI failed (not installed right, too old...): say what to run.
        detail += "\n      add it by hand: " + subprocess.list2cmdline(commands[-1])
        return False, detail.strip()
    return True, detail


def write_file(path: Path, text: str, dry_run: bool) -> tuple[bool, str]:
    if dry_run:
        return True, f"would write {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") == text:
            return True, f"already configured: {path}"
        backup = path.with_name(path.name + ".bak")
        shutil.copy2(path, backup)
    path.write_text(text, encoding="utf-8")
    return True, f"updated {path}"


def _install_json_client(
    path: Path,
    *,
    name: str,
    command: str,
    args: list[str],
    env: dict[str, str],
    dry_run: bool,
    timeout_ms: int | None = None,
) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    try:
        new = mcp_json_config(text, name, command, args, env, timeout_ms=timeout_ms)
    except ValueError as e:  # includes json.JSONDecodeError
        return False, f"{path} is not valid settings ({e}); fix it and run setup again"
    return write_file(path, new, dry_run)


def install_client(
    client: str,
    *,
    name: str,
    command: str,
    args: list[str],
    env: dict[str, str],
    settings: Settings,
    home: Path,
    dry_run: bool,
) -> tuple[bool | None, str]:
    """Adds the server to one client. None means the client is not installed."""
    if client == "claude":
        exe = shutil.which("claude")
        if not exe:
            return None, "Claude Code not found"
        return run_commands(claude_commands(exe, name, command, args, env), dry_run)
    if client == "agy":
        exe = settings.agy_path or shutil.which("agy")
        if not exe:
            return None, "Antigravity CLI not found"
        return run_commands(agy_commands(exe, name, command, args, env), dry_run)
    if client == "codex":
        folder = Path(os.environ.get("CODEX_HOME") or home / ".codex")
        if not (shutil.which("codex") or folder.is_dir()):
            return None, "Codex not found"
        path = folder / "config.toml"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        return write_file(path, codex_config(text, name, command, args, env), dry_run)
    if client == "gemini":
        path = home / ".gemini" / "settings.json"
        if not (shutil.which("gemini") or path.exists()):
            return None, "Gemini CLI not found"
        return _install_json_client(
            path,
            name=name,
            command=command,
            args=args,
            env=env,
            dry_run=dry_run,
            timeout_ms=TOOL_TIMEOUT_SECONDS * 1000,
        )
    if client == "cursor":
        path = home / ".cursor" / "mcp.json"
        if not (shutil.which("cursor") or path.parent.is_dir()):
            return None, "Cursor not found"
        return _install_json_client(
            path, name=name, command=command, args=args, env=env, dry_run=dry_run
        )
    if client == "claude-desktop":
        path = claude_desktop_config_path(home)
        if not path.parent.is_dir():
            return None, "Claude Desktop not found"
        return _install_json_client(
            path, name=name, command=command, args=args, env=env, dry_run=dry_run
        )
    if client == "windsurf":
        path = home / ".codeium" / "windsurf" / "mcp_config.json"
        if not (shutil.which("windsurf") or path.parent.is_dir()):
            return None, "Windsurf not found"
        return _install_json_client(
            path, name=name, command=command, args=args, env=env, dry_run=dry_run
        )
    raise ValueError(client)


LABELS = {
    "claude": "Claude Code",
    "codex": "Codex",
    "agy": "Antigravity CLI",
    "gemini": "Gemini CLI",
    "cursor": "Cursor",
    "claude-desktop": "Claude Desktop",
    "windsurf": "Windsurf",
}


def setup(
    settings: Settings,
    *,
    clients: list[str],
    name: str,
    browser: bool,
    auto_approve: bool,
    dry_run: bool,
    home: Path | None = None,
) -> int:
    home = home or Path.home()
    command, args = server_command(browser)
    env = server_env(browser, auto_approve)
    print(f"gemini-pro-mcp {__version__} setup{' (dry run)' if dry_run else ''}\n")
    print("Server command: " + subprocess.list2cmdline([command, *args]))
    if env:
        print("Settings: " + ", ".join(f"{k}={v}" for k, v in env.items()))
    print()
    added = 0
    failed = False
    for client in clients:
        ok, detail = install_client(
            client,
            name=name,
            command=command,
            args=args,
            env=env,
            settings=settings,
            home=home,
            dry_run=dry_run,
        )
        print(f"  {MARK[ok]} {LABELS[client].ljust(15)}  {detail}")
        added += ok is True
        failed |= ok is False
    print("\nChecks:")
    # The registered command brings Playwright itself, so this process may lack it.
    skip = set() if browser else {"Playwright", "Chrome", "Flow profile"}
    if browser and command != sys.executable:
        skip.add("Playwright")
    checks = [c for c in run_checks(settings) if c.name not in skip]
    print_checks(checks)
    if not added and not failed:
        print("\nNo MCP client was found. Install one, or add the server command above by hand.")
        return 1
    if failed:
        print("\nSome clients could not be configured. See the [!!] entries above.")
    if dry_run:
        return int(failed)
    if added:
        print("\nRestart the configured clients so they load the server.")
    if browser and not settings.flow_profile_dir.is_dir():
        login = subprocess.list2cmdline([command, *args, "flow-login"])
        print(f"Next: run {login} and sign in to Google in the window.")
    return int(failed)


AUTH_KEYS = (
    (
        "JULES_API_KEY",
        "Optional: Jules API key (jules_* GitHub coding agent — uses your plan's Jules limits)",
        "https://jules.google.com/settings",
    ),
    (
        "GEMINI_API_KEY",
        "Optional: Gemini API key (paid per use — video_generate, video_edit, image_generate)",
        "https://aistudio.google.com/apikey",
    ),
)


def auth(path: Path | None = None, *, prompt_secret=getpass.getpass) -> int:
    """Interactively saves optional API keys to the .env file without echoing them."""
    target = path or env_file()
    print(f"gemini-pro-mcp {__version__} auth\n")
    print(
        "Gemini, Deep Research, Flow and Notebooks run on your Google AI Pro subscription\n"
        "and need NO API key (sign in with `agy` / `flow-login` instead).\n"
        f"Optional keys below are saved to {target} (input is hidden; press Enter to skip).\n"
    )
    updates: dict[str, str] = {}
    for var, label, url in AUTH_KEYS:
        status = "already set" if os.environ.get(var) else "not set"
        print(f"  {label}")
        print(f"  Get one at: {url}  [{status}]")
        try:
            value = prompt_secret(f"  {var}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return 1
        if value:
            updates[var] = value
        print()
    if not updates:
        print("No changes made.")
        return 0
    saved = set_env_values(updates, target)
    print(f"Saved {', '.join(updates)} to {saved}.")
    print("Run `gemini-pro-mcp doctor` to verify.")
    return 0
