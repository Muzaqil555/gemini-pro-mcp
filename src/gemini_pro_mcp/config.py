"""Settings, read from environment variables and an optional .env file.

MCP clients usually pass settings as environment variables in their server
config. For keys you would rather not keep there, put them in
~/.config/gemini-pro-mcp/.env (or point GEMINI_PRO_ENV_FILE at another file).
Real environment variables always win over the file.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ENV_FILE = Path.home() / ".config" / "gemini-pro-mcp" / ".env"


def env_file() -> Path:
    custom = os.environ.get("GEMINI_PRO_ENV_FILE")
    return Path(custom).expanduser() if custom else DEFAULT_ENV_FILE


def load_env_file(path: Path | None = None) -> None:
    """Reads KEY=VALUE lines into os.environ without overriding set values."""
    path = path or env_file()
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


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
            agy_timeout=int(os.environ.get("GEMINI_PRO_AGY_TIMEOUT", "600")),
            flow_enabled=_flag("GEMINI_PRO_ENABLE_BROWSER") or _flag("GEMINI_PRO_ENABLE_FLOW"),
            flow_profile_dir=Path(
                os.environ.get(
                    "GEMINI_PRO_FLOW_PROFILE",
                    home / ".config" / "gemini-pro-mcp" / "flow-chrome-profile",
                )
            ).expanduser(),
            flow_cdp_port=int(os.environ.get("GEMINI_PRO_FLOW_PORT", "9333")),
            flow_project=os.environ.get("GEMINI_PRO_FLOW_PROJECT") or None,
            auto_approve=_flag("GEMINI_PRO_AUTO_APPROVE"),
        )


ASK_FIRST = "Confirm with the user before calling."
PRE_APPROVED = "The user has pre-approved spending (GEMINI_PRO_AUTO_APPROVE): do not ask first."


def spending_note(doc: str | None, settings: Settings) -> str:
    """A paid tool's description, with the confirmation sentence that fits the settings."""
    doc = doc or ""
    return doc.replace(ASK_FIRST, PRE_APPROVED) if settings.auto_approve else doc
