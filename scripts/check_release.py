"""Exercise the server shipped via the Claude marketplace, a wheel, or PyPI."""

import argparse
import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from mcp import ClientSession, StdioServerParameters, stdio_client

from gemini_pro_mcp import __version__

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = {
    "gemini_review",
    "gemini_research",
    "second_opinion",
    "jules_task",
    "notebook_workflow",
    "make_video",
}


async def check(command, args, env=None):
    params = StdioServerParameters(command=command, args=args, env=env)
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as session:
        init = await session.initialize()
        assert init.server_info.version == __version__, init.server_info
        tools = {t.name for t in (await session.list_tools()).tools}
        assert {"gemini_ask", "google_pro_benefits"} <= tools, tools
        prompts = {p.name for p in (await session.list_prompts()).prompts}
        assert PROMPTS == prompts, prompts
        prompt = await session.get_prompt("second_opinion", {"question": "Can zero be a price?"})
        assert "Can zero be a price?" in prompt.messages[0].content.text
        result = await session.call_tool("google_pro_benefits", {})
        assert not result.is_error and "gemini_ask" in result.content[0].text, result
        print(f"{init.server_info.version}: {len(tools)} tools, {len(prompts)} prompts, call OK")


def plugin_launcher(profile):
    env = {**os.environ, "CLAUDE_CONFIG_DIR": str(profile)}
    claude = shutil.which("claude")
    if not claude:
        raise RuntimeError("Install the Claude Code CLI to check the marketplace package")
    subprocess.run(
        [claude, "plugin", "install", "gemini-pro", "--marketplace", str(ROOT)],
        cwd=profile,
        env=env,
        check=True,
    )
    installed = subprocess.check_output(
        [claude, "plugin", "list", "--json"], cwd=profile, env=env, text=True, encoding="utf-8"
    )
    plugin = next(p for p in json.loads(installed) if p["id"] == "gemini-pro@gemini-pro-mcp")
    assert plugin["enabled"], "Claude installed the plugin but did not enable it"
    folder = Path(plugin["installPath"])
    assert (folder / "skills" / "gemini-pro" / "SKILL.md").is_file()
    commands = {path.stem for path in (folder / "commands").glob("*.md")}
    expected = {"gemini-review", "gemini-research", "second-opinion", "jules", "notebook", "video"}
    assert expected <= commands, f"Missing plugin commands: {sorted(expected - commands)}"
    manifest = json.loads((folder / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["version"] == __version__
    server = manifest["mcpServers"]["gemini-pro"]
    return server["command"], server["args"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plugin", action="store_true")
    group.add_argument("--package", help="Wheel path or exact published package specification")
    options = parser.parse_args()
    with TemporaryDirectory() as directory:
        if options.plugin:
            command, args = plugin_launcher(Path(directory))
        else:
            command, args = "uvx", ["--from", options.package, "gemini-pro-mcp"]
        asyncio.run(asyncio.wait_for(check(command, args), timeout=180))


if __name__ == "__main__":
    main()
