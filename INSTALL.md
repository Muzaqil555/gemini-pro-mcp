# Install gemini-pro-mcp from its repository link

When a user asks you to connect this repository as MCP, install the released package for the client where they want to use it. You can do this from their existing project. The server uses local stdio and the registration name is `gemini-pro`.

1. Identify the client from the user's request or your own host. If it already has a working `gemini-pro` connection, including one supplied by a plugin or extension, go straight to verification.
2. Run `uvx --version`. If the executable is missing, install uv for the current user using the method for their platform, then locate `uvx` in the new installation. [Official uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/)
3. Run the command for that client in a terminal on the machine that runs the client.

| Host | Command |
|---|---|
| Claude Code | `uvx gemini-pro-mcp setup --client claude` |
| Gemini CLI | `uvx gemini-pro-mcp setup --client gemini` |
| Antigravity | `uvx gemini-pro-mcp setup --client agy` |
| Cursor | `uvx gemini-pro-mcp setup --client cursor` |
| Codex | `uvx gemini-pro-mcp setup --client codex` |
| Claude Desktop | `uvx gemini-pro-mcp setup --client claude-desktop` |
| Windsurf | `uvx gemini-pro-mcp setup --client windsurf` |

For another host with local stdio support, use its native MCP registration tool or configuration format. Set the executable to the resolved path of `uvx`, with the single argument `gemini-pro-mcp`. The [registry manifest](server.json) identifies the published package and transport. Hosted clients that accept only a remote HTTPS endpoint require a different deployment.

## Verify the connection

Reload MCP through the host if it supports that operation. Once the tool is available, call `google_pro_benefits` with `{}`. It works without Google sign-in or API keys. If a new session or a permission prompt is required, tell the user the one action to take and report which check has actually passed. Gemini CLI also requires a trusted project folder.

For a subsequent live Gemini code review, the user signs in once with the Antigravity CLI (`agy`). The [Claude plugin and Gemini CLI extension](README.md#try-it-in-your-coding-agent) are available when the user specifically wants those integrations.
