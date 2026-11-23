import asyncio
import sys
import threading
import types

import pytest

from gemini_pro_mcp.config import Settings
from gemini_pro_mcp.flow import browser


async def test_connect_starts_chrome_off_the_event_loop(monkeypatch, tmp_path):
    # launch_chrome waits up to 10 s for Chrome's port with time.sleep; on the
    # event loop that would stall every other tool call of the server.
    threads = []

    def fake_launch(settings):
        threads.append(threading.current_thread())
        raise browser.FlowError("no chrome")

    # Stub playwright so the test runs even when the optional [flow] extra is not installed.
    fake_playwright = types.ModuleType("playwright")
    fake_async_api = types.ModuleType("playwright.async_api")
    fake_async_api.async_playwright = None
    fake_playwright.async_api = fake_async_api
    monkeypatch.setitem(sys.modules, "playwright", fake_playwright)
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_async_api)
    monkeypatch.setattr(browser, "launch_chrome", fake_launch)
    settings = Settings(
        output_dir=tmp_path,
        agy_path=None,
        agy_model=None,
        agy_timeout=1,
        flow_enabled=True,
        flow_profile_dir=tmp_path,
        flow_cdp_port=9,
        flow_project=None,
    )
    with pytest.raises(browser.FlowError, match="no chrome"):
        await browser.connect(settings)
    assert threads and threads[0] is not threading.main_thread()


async def test_concurrent_cold_starts_share_one_browser(monkeypatch):
    launches = []
    connections = []
    connected = types.SimpleNamespace(is_connected=lambda: True)

    async def connect_over_cdp(url):
        connections.append(url)
        await asyncio.sleep(0)
        return connected

    playwright = types.SimpleNamespace(
        chromium=types.SimpleNamespace(connect_over_cdp=connect_over_cdp)
    )

    async def start():
        return playwright

    api = types.ModuleType("playwright.async_api")
    api.async_playwright = lambda: types.SimpleNamespace(start=start)
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.async_api", api)
    monkeypatch.setattr(browser, "_shared", dict(playwright=None, browser=None, loop=None))
    monkeypatch.setattr(browser, "launch_chrome", lambda settings: launches.append(settings))
    settings = Settings.from_env()
    first, second = await asyncio.gather(browser.connect(settings), browser.connect(settings))
    assert first == second == (playwright, connected)
    assert len(launches) == len(connections) == 1
