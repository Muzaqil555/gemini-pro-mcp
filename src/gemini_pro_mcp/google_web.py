"""Google AI Pro web apps (Gemini app, Gemini Notebook, AI Studio, Jules, AI
Mode, Flow, Flow Music...) in the user's own signed-in Chrome profile.

`google_page` / `google_act` read and operate any of these sites like a person.
`gemini_app` and `google_ai_mode` are shortcuts for the most used features.
Each site gets its own tab, so a long Flow job and a Gemini chat can run at once.
"""

from __future__ import annotations

import base64
import mimetypes
import re
import time
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus, urlparse

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from . import benefits
from .config import Settings
from .flow import page as page_lib
from .flow.browser import FlowError, connect, lock_for

PAID = ToolAnnotations(
    readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True
)

# Sites the tools may open and operate. Sign-in, payment and account pages are
# deliberately absent; Gmail is left to its official connector (sending mail).
OPERATE = {
    "flow.google.com",
    "gemini.google.com",
    "notebooklm.google.com",
    "aistudio.google.com",
    "jules.google.com",
    "colab.research.google.com",
    "www.google.com",
    "labs.google",
    "www.flowmusic.app",
    "flowmusic.app",
    "playground.google",
    "earth.google.com",
    "docs.google.com",
    "drive.google.com",
    "antigravity.google",
}
READ_ONLY_SITES = {"one.google.com", "support.google.com", "developers.google.com"}

FETCH_JS = r"""async (src) => {
  const response = await fetch(src);
  if (!response.ok) throw new Error('HTTP ' + response.status);
  const blob = await response.blob();
  const buffer = new Uint8Array(await blob.arrayBuffer());
  let binary = '';
  for (let i = 0; i < buffer.length; i += 0x8000)
    binary += String.fromCharCode.apply(null, buffer.subarray(i, i + 0x8000));
  return {type: blob.type, data: btoa(binary)};
}"""

_last_host = {"value": "gemini.google.com"}


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower()


def check_url(url: str, *, operate: bool) -> str:
    if not url.startswith("https://"):
        raise FlowError("Give a full https:// URL.")
    host = host_of(url)
    if host in OPERATE or (not operate and host in READ_ONLY_SITES):
        return host
    allowed = ", ".join(sorted(OPERATE | (set() if operate else READ_ONLY_SITES)))
    raise FlowError(f"{host} is not one of the supported Google AI sites: {allowed}")


def with_english(url: str) -> str:
    if "hl=" in url or "flowmusic.app" in url:
        return url
    return url + ("&" if "?" in url else "?") + "hl=en"


class Tab:
    """The Chrome tab for one site, for the length of a tool call."""

    def __init__(self, settings: Settings, host: str):
        self.settings, self.host = settings, host

    async def __aenter__(self):
        self.lock = lock_for(self.host)
        await self.lock.acquire()
        try:
            self.playwright, self.browser = await connect(self.settings)
            context = self.browser.contexts[0]
            self.page = next((p for p in context.pages if host_of(p.url) == self.host), None)
            if self.page is None:
                self.page = await context.new_page()
        except BaseException:
            self.lock.release()
            raise
        return self

    async def __aexit__(self, *exc):
        try:
            await self.browser.close()  # disconnects; the user's Chrome keeps running
            await self.playwright.stop()
        finally:
            self.lock.release()

    async def goto(self, url: str, settle_ms: int = 4000) -> None:
        await self.page.goto(with_english(url), wait_until="domcontentloaded")
        await self.page.wait_for_timeout(settle_ms)
        if "accounts.google.com" in self.page.url:
            raise FlowError(
                "Not signed in. Ask the user to run `gemini-pro-mcp flow-login` and sign "
                "in to Google in that window (they must do it themselves)."
            )

    async def save_media(self, src: str, folder: Path, stem: str) -> Path:
        result = await self.page.evaluate(FETCH_JS, src)
        ext = mimetypes.guess_extension(result.get("type") or "") or ".bin"
        ext = {".jpe": ".jpg"}.get(ext, ext)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{stem}{ext}"
        n = 2
        while path.exists():
            path = folder / f"{stem}-{n}{ext}"
            n += 1
        path.write_bytes(base64.b64decode(result["data"]))
        return path


def failure(e: Exception) -> str:
    if isinstance(e, FlowError | ValueError):
        return f"Error: {e}"
    first = str(e).splitlines()[0] if str(e) else ""
    return (
        f"Error ({type(e).__name__}): {first} The page may have changed; please report it at "
        "https://github.com/Muzaqil555/gemini-pro-mcp/issues"
    )


# --- Gemini app -----------------------------------------------------------

GEMINI = "https://gemini.google.com/app"
MODELS = {
    "flash-lite": "3.5 Flash-Lite",
    "flash": "3.8 Flash",
    "pro": "3.1 Pro",
    "argon": "4 Argon",
}
DIRECT_TOOLS = {"image": "Create image", "video": "Create video"}
MORE_TOOLS = {
    "music": "Create music",
    "canvas": "Canvas",
    "deep_research": "Deep research",
    "guided_learning": "Guided learning",
}
GeminiTool = Literal[
    "chat", "image", "video", "music", "canvas", "deep_research", "guided_learning"
]

RESPONSE_JS = r"""() => {
  const all = [...document.querySelectorAll('model-response')];
  const last = all[all.length - 1];
  if (!last) return {count: 0, text: '', media: []};
  const media = [];
  for (const el of last.querySelectorAll('img, video, audio, source')) {
    const src = el.currentSrc || el.src || '';
    if (!src.startsWith('http') && !src.startsWith('blob:')) continue;
    const r = el.getBoundingClientRect();
    if (el.tagName === 'IMG' && (r.width < 120 || r.height < 120)) continue;  // icons
    media.push({kind: el.tagName.toLowerCase(), src});
  }
  return {count: all.length, text: last.innerText, media};
}"""


async def click_menu_item(page, name: str) -> None:
    item = page.get_by_role("menuitemcheckbox", name=name).or_(
        page.get_by_role("menuitem", name=name)
    )
    try:
        await item.first.click(timeout=5000)
    except Exception:
        await item.first.dispatch_event("click")
    await page.wait_for_timeout(800)


async def wait_for_answer(page, before: int, timeout: float) -> dict:
    """Waits until Gemini has finished writing a new answer."""
    deadline = time.monotonic() + timeout
    quiet = 0
    state = await page.evaluate(RESPONSE_JS)
    while time.monotonic() < deadline:
        await page.wait_for_timeout(1500)
        state = await page.evaluate(RESPONSE_JS)
        writing = await page.locator('button[aria-label="Stop response"]').count()
        quiet = quiet + 1 if (state["count"] > before and not writing) else 0
        if quiet >= 2:
            break
    state["done"] = quiet >= 2
    return state


def register(mcp: MCPServer, settings: Settings) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def google_pro_benefits() -> str:
        """Everything a Google AI Pro plan includes, and which tool of this server
        reaches each part (or why it cannot). Free; start here when unsure.

        Returns:
            One entry per benefit: what it is, where it lives, how to use it here.
        """
        return benefits.as_text()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def google_page(url: str | None = None, site: str | None = None) -> str:
        """Show a Google AI site as text with numbered elements, in the user's
        signed-in Chrome: Gemini app and Notebooks, AI Studio, Jules, Colab, AI Mode,
        Flow, Flow Music, Docs/Drive... Free. Use with google_act.

        Args:
            url: A page to open first, e.g. "https://gemini.google.com/app" or
                "https://jules.google.com". Without it the site's tab is shown as is.
            site: Which open tab to show (a host like "gemini.google.com"); default
                is the one used last.

        Returns:
            Page text and elements like "[12] button 'Send message'" (frames f1:...).
        """
        try:
            host = check_url(url, operate=False) if url else (site or _last_host["value"])
            async with Tab(settings, host) as tab:
                if url:
                    await tab.goto(url)
                elif tab.page.url in ("", "about:blank"):
                    await tab.goto(f"https://{host}/")
                _last_host["value"] = host
                return f"Tab: {host}\n" + await page_lib.snapshot(tab.page)
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=PAID)
    async def google_act(
        ref: str,
        action: page_lib.Action = "click",
        text: str | None = None,
        files: list[str] | None = None,
        wait_seconds: int = 3,
        site: str | None = None,
    ) -> str:
        """Act on an element from the last google_page snapshot, like a person:
        click, type, upload files, choose options, export. Some buttons spend plan
        credits or limits (Generate, Upscale...). Never types into sign-in, password
        or payment pages.

        Args:
            ref: Element number from the snapshot, e.g. "12" or "f1:3".
            action: click, type, replace, press (a key), upload (local `files`),
                select (option label in `text`), hover or scroll.
            text: Text to type, key to press or option to select.
            files: Local paths for action="upload".
            wait_seconds: How long to wait afterwards (e.g. 120 for an export).
            site: Tab host if not the one of the last google_page call.

        Returns:
            Saved downloads, if any, and the page afterwards with fresh numbers.
        """
        try:
            host = site or _last_host["value"]
            if host not in OPERATE:
                raise FlowError(f"{host} can be read but not operated.")
            async with Tab(settings, host) as tab:
                check_url(tab.page.url, operate=True)
                saved = await page_lib.act(
                    tab.page, ref, action, text, files, settings.output_dir, wait_seconds
                )
                header = "".join(f"Downloaded: {p}\n" for p in saved)
                return header + f"Tab: {host}\n" + await page_lib.snapshot(tab.page)
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=PAID)
    async def gemini_app(
        prompt: str,
        tool: GeminiTool = "chat",
        model: Literal["flash-lite", "flash", "pro", "argon"] | None = None,
        thinking: Literal["low", "medium", "high"] | None = None,
        files: list[str] | None = None,
        temporary: bool = False,
        wait_seconds: int = 300,
    ) -> str:
        """Use the Gemini app (gemini.google.com) on the user's Google AI Pro plan:
        chat with 4 Argon / 3.1 Pro, Deep Research, create images (Nano Banana),
        videos (Veo), music, Canvas, Guided learning. Uses the plan's daily limits,
        no API cost. Generated images/videos/music are saved locally.

        Args:
            prompt: The request.
            tool: "chat" (default), "image", "video", "music", "canvas",
                "deep_research" (starts a long report; fetch it later with
                gemini_app_result) or "guided_learning".
            model: "argon" (4 Argon, complex tasks), "pro" (3.1 Pro), "flash"
                (3.8 Flash) or "flash-lite"; default is the app's current choice.
            thinking: "low", "medium" or "high" thinking level.
            files: Local files to attach (images, PDFs, documents...).
            temporary: Use a temporary chat that is not kept in the history.
            wait_seconds: How long to wait for the answer.

        Returns:
            Gemini's answer, saved media paths and the chat URL.
        """
        try:
            async with Tab(settings, "gemini.google.com") as tab:
                page = tab.page
                await tab.goto(GEMINI, settle_ms=5000)
                skip = page.get_by_role("button", name="Use without content apps")
                if await skip.count():  # the privacy-preserving answer to the app card
                    await skip.first.click()
                if temporary:
                    await page.locator('button[aria-label="Temporary chat"]').first.click()
                    await page.wait_for_timeout(1500)
                if model:
                    await page.locator('button[aria-label^="Open mode picker"]').first.click()
                    await page.wait_for_timeout(800)
                    await page.get_by_text(MODELS[model], exact=True).first.click()
                    await page.wait_for_timeout(800)
                if thinking:
                    await page.locator('button[aria-label^="Open mode picker"]').first.click()
                    await page.wait_for_timeout(800)
                    await click_menu_item(page, "Thinking level")
                    await page.get_by_text(thinking.capitalize(), exact=True).first.click()
                    await page.wait_for_timeout(800)
                if files:
                    paths = [str(Path(f).expanduser().resolve()) for f in files]
                    await page.locator('button[aria-label="Upload & tools"]').first.click()
                    await page.wait_for_timeout(800)
                    await page.locator('input[type="file"]').first.set_input_files(paths)
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(3000 + 1000 * len(paths))
                if tool != "chat":
                    await page.locator('button[aria-label="Upload & tools"]').first.click()
                    await page.wait_for_timeout(800)
                    if tool in MORE_TOOLS:
                        more = page.locator('button[aria-label="More tools"]').first
                        await more.dispatch_event("click")
                        await page.wait_for_timeout(1000)
                        await click_menu_item(page, MORE_TOOLS[tool])
                    else:
                        await click_menu_item(page, DIRECT_TOOLS[tool])
                before = (await page.evaluate(RESPONSE_JS))["count"]
                box = page.get_by_role("textbox", name="Enter a prompt for Gemini")
                await box.click()
                await page.keyboard.type(prompt, delay=3)
                await page.keyboard.press("Enter")
                state = await wait_for_answer(page, before, wait_seconds)
                if tool == "deep_research":
                    start = page.get_by_role("button", name=re.compile("Start research", re.I))
                    if await start.count():
                        await start.first.click()
                        await page.wait_for_timeout(3000)
                        return (
                            "Deep Research started (it takes several minutes). Plan:\n"
                            f"{state['text'][:3000]}\n\nChat: {page.url}\n"
                            "Fetch the report later with gemini_app_result(chat_url)."
                        )
                saved = []
                stem = time.strftime("gemini-%Y%m%d-%H%M%S")
                for item in state["media"]:
                    try:
                        saved.append(await tab.save_media(item["src"], settings.output_dir, stem))
                    except Exception:
                        pass
                lines = [state["text"].strip()[:8000] or "(no text answer)"]
                lines += [f"Saved: {p}" for p in saved]
                if not state["done"]:
                    lines.append("(Gemini was still working; call gemini_app_result later.)")
                lines.append(f"Chat: {page.url}")
                return "\n".join(lines)
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True))
    async def gemini_app_result(chat_url: str, wait_seconds: int = 120) -> str:
        """Read the latest answer of a Gemini app chat (e.g. a Deep Research report)
        and save its images/videos. Free.

        Args:
            chat_url: The "Chat:" URL returned by gemini_app.
            wait_seconds: How long to wait if Gemini is still writing.

        Returns:
            The answer text, saved media and whether it is finished.
        """
        try:
            check_url(chat_url, operate=True)
            async with Tab(settings, "gemini.google.com") as tab:
                await tab.goto(chat_url, settle_ms=6000)
                state = await wait_for_answer(tab.page, 0, wait_seconds)
                saved = []
                stem = time.strftime("gemini-%Y%m%d-%H%M%S")
                for item in state["media"]:
                    try:
                        saved.append(await tab.save_media(item["src"], settings.output_dir, stem))
                    except Exception:
                        pass
                status = "finished" if state["done"] else "still working"
                body = state["text"].strip()[:12000]
                return "\n".join([f"Status: {status}", body, *[f"Saved: {p}" for p in saved]])
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def google_ai_mode(question: str, wait_seconds: int = 60) -> str:
        """Ask Google Search's AI Mode (Gemini 4 Argon with live search, on the
        user's Pro plan) and return its answer with source links. Free.

        Args:
            question: What to search for.
            wait_seconds: How long to let the answer finish.

        Returns:
            The AI Mode answer and its links.
        """
        try:
            async with Tab(settings, "www.google.com") as tab:
                url = f"https://www.google.com/search?q={quote_plus(question)}&udm=50"
                await tab.goto(url, settle_ms=3000)
                deadline = time.monotonic() + wait_seconds
                last, stable = "", 0
                while time.monotonic() < deadline and stable < 3:
                    await tab.page.wait_for_timeout(1500)
                    text = await tab.page.evaluate(
                        "() => (document.querySelector('main') || document.body).innerText"
                    )
                    stable = stable + 1 if text == last else 0
                    last = text
                links = await tab.page.evaluate(
                    r"""() => [...new Set([...document.querySelectorAll('main a[href^="http"]')]
                      .map(a => a.href).filter(h => !h.includes('google.com')))].slice(0, 15)"""
                )
                return last.strip()[:8000] + ("\n\nSources:\n" + "\n".join(links) if links else "")
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)
