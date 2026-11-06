# Runs the MCP server over stdio, e.g. for MCP directories that start it and
# list its tools. The subscription tools still need the Antigravity CLI and the
# browser tools need a signed-in Chrome, so for real use install it locally
# with `uvx ... gemini-pro-mcp setup` (see the README).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "--frozen", "--no-dev", "gemini-pro-mcp"]
