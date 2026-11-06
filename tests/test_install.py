import dataclasses
import json

from gemini_pro_mcp import install
from gemini_pro_mcp.config import Settings

COMMAND = "uvx"
ARGS = ["--from", "gemini-pro-mcp[flow] @ git+https://example.com/repo", "gemini-pro-mcp"]
ENV = {"GEMINI_PRO_ENABLE_BROWSER": "1"}

CODEX = """\
model = "gpt-5"

[mcp_servers.rea]
command = "npx"
args = ["-y", "rea"]

[mcp_servers.gemini-pro]
command = "old"
args = []

[mcp_servers.gemini-pro.env]
OLD = "1"

[mcp_servers.stitch]
url = "https://stitch.example"
"""


def test_codex_config_replaces_only_this_server():
    text = install.codex_config(CODEX, "gemini-pro", COMMAND, ARGS, ENV)
    assert 'command = "old"' not in text and "OLD" not in text
    assert text.count("[mcp_servers.rea]") == 1 and text.count("[mcp_servers.stitch]") == 1
    assert 'model = "gpt-5"' in text
    assert '[mcp_servers."gemini-pro"]' in text
    assert '"gemini-pro-mcp[flow] @ git+https://example.com/repo"' in text
    assert f"tool_timeout_sec = {install.TOOL_TIMEOUT_SECONDS}" in text
    assert 'GEMINI_PRO_ENABLE_BROWSER = "1"' in text
    # Running setup again replaces its own (quoted) tables instead of adding more.
    again = install.codex_config(text, "gemini-pro", COMMAND, ARGS, {})
    assert again.count('[mcp_servers."gemini-pro"]') == 1
    assert "GEMINI_PRO_ENABLE_BROWSER" not in again


def test_codex_config_escapes_windows_paths():
    text = install.codex_config("", "gemini-pro", r"C:\Users\me\uv.exe", [], {})
    assert text.startswith('[mcp_servers."gemini-pro"]')
    assert r'command = "C:\\Users\\me\\uv.exe"' in text


def test_gemini_settings_keep_other_keys():
    old = json.dumps({"theme": "dark", "mcpServers": {"other": {"command": "x"}}})
    data = json.loads(install.gemini_settings(old, "gemini-pro", COMMAND, ARGS, ENV))
    assert data["theme"] == "dark" and "other" in data["mcpServers"]
    server = data["mcpServers"]["gemini-pro"]
    assert server["args"] == ARGS and server["env"] == ENV
    assert server["timeout"] == install.TOOL_TIMEOUT_SECONDS * 1000
    assert (
        "gemini-pro"
        in json.loads(install.gemini_settings("", "gemini-pro", "uvx", [], {}))["mcpServers"]
    )


def test_client_commands():
    claude = install.claude_commands("claude", "gemini-pro", COMMAND, ARGS, ENV)
    assert claude[0] == ["claude", "mcp", "remove", "gemini-pro", "--scope", "user"]
    assert claude[1][:6] == ["claude", "mcp", "add", "gemini-pro", "--scope", "user"]
    assert claude[1][6:9] == ["-e", "GEMINI_PRO_ENABLE_BROWSER=1", "--"]
    assert claude[1][9:] == [COMMAND, *ARGS]
    (agy,) = install.agy_commands("agy", "gemini-pro", COMMAND, ARGS, ENV)
    assert agy[:5] == ["agy", "mcp", "add", "--env", "GEMINI_PRO_ENABLE_BROWSER=1"]
    assert agy[5:7] == ["gemini-pro", "--"] and agy[7:] == [COMMAND, *ARGS]


def test_server_command(monkeypatch, tmp_path):
    monkeypatch.setattr(install, "source_root", lambda: None)
    _, args = install.server_command(browser=False)
    assert args == ["--from", f"git+{install.REPO}", "gemini-pro-mcp"]
    _, args = install.server_command(browser=True)
    assert args[1] == f"gemini-pro-mcp[flow] @ git+{install.REPO}"
    monkeypatch.setattr(install, "source_root", lambda: tmp_path)
    _, args = install.server_command(browser=True)
    assert args == ["--directory", tmp_path.as_posix(), "run", "--extra", "flow", "gemini-pro-mcp"]


def test_setup_writes_file_clients(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(install.shutil, "which", lambda name: None)
    monkeypatch.setattr(install, "run_checks", lambda settings, live_flow=False: [])
    monkeypatch.setattr(install, "source_root", lambda: None)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".gemini").mkdir()
    (tmp_path / ".gemini" / "settings.json").write_text('{"theme": "dark"}')
    settings = dataclasses.replace(
        Settings.from_env(), agy_path=None, flow_profile_dir=tmp_path / "profile"
    )

    def run(**changes):
        options = dict(
            clients=list(install.CLIENTS),
            name="gemini-pro",
            browser=True,
            auto_approve=False,
            dry_run=False,
            home=tmp_path,
        )
        return install.setup(settings, **{**options, **changes})

    assert run(dry_run=True) == 0
    assert not (tmp_path / ".codex" / "config.toml").exists()  # a dry run changes nothing
    assert run() == 0
    out = capsys.readouterr().out
    assert "Claude Code not found" in out and "flow-login" in out
    assert "GEMINI_PRO_ENABLE_BROWSER" in (tmp_path / ".codex" / "config.toml").read_text()
    data = json.loads((tmp_path / ".gemini" / "settings.json").read_text())
    assert data["theme"] == "dark" and "gemini-pro" in data["mcpServers"]
    assert (tmp_path / ".gemini" / "settings.json.bak").exists()


def test_setup_without_clients_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(install.shutil, "which", lambda name: None)
    monkeypatch.setattr(install, "run_checks", lambda settings, live_flow=False: [])
    monkeypatch.delenv("CODEX_HOME", raising=False)
    settings = dataclasses.replace(Settings.from_env(), agy_path=None)
    code = install.setup(
        settings,
        clients=list(install.CLIENTS),
        name="gemini-pro",
        browser=False,
        auto_approve=False,
        dry_run=False,
        home=tmp_path,
    )
    assert code == 1


def test_key_check(monkeypatch):
    monkeypatch.delenv("JULES_API_KEY", raising=False)
    missing = install.key_check("Jules", ("JULES_API_KEY",), "jules tools", "https://x")
    assert missing.ok is None and "JULES_API_KEY=" in missing.detail
    monkeypatch.setenv("JULES_API_KEY", "secret")
    found = install.key_check("Jules", ("JULES_API_KEY",), "jules tools", "https://x")
    assert found.ok is True and "secret" not in found.detail
