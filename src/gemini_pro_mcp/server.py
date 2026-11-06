"""gemini-pro-mcp: Google AI Pro and the Gemini API as MCP tools."""

from __future__ import annotations

import argparse
import sys

from mcp.server.mcpserver import MCPServer

from . import __version__, agy, benefits, install, jules, media, stitch
from .config import Settings, load_env_file

INSTRUCTIONS = """\
Tools for everything a Google AI Pro plan includes. google_pro_benefits lists each
benefit and the tool that reaches it; start there when unsure.

- gemini_ask, gemini_research, gemini_code, gemini_agents, gemini_models: Gemini
  through the Antigravity CLI on the user's Google AI Pro subscription. No API cost;
  second opinions, reading local files, sourced web research, and gemini_code, which
  EDITS files in a given folder (delegate a coding task, then review the diff).
- jules_*: Jules, Google's cloud coding agent, on GitHub repos (official API; needs
  JULES_API_KEY from jules.google.com/settings).
- notebook_*: Gemini Notebook (formerly NotebookLM): notebooks, sources, grounded
  questions, Studio outputs (Audio/Video Overviews, slides, mind maps, quizzes...).
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
  - flow_collect downloads results.
- gemini_app (Gemini app: 4 Argon, Deep Research, images, Veo videos, music,
  Canvas, files), gemini_app_result, google_ai_mode (AI Mode in Search), and
  google_page / google_act, which read and operate ANY Google AI site like a person:
  Flow, Gemini Notebooks, AI Studio, Jules, Colab, Flow Music, Docs/Drive.

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
    jules.register(server, settings)
    if settings.flow_enabled:
        from . import google_web, notebook
        from .flow import tools as flow_tools

        flow_tools.register(server, settings)
        google_web.register(server, settings)
        notebook.register(server, settings)
    else:
        benefits.register(server)
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
    doctor = sub.add_parser("doctor", help="check what works and how to fix the rest")
    doctor.add_argument(
        "--flow", action="store_true", help="also open Flow and check the sign-in and credits"
    )
    setup = sub.add_parser(
        "setup", help="add the server to Claude Code, Codex, Antigravity and Gemini CLI"
    )
    setup.add_argument(
        "--client",
        action="append",
        choices=install.CLIENTS,
        help="only this client (repeatable); default: every one that is installed",
    )
    setup.add_argument(
        "--browser",
        action="store_true",
        help="enable the browser tools (Flow, Gemini app, AI Mode, Notebooks)",
    )
    setup.add_argument(
        "--auto-approve",
        action="store_true",
        help="pre-approve spending: paid tools run without asking first",
    )
    setup.add_argument("--name", default=install.DEFAULT_NAME, help="server name in the clients")
    setup.add_argument("--dry-run", action="store_true", help="show what would change")
    args = parser.parse_args(argv)

    load_env_file()
    if args.command == "flow-login":
        from .flow.browser import login

        sys.exit(login(Settings.from_env()))
    if args.command == "doctor":
        sys.exit(install.doctor(Settings.from_env(), live_flow=args.flow))
    if args.command == "setup":
        sys.exit(
            install.setup(
                Settings.from_env(),
                clients=args.client or list(install.CLIENTS),
                name=args.name,
                browser=args.browser,
                auto_approve=args.auto_approve,
                dry_run=args.dry_run,
            )
        )
    build_server().run()


if __name__ == "__main__":
    main()
