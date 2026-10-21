# Contributing

Thanks for helping! Issues, ideas and pull requests are all welcome.

## Setup

```bash
git clone https://github.com/Muzaqil555/gemini-pro-mcp
cd gemini-pro-mcp
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Try your local copy in Claude Code:

```bash
claude mcp add gemini-pro-dev -- uv --directory /path/to/gemini-pro-mcp run gemini-pro-mcp
```

## Ground rules

- **Never handle user credentials.** The server must not type, store or log passwords, cookies or API keys. Sign-in is always done by the user.
- **No stealth.** Do not add fingerprint spoofing, CAPTCHA solving or any other bot-detection evasion. If Google blocks automation, the user decides what to do.
- **Paid calls stay explicit.** Every tool that spends money or credits must say so in its description, so the model asks the user first.
- **Tests without network.** Unit tests use fakes (see `tests/`). Calls to the real API or `agy` belong in manual checks, not in CI.

## Good first issues

- Flow: download images (only videos are tested), and use the Scenes view to stitch several clips into a longer video.
- Lyria music generation through the Gemini API.
- A demo GIF for the README.
- Docs for more MCP clients (Cursor, Windsurf, VS Code, Zed).

## Pull requests

Keep them focused, add or update tests, and describe how you checked the change, for example "generated one 720p video" or "ran gemini_research".
