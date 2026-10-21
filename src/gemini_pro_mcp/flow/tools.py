"""EXPERIMENTAL Google Flow tools (opt-in with GEMINI_PRO_ENABLE_FLOW=1).

Flow has no public API. These tools drive flow.google.com in the user's own
signed-in Chrome profile, spending the Flow credits of their Google AI plan.
They depend on Flow's web page and can break when Google changes it.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from ..config import Settings
from .browser import FLOW_URL, FlowError, connect


async def flow_page(browser):
    """The open Flow tab, or a new one."""
    pages = [page for context in browser.contexts for page in context.pages]
    for page in pages:
        if "flow.google.com" in page.url:
            return page
    context = browser.contexts[0] if browser.contexts else await browser.new_context()
    page = await context.new_page()
    await page.goto(FLOW_URL, wait_until="domcontentloaded")
    return page


def register(mcp: MCPServer, settings: Settings) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def flow_status() -> str:
        """EXPERIMENTAL: check that Google Flow is open and signed in.

        Opens the dedicated Chrome profile if needed. Free.

        Returns:
            Whether Flow is ready, or what the user has to do first.
        """
        try:
            playwright, browser = await connect(settings)
        except FlowError as e:
            return f"Error: {e}"
        try:
            page = await flow_page(browser)
            await page.wait_for_load_state("domcontentloaded")
            if "accounts.google.com" in page.url:
                return (
                    "Not signed in. Ask the user to run `gemini-pro-mcp flow-login` and "
                    "sign in to Google in the window that opens."
                )
            return f"Flow is open and ready: {page.url} ({await page.title()})"
        finally:
            await browser.close()  # disconnects; the user's Chrome keeps running
            await playwright.stop()
