import sys
from pathlib import Path

import pytest

from gemini_pro_mcp import install
from gemini_pro_mcp.config import Settings
from gemini_pro_mcp.flow import browser


def test_a_wrong_chrome_path_is_not_reported_as_found(tmp_path, monkeypatch):
    missing = str(tmp_path / "chrome.exe")
    monkeypatch.setenv("GEMINI_PRO_CHROME", missing)
    assert browser.find_chrome() is None
    (chrome,) = [c for c in install.browser_checks(Settings.from_env()) if c.name == "Chrome"]
    assert chrome.ok is None
    assert "GEMINI_PRO_CHROME" in chrome.detail and missing in chrome.detail
    monkeypatch.setattr(browser, "port_open", lambda port: False)
    with pytest.raises(browser.FlowError, match="GEMINI_PRO_CHROME"):
        browser.launch_chrome(Settings.from_env())


def test_chrome_path_from_the_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_PRO_CHROME", sys.executable)  # any real program will do
    assert Path(browser.find_chrome()).samefile(sys.executable)
