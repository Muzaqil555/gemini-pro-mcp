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

## Where things live

| Path | What |
|---|---|
| `src/gemini_pro_mcp/server.py` | Builds the server and the CLI (`serve`, `setup`, `doctor`, `flow-login`) |
| `src/gemini_pro_mcp/agy.py` | `gemini_*` tools through the Antigravity CLI |
| `src/gemini_pro_mcp/media.py` | Gemini API video and image tools |
| `src/gemini_pro_mcp/jules.py` | `jules_*` tools (official API) |
| `src/gemini_pro_mcp/google_web.py` | `gemini_app`, `google_ai_mode`, `google_page`, `google_act` |
| `src/gemini_pro_mcp/notebook.py` | `notebook_*` tools |
| `src/gemini_pro_mcp/flow/` | `flow_*` tools and the shared Chrome connection |
| `src/gemini_pro_mcp/install.py` | `setup` and `doctor` |

## Adding a tool

1. Write it as an `async def` inside the `register()` function of the module it belongs to. The docstring becomes the tool description the model reads, so say what the tool does, what it costs and what it returns.
2. Decorate it with `@mcp.tool(annotations=...)`. Tools that spend money or credits use the module's `paid` helper instead, which marks them and adds the confirmation sentence.
3. Add its name to `BASE` or `FLOW` in `tests/test_server.py`, and test its logic with fakes in `tests/`.
4. List it in the README's tool tables.

## Good first issues

Open tasks for newcomers are labelled [`good first issue`](https://github.com/Muzaqil555/gemini-pro-mcp/labels/good%20first%20issue): Lyria music, Flow images, Deep Research reports, testing on macOS and Linux, README translations and support for more Google AI sites. Comment on one to take it. Questions are welcome in [Discussions](https://github.com/Muzaqil555/gemini-pro-mcp/discussions).

## Pull requests

Keep them focused, add or update tests, and describe how you checked the change, for example "generated one 720p video" or "ran gemini_research".
