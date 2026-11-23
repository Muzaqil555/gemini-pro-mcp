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
