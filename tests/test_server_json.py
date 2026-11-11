"""server.json (the MCP Registry entry) must match the package it points to."""

import json
import re
from pathlib import Path

from gemini_pro_mcp import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_server_json_matches_package():
    server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project = dict(re.findall(r'^(name|version) = "([^"]+)"', pyproject, re.MULTILINE))
    assert server["version"] == project["version"] == __version__
    package = server["packages"][0]
    assert package["identifier"] == project["name"]
    assert package["version"] == project["version"]
    assert len(server["description"]) <= 100
    assert f"mcp-name: {server['name']}" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_extension_and_plugin_manifests_match_package():
    """The Gemini CLI extension and the Claude Code plugin start the same package."""
    extension = json.loads((ROOT / "gemini-extension.json").read_text(encoding="utf-8"))
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert extension["version"] == plugin["version"] == __version__
    for manifest in (extension, plugin):
        assert manifest["mcpServers"]["gemini-pro"] == {
            "command": "uvx",
            "args": ["gemini-pro-mcp"],
        }
    assert [p["name"] for p in market["plugins"]] == [plugin["name"]]
