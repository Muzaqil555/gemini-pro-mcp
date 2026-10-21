"""gemini-pro-mcp: Google AI Pro and the Gemini API as MCP tools."""

from __future__ import annotations

import argparse
import sys

from mcp.server.mcpserver import MCPServer

from . import __version__, agy, media, stitch
from .config import Settings, load_env_file

INSTRUCTIONS = """\
Tools for Google's Gemini, in three groups:

- gemini_ask, gemini_research, gemini_models: Gemini through the Antigravity CLI on
  the user's Google AI Pro subscription. No API cost; good for second opinions,
  reading local files and sourced web research.
- video_generate, video_edit, video_check, image_generate, video_stitch: the official
  Gemini API (video_stitch is local and free). The generation tools COST MONEY, billed
  to the API key's Google Cloud project.
- flow_* (only if enabled): EXPERIMENTAL, drives Google Flow in the user's own
  signed-in Chrome and spends their monthly Flow credits. EVERY Flow feature is
  reachable:
  - flow_make_video turns "a 2 minute video of ..." into clips and one stitched file;
  - flow_generate talks to Flow's agent (videos, images, edits, extensions, characters);
  - flow_tools / flow_open_tool use any Flow tool (Image Editor, Video Resizer,
    Transition Machine, Type Overlays, community tools...);
  - flow_page / flow_act operate any Flow page or tool like a person (Characters,
    Scenes, Library, uploads, upscaling); flow_collect downloads results.

{spending}

Generated files are saved locally; tool results give the path.
"""

ASK = "Before any paid call, tell the user roughly what it costs and get their OK."
AUTO = (
    "The user has pre-approved spending (GEMINI_PRO_AUTO_APPROVE): do not ask before "
    "paid calls; just do what they asked and report the cost afterwards."
)


def build_server(settings: Settings | None = None) -> MCPServer:
    settings = settings or Settings.from_env()
    server = MCPServer(
        "gemini_pro_mcp",
        instructions=INSTRUCTIONS.format(spending=AUTO if settings.auto_approve else ASK),
        version=__version__,
        website_url="https://github.com/Muzaqil555/gemini-pro-mcp",
    )
    agy.register(server, settings)
    media.register(server, settings)
    stitch.register(server, settings)
    if settings.flow_enabled:
        from .flow import tools as flow_tools

        flow_tools.register(server, settings)
    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="gemini-pro-mcp",
        description="MCP server for Google AI Pro (Antigravity, Flow) and the Gemini API.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="run the MCP server over stdio (default)")
    sub.add_parser(
        "flow-login",
        help="open the Chrome profile used by the Flow tools so you can sign in",
    )
    args = parser.parse_args(argv)

    load_env_file()
    if args.command == "flow-login":
        from .flow.browser import login

        sys.exit(login(Settings.from_env()))
    build_server().run()


if __name__ == "__main__":
    main()
