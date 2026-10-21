"""A dedicated Chrome profile for Google Flow, driven over the DevTools protocol.

The user signs in to Google themselves in this profile (`gemini-pro-mcp
flow-login`); the server never sees or types credentials. It is the user's
normal Chrome with no stealth tricks: if Google asks for a CAPTCHA or another
check, the user answers it in that window.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import socket
import subprocess
import time
from pathlib import Path

from ..config import Settings

FLOW_URL = "https://flow.google.com/"


class FlowError(RuntimeError):
    pass


_locks: dict[str, asyncio.Lock] = {}


def lock_for(host: str) -> asyncio.Lock:
    """One driver per site tab at a time; different sites run side by side."""
    if host not in _locks:
        _locks[host] = asyncio.Lock()
    return _locks[host]


def find_chrome() -> str | None:
    custom = os.environ.get("GEMINI_PRO_CHROME")
    if custom:
        return custom
    system = platform.system()
    candidates: list[Path | str | None] = []
    if system == "Windows":
        for base in (
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ):
            if base:
                candidates.append(Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe")
    elif system == "Darwin":
        candidates.append(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        candidates.append(shutil.which(name))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


def port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def launch_chrome(settings: Settings, url: str = FLOW_URL) -> None:
    """Starts the Flow Chrome profile with remote debugging, if not running."""
    if port_open(settings.flow_cdp_port):
        return
    chrome = find_chrome()
    if not chrome:
        raise FlowError(
            "Google Chrome was not found. Install it or set GEMINI_PRO_CHROME to its path."
        )
    settings.flow_profile_dir.mkdir(parents=True, exist_ok=True)
    args = [
        chrome,
        f"--remote-debugging-port={settings.flow_cdp_port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={settings.flow_profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        # Flow's labels follow the browser language; the tools expect English.
        "--lang=en-US",
        "--accept-lang=en-US,en",
        # Several Google apps run in tabs at once (Flow, Gemini, Notebook...);
        # Chrome would otherwise pause the background ones mid-answer.
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        url,
    ]
    flags = 0
    if platform.system() == "Windows":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        start_new_session=platform.system() != "Windows",
    )
    for _ in range(40):
        if port_open(settings.flow_cdp_port):
            return
        time.sleep(0.25)
    raise FlowError(
        f"Chrome started but its debugging port {settings.flow_cdp_port} did not open. "
        "Close other windows of this profile and try again."
    )


def login(settings: Settings) -> int:
    """CLI: opens the Flow profile so the user can sign in to Google."""
    try:
        launch_chrome(settings)
    except FlowError as e:
        print(f"Error: {e}")
        return 1
    print(
        "A Chrome window with the Flow profile is open at flow.google.com.\n"
        "1. Sign in with the Google account that has Google AI Pro / Ultra.\n"
        "2. Open Flow once and accept its terms if asked.\n"
        "You can close the window afterwards; the MCP server reopens it when needed.\n"
        f"Profile folder: {settings.flow_profile_dir}"
    )
    return 0


# One CDP connection per server process, shared by every tool call. Each new
# Playwright connection resets Chrome's download handling, which silently broke
# downloads still running on another connection (0-byte files).
_shared: dict = {"playwright": None, "browser": None, "loop": None}


async def connect(settings: Settings):
    """Returns (playwright, browser) attached to the signed-in Chrome profile.
    The connection is shared and stays open; callers must not close it."""
    loop = asyncio.get_running_loop()
    browser = _shared["browser"]
    if browser is not None and _shared["loop"] is loop and browser.is_connected():
        return _shared["playwright"], browser
    if _shared["playwright"] is not None and _shared["loop"] is loop:
        try:
            await _shared["playwright"].stop()
        except Exception:
            pass
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise FlowError(
            "The Flow tools need Playwright: install with `pip install gemini-pro-mcp[flow]` "
            "(or `uvx --with playwright gemini-pro-mcp`)."
        ) from e
    launch_chrome(settings)
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{settings.flow_cdp_port}"
        )
    except Exception:
        await playwright.stop()
        raise
    _shared.update(playwright=playwright, browser=browser, loop=loop)
    return playwright, browser
