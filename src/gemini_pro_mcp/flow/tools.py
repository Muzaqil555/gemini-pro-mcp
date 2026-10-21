"""EXPERIMENTAL Google Flow tools (opt-in with GEMINI_PRO_ENABLE_FLOW=1).

Flow has no public API. These tools drive flow.google.com in the user's own
signed-in Chrome profile and spend the Flow credits of their Google AI plan.
They depend on Flow's web page and can break when Google changes it.

Flow is an agent: you send a request, and before spending credits it asks for
permission ("...costing 12 credits?"). `flow_generate` stops at that question
and returns it; only `flow_approve` answers it. So credits are never spent
without a separate, explicit call.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from ..config import Settings
from .browser import FlowError, connect

HOME = "https://flow.google.com/?hl=en"
PROJECT = "https://flow.google.com/project/{id}?hl=en"

# Selectors. Custom element names and Material icon ligatures (the text of
# icon buttons, e.g. "arrow_forward") do not depend on the page language.
PROMPT_BOX = 'div[role="textbox"][contenteditable="true"]'
SUBMIT = 'button[type="submit"]'
NEW_SESSION = 'button:has-text("edit_square")'
BUBBLE = "flow-chat-bubble"
PERMISSION = "flow-permission-message"
PERMISSION_OPTION = f'{PERMISSION} [role="radio"]'
PROJECT_LINK = 'a[href^="/project/"]'
ACCOUNT_BUTTON = 'div[role="button"]:has-text("PRO"), div[role="button"]:has-text("ULTRA")'
ACCOUNT_CLOSE = 'button[aria-label="Close account panel"]'

# The project's media grid, in Flow's order (newest first). Thumbnail URLs
# change between page loads, so a tile is identified by its label + thumbnail
# only within one page load.
TILE = "flow-grid-tile-container"
MEDIA_JS = r"""() => [...document.querySelectorAll('flow-grid-tile-container')]
  .map((tile, index) => {
  const img = tile.querySelector('img');
  return {index, kind: tile.querySelector('flow-video-tile') ? 'video' : 'image',
          label: tile.getAttribute('aria-label') || '',
          key: (tile.getAttribute('aria-label') || '') + '|' + (img ? img.src.split('?')[0] : ''),
          ready: !!img};
})"""

# The editor's "Download media" button (its icon ligature is "download").
DOWNLOAD_MENU = 'button[aria-haspopup="menu"]:has-text("download")'

PAID = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
)


class Flow:
    """One connection to the Flow Chrome profile, for the length of a tool call."""

    def __init__(self, settings: Settings):
        self.settings = settings

    async def __aenter__(self):
        self.playwright, self.browser = await connect(self.settings)
        self.page = await self._page()
        return self

    async def __aexit__(self, *exc):
        await self.browser.close()  # disconnects; the user's Chrome keeps running
        await self.playwright.stop()

    async def _page(self):
        pages = [page for context in self.browser.contexts for page in context.pages]
        for page in pages:
            if "flow.google.com" in page.url:
                return page
        context = self.browser.contexts[0]
        page = await context.new_page()
        await page.goto(HOME, wait_until="domcontentloaded")
        return page

    def signed_out(self) -> bool:
        return "accounts.google.com" in self.page.url or "/about" in self.page.url

    async def open_project(self, project_id: str | None = None) -> str:
        """Opens the given, configured, current or most recent project."""
        page = self.page
        wanted = project_id or self.settings.flow_project
        current = re.search(r"/project/([0-9a-f-]{36})", page.url)
        if wanted:
            target = PROJECT.format(id=wanted)
        elif current:
            target = PROJECT.format(id=current.group(1))
        else:
            await page.goto(HOME, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            if self.signed_out():
                raise FlowError(SIGN_IN)
            link = page.locator(PROJECT_LINK).first
            if not await link.count():
                raise FlowError(
                    "No Flow project found. Create one at flow.google.com, or pass project_id."
                )
            target = "https://flow.google.com" + (await link.get_attribute("href")) + "?hl=en"
        if page.url.split("#")[0] != target:
            await page.goto(target, wait_until="domcontentloaded")
        await page.locator(PROMPT_BOX).first.wait_for(timeout=30_000)
        if self.signed_out():
            raise FlowError(SIGN_IN)
        await self.close_account_panel()
        return re.search(r"/project/([0-9a-f-]{36})", page.url).group(1)

    async def busy(self) -> bool:
        text = (await self.page.locator(SUBMIT).first.inner_text()).strip()
        return text == "stop"

    async def wait_for_agent(self, timeout: float) -> None:
        """Waits until the agent stops working or asks for permission."""
        deadline = time.monotonic() + timeout
        await self.page.wait_for_timeout(2000)
        while time.monotonic() < deadline:
            if await self.pending_permission() is not None or not await self.busy():
                return
            await self.page.wait_for_timeout(2000)

    async def pending_permission(self):
        """The newest permission question that has not been answered, or None."""
        messages = self.page.locator(PERMISSION)
        count = await messages.count()
        if not count:
            return None
        last = messages.nth(count - 1)
        options = last.locator('[role="radio"]')
        if not await options.count():
            return None
        for i in range(await options.count()):
            option = options.nth(i)
            if (await option.get_attribute("aria-checked")) == "true" or (
                await option.get_attribute("aria-disabled")
            ) == "true":
                return None
        return last

    async def last_reply(self) -> str:
        bubbles = self.page.locator(BUBBLE)
        count = await bubbles.count()
        if not count:
            return ""
        text = await bubbles.nth(count - 1).inner_text()
        # Drop icon ligatures and feedback buttons from the copied text.
        noise = {"check", "close", "thumb_up", "thumb_down", "content_copy", "flag"}
        noise |= {"Approve", "Always approve", "Reject"}
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line and line not in noise)

    async def media(self) -> list[dict]:
        return await self.page.evaluate(MEDIA_JS)

    async def close_overlays(self) -> None:
        backdrop = self.page.locator(".cdk-overlay-backdrop")
        if await backdrop.count():
            await backdrop.first.click()
            await self.page.wait_for_timeout(300)

    async def wait_for_media(self, timeout: float = 15) -> list[dict]:
        """The grid fills in after the chat; wait a little for its tiles."""
        deadline = time.monotonic() + timeout
        items = await self.media()
        while not items and time.monotonic() < deadline:
            await self.page.wait_for_timeout(1000)
            items = await self.media()
        return items

    async def download(self, item: dict, output_dir: Path, stem: str) -> Path | None:
        """Saves one grid item in its original size through Flow's own Download
        menu (free; upscaled sizes cost credits and are skipped). Returns None
        if the item is not ready yet."""
        if not item["ready"]:
            return None
        page = self.page
        project = re.search(r"/project/([0-9a-f-]{36})", page.url)
        await self.close_overlays()
        await page.locator(TILE).nth(item["index"]).locator("img").first.click()
        try:
            menu = page.locator(DOWNLOAD_MENU).first
            try:
                await menu.wait_for(timeout=20_000)
            except Exception:
                return None  # no Download button: still rendering
            await menu.click()
            options = page.get_by_role("menuitem")
            await options.first.wait_for(timeout=10_000)
            choice = None
            for i in range(await options.count()):
                option = options.nth(i)
                text = await option.inner_text()
                if await option.is_disabled() or "GIF" in text:
                    continue
                if choice is None or "720p" in text or "Original" in text:
                    choice = option
                if "720p" in text or "Original" in text:
                    break
            if choice is None:
                return None
            async with page.expect_download(timeout=120_000) as info:
                await choice.click()
            download = await info.value
            extension = Path(download.suggested_filename).suffix or (
                ".mp4" if item["kind"] == "video" else ".png"
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / f"{stem}{extension}"
            n = 2
            while path.exists():
                path = output_dir / f"{stem}-{n}{extension}"
                n += 1
            await download.save_as(path)
            return path
        finally:
            if project and "/edit/" in page.url:  # back from the editor
                await page.goto(PROJECT.format(id=project.group(1)))
                await page.locator(PROMPT_BOX).first.wait_for(timeout=30_000)
                await self.wait_for_media()

    async def credits(self) -> str | None:
        page = self.page
        await page.locator(ACCOUNT_BUTTON).first.click()
        try:
            panel = page.get_by_text(re.compile(r"[\d,.]+\s+Google Flow credits"))
            await panel.first.wait_for(timeout=10_000)
            match = re.search(r"([\d,.]+)\s+Google Flow credits", await panel.first.inner_text())
            return match.group(1) if match else None
        finally:
            await self.close_account_panel()

    async def close_account_panel(self) -> None:
        """The account panel covers the chat; Escape does not reach a background window."""
        close = self.page.locator(ACCOUNT_CLOSE)
        if await close.count() and await close.first.is_visible():
            await close.first.click()
            await self.page.wait_for_timeout(500)


SIGN_IN = (
    "Flow is not signed in. Ask the user to run `gemini-pro-mcp flow-login` and sign in "
    "to Google in the window that opens (they must do it themselves)."
)


def failure(e: Exception) -> str:
    if isinstance(e, FlowError):
        return f"Error: {e}"
    return (
        f"Error ({type(e).__name__}): {str(e).splitlines()[0] if str(e) else ''} "
        "Flow's page may have changed; please report it at "
        "https://github.com/Muzaqil555/gemini-pro-mcp/issues"
    )


def register(mcp: MCPServer, settings: Settings) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def flow_status() -> str:
        """EXPERIMENTAL: check that Google Flow is signed in, and show credits left. Free.

        Returns:
            The open project and the Flow credit balance, or what the user must do first.
        """
        try:
            async with Flow(settings) as flow:
                project = await flow.open_project()
                credits = await flow.credits()
                return f"Flow is ready. Project: {project}. Credits left: {credits or 'unknown'}."
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=PAID)
    async def flow_generate(
        request: str,
        new_session: bool = True,
        project_id: str | None = None,
        wait_seconds: int = 90,
    ) -> str:
        """EXPERIMENTAL: ask Google Flow's agent to make videos or images.

        Does NOT spend credits by itself: Flow answers with a permission question
        such as "...1 video generation, costing 12 credits?". Show that question to
        the user, and only if they agree call flow_approve (or flow_reject).

        Args:
            request: What to make, in plain words, e.g. "an 8 second 9:16 video of a
                red tram in Baku at sunset, use Veo 3.1 Fast". Mention aspect ratio,
                number of results or model if they matter.
            new_session: Start a fresh agent chat (default). False continues the
                current chat, e.g. to answer a question the agent asked.
            project_id: Flow project to use; default is the configured, current or
                most recent project.
            wait_seconds: How long to wait for the agent's answer.

        Returns:
            The agent's reply, including any permission question and its credit cost.
        """
        try:
            async with Flow(settings) as flow:
                await flow.open_project(project_id)
                page = flow.page
                if new_session:
                    await page.locator(NEW_SESSION).first.click()
                    await page.wait_for_timeout(1000)
                box = page.locator(PROMPT_BOX).first
                await box.click()
                await page.keyboard.type(request, delay=5)
                await page.locator(SUBMIT).first.click()
                await flow.wait_for_agent(wait_seconds)
                reply = await flow.last_reply()
                if await flow.pending_permission() is not None:
                    return (
                        f"Flow asks:\n{reply}\n\nNothing has been spent yet. Ask the user; "
                        "if they agree call flow_approve, otherwise flow_reject."
                    )
                if await flow.busy():
                    return f"Flow is still working. Latest reply so far:\n{reply}"
                return f"Flow replied:\n{reply}"
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=PAID)
    async def flow_approve(wait_seconds: int = 420, file_name: str | None = None) -> str:
        """EXPERIMENTAL: approve Flow's pending request; SPENDS FLOW CREDITS.

        Only call after the user agreed to the cost shown by flow_generate. Waits
        for the results and saves new videos/images to the output folder.

        Args:
            wait_seconds: How long to wait for the media (videos take minutes).
            file_name: Optional base name for the saved files.

        Returns:
            The saved file paths, or the agent's latest reply if nothing came yet.
        """
        try:
            async with Flow(settings) as flow:
                await flow.open_project()
                permission = await flow.pending_permission()
                if permission is None:
                    return "Nothing to approve: Flow has no pending question."
                # The grid lists newest first, so new results are its first tiles.
                before = len(await flow.wait_for_media(timeout=5))
                await permission.locator('[role="radio"]').first.click()  # "Approve"
                stem = Path(file_name).stem if file_name else time.strftime("flow-%Y%m%d-%H%M%S")
                deadline = time.monotonic() + wait_seconds
                saved: dict[int, Path] = {}
                await flow.page.wait_for_timeout(5000)
                while time.monotonic() < deadline:
                    count = max(0, len(await flow.media()) - before)
                    for index in range(count):
                        if index not in saved:
                            item = (await flow.media())[index]
                            path = await flow.download(item, settings.output_dir, stem)
                            if path:
                                saved[index] = path
                    if count and len(saved) == count and not await flow.busy():
                        break
                    await flow.page.wait_for_timeout(10_000)
                reply = await flow.last_reply()
                if not saved:
                    return (
                        "Approved (credits are being spent). The media is not ready yet. "
                        f"Latest reply:\n{reply}\n"
                        "Call flow_collect in a few minutes to download it."
                    )
                listed = "\n".join(f"Saved: {p}" for p in saved.values())
                return f"{listed}\n\nFlow said:\n{reply}"
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True))
    async def flow_reject() -> str:
        """EXPERIMENTAL: decline Flow's pending request. Free.

        Returns:
            Confirmation, or a note that nothing was pending.
        """
        try:
            async with Flow(settings) as flow:
                await flow.open_project()
                permission = await flow.pending_permission()
                if permission is None:
                    return "Nothing to reject: Flow has no pending question."
                await permission.locator('[role="radio"]').last.click()  # "Reject"
                return "Rejected; no credits were spent."
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True))
    async def flow_collect(count: int = 1, file_name: str | None = None) -> str:
        """EXPERIMENTAL: download the newest videos/images of the Flow project. Free.

        Saves the original size (720p for video); upscaled versions cost credits
        in Flow and are not fetched.

        Args:
            count: How many of the newest media items to save.
            file_name: Optional base name for the saved files.

        Returns:
            The saved file paths.
        """
        try:
            async with Flow(settings) as flow:
                await flow.open_project()
                total = len(await flow.wait_for_media())
                if not total:
                    return "No videos or images in this Flow project yet."
                stem = Path(file_name).stem if file_name else time.strftime("flow-%Y%m%d-%H%M%S")
                lines = []
                for index in range(min(count, total)):
                    item = (await flow.media())[index]
                    path = await flow.download(item, settings.output_dir, stem)
                    lines.append(
                        f"Saved: {path}"
                        if path
                        else f"{item['kind']} '{item['label']}': not ready yet"
                    )
                return "\n".join(lines)
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)
