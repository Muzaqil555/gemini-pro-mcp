# Install gemini-pro-mcp from its repository link

When a user shares the repository link and asks you to install or connect it, use the client they name or the client you are running in. The server runs locally over stdio. Check that `uvx --version` works on that machine. If needed, install uv for the current user. [Official uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/)

## Claude Code

Install the **Claude Code plugin** by default, including when the user describes this project as an MCP. The plugin supplies the server, the `gemini-pro` skill and six slash commands in one installation.

1. Run `claude plugin list --json` and look for the exact ID `gemini-pro@gemini-pro-mcp`. A standalone MCP entry only confirms that the server was registered.
2. If the plugin is missing, run `claude plugin install gemini-pro --marketplace Muzaqil555/gemini-pro-mcp`. If it is already installed but disabled, run `claude plugin enable gemini-pro@gemini-pro-mcp`.
3. Verify the ID is enabled in `claude plugin list --json`. Start a fresh Claude Code session if needed, then call the plugin's `google_pro_benefits` tool. The user can also try `/gemini-pro:second-opinion`.

If the user explicitly asks for **standalone MCP only**, run `uvx gemini-pro-mcp setup --client claude`. On a machine with an existing standalone registration, preserve its settings and use the plugin's connection when checking the plugin.

## Other clients

If the chosen client already has a working `gemini-pro` connection, go straight to verification. Otherwise run its command on the machine that hosts the client.

| Host | Command |
|---|---|
| Gemini CLI | `uvx gemini-pro-mcp setup --client gemini` |
| Antigravity | `uvx gemini-pro-mcp setup --client agy` |
| Cursor | `uvx gemini-pro-mcp setup --client cursor` |
| Codex | `uvx gemini-pro-mcp setup --client codex` |
| Claude Desktop | `uvx gemini-pro-mcp setup --client claude-desktop` |
| Windsurf | `uvx gemini-pro-mcp setup --client windsurf` |

For another host with local stdio support, use its native MCP registration tool or configuration format. Set the executable to the resolved path of `uvx`, with the single argument `gemini-pro-mcp`. The [registry manifest](server.json) identifies the published package and transport. Hosted clients that accept only a remote HTTPS endpoint require a different deployment.

## Verify the connection

Reload MCP through the host if it supports that operation. Once the tool is available, call `google_pro_benefits` with `{}`. It works without Google sign-in or API keys. If a new session or a permission prompt is required, tell the user the one action to take and report which check has actually passed. Gemini CLI also requires a trusted project folder.

For a subsequent live Gemini code review, the user signs in once with the Antigravity CLI (`agy`). Users who request the [Gemini CLI extension](README.md#try-it-in-your-coding-agent) can install it directly with `gemini extensions install https://github.com/Muzaqil555/gemini-pro-mcp`.
