"""server.json (the MCP Registry entry) must match the package it points to."""

import json
import tomllib
from pathlib import Path

from gemini_pro_mcp import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_server_json_matches_package():
    server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert server["version"] == project["version"] == __version__
    package = server["packages"][0]
    assert package["identifier"] == project["name"]
    assert package["version"] == project["version"]
    assert len(server["description"]) <= 100
    assert f"mcp-name: {server['name']}" in (ROOT / "README.md").read_text(encoding="utf-8")
