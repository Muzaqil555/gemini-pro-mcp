"""Settings, read from environment variables and an optional .env file.

MCP clients usually pass settings as environment variables in their server
config. For keys you would rather not keep there, put them in
~/.config/gemini-pro-mcp/.env (or point GEMINI_PRO_ENV_FILE at another file).
Real environment variables always win over the file.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ENV_FILE = Path.home() / ".config" / "gemini-pro-mcp" / ".env"


def env_file() -> Path:
    custom = os.environ.get("GEMINI_PRO_ENV_FILE")
    return Path(custom).expanduser() if custom else DEFAULT_ENV_FILE


def parse_env_line(line: str) -> tuple[str, str] | None:
    """The (key, value) of one .env line, or None for blank lines and comments.

    Accepts the forms people copy from other projects: an `export ` prefix,
    values in matching single or double quotes, and `# comments` after a value.
    """
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    if key.startswith("export "):
        key = key[len("export ") :].strip()
    value = value.strip()
    quoted = re.fullmatch(r"""(["'])(.*?)\1(?:\s+#.*)?""", value)
    if quoted:
        value = quoted.group(2)
    else:
        value = re.split(r"\s+#", value, maxsplit=1)[0]
    return (key, value) if key else None


def load_env_file(path: Path | None = None) -> None:
    """Reads KEY=VALUE lines into os.environ without overriding set values."""
    path = path or env_file()
    if not path.is_file():
        return
    # utf-8-sig: Windows Notepad can save the file with a byte order mark, which
    # would otherwise become part of the first key's name.
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parsed = parse_env_line(line)
        if parsed:
            os.environ.setdefault(*parsed)


def _format_env_value(value: str) -> str:
    if any(ch.isspace() or ch in ("#", "'", '"') for ch in value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def set_env_values(updates: dict[str, str], path: Path | None = None) -> Path:
    """Writes or updates KEY=VALUE entries in the .env file, keeping comments and other keys."""
    path = path or env_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.is_file() else []
    remaining = {k: v for k, v in updates.items() if v}
    out: list[str] = []
    for line in lines:
        parsed = parse_env_line(line)
        if parsed and parsed[0] in remaining:
            key = parsed[0]
            out.append(f"{key}={_format_env_value(remaining.pop(key))}")
        else:
            out.append(line)
    for key, value in remaining.items():
        out.append(f"{key}={_format_env_value(value)}")
    path.write_text("\n".join(out) + ("\n" if out else ""), encoding="utf-8")
    if os.name != "nt":
        os.chmod(path, 0o600)
    return path


def _int(name: str, default: int) -> int:
    """A whole-number setting; a value that isn't one falls back to the default.

    Raising here would stop the server before the MCP client can show any error,
    so the problem is reported on stderr, which clients keep in their logs.
    """
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(
            f"gemini-pro-mcp: {name}={raw!r} is not a whole number; using {default}.",
            file=sys.stderr,
        )
        return default


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    output_dir: Path
    """Where generated videos and images are saved."""

    agy_path: str | None
    """The Antigravity CLI executable, or None if it is not installed."""

    agy_model: str | None
    """Default model for Antigravity tools; None uses agy's own default."""

    agy_timeout: int
    """Seconds an Antigravity request may run."""

    flow_enabled: bool
    """Whether the browser tools (Flow, Gemini app, AI Mode, other Google AI
    sites) are registered: GEMINI_PRO_ENABLE_BROWSER=1 (or ..._ENABLE_FLOW=1)."""

    flow_profile_dir: Path
    """Chrome profile used by the Flow tools (signed in by the user)."""

    flow_cdp_port: int
    """Remote debugging port of that Chrome."""

    flow_project: str | None
    """Flow project id to work in; None uses the open or most recent one."""

    auto_approve: bool = False
    """The user pre-approved spending: paid tools run without asking first and
    Flow's permission questions are answered automatically."""

    @classmethod
    def from_env(cls) -> Settings:
        home = Path.home()
        return cls(
            output_dir=Path(
                os.environ.get("GEMINI_PRO_OUTPUT_DIR", home / "gemini-pro-output")
            ).expanduser(),
            agy_path=os.environ.get("AGY_PATH") or shutil.which("agy"),
            agy_model=os.environ.get("GEMINI_PRO_AGY_MODEL") or None,
            agy_timeout=_int("GEMINI_PRO_AGY_TIMEOUT", 600),
            flow_enabled=_flag("GEMINI_PRO_ENABLE_BROWSER") or _flag("GEMINI_PRO_ENABLE_FLOW"),
            flow_profile_dir=Path(
                os.environ.get(
                    "GEMINI_PRO_FLOW_PROFILE",
                    home / ".config" / "gemini-pro-mcp" / "flow-chrome-profile",
                )
            ).expanduser(),
            flow_cdp_port=_int("GEMINI_PRO_FLOW_PORT", 9333),
            flow_project=os.environ.get("GEMINI_PRO_FLOW_PROJECT") or None,
            auto_approve=_flag("GEMINI_PRO_AUTO_APPROVE"),
        )


ASK_FIRST = "Confirm with the user before calling."
PRE_APPROVED = "The user has pre-approved spending (GEMINI_PRO_AUTO_APPROVE): do not ask first."


def spending_note(doc: str | None, settings: Settings) -> str:
    """A paid tool's description, with the confirmation sentence that fits the settings."""
    doc = doc or ""
    return doc.replace(ASK_FIRST, PRE_APPROVED) if settings.auto_approve else doc
