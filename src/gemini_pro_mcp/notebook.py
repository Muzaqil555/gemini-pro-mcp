"""Gemini Notebook (formerly NotebookLM) on the user's Google AI Pro plan.

Driven in the signed-in Chrome profile like the other Google web apps: list and
create notebooks, add sources (files, websites, YouTube, text), ask questions
grounded in the sources, and make Studio outputs (Audio/Video Overviews, slide
decks, mind maps, reports, flashcards, quizzes, infographics, data tables).
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from .config import Settings
from .google_web import Tab, failure

HOST = "notebook.google.com"
HOME = "https://notebook.google.com/"
NOTEBOOK = "https://notebook.google.com/notebook/{id}"

STUDIO = {
    "audio_overview": "Audio Overview",
    "video_overview": "Video Overview",
    "slide_deck": "Slide Deck",
    "mind_map": "Mind Map",
    "report": "Reports",
    "flashcards": "Flashcards",
    "quiz": "Quiz",
    "infographic": "Infographic",
    "data_table": "Data Table",
}
StudioOutput = Literal[
    "audio_overview",
    "video_overview",
    "slide_deck",
    "mind_map",
    "report",
    "flashcards",
    "quiz",
    "infographic",
    "data_table",
]

LIST_JS = r"""() => [...document.querySelectorAll('a[href^="/notebook/"]')].map(a => {
  const card = a.closest('[class*="project"]') || a.parentElement;
  const title = (card.querySelector('[class*="title"]') || a).innerText.trim();
  const text = card.innerText.replace(/\s+/g, ' ');
  const meta = (text.match(/[A-Z][a-z]{2} \d{1,2}, \d{4}\s*·\s*\d+ sources?/) || [''])[0];
  return {id: a.getAttribute('href').split('/').pop(), title, meta};
})"""

ANSWER_JS = r"""() => {
  const selector = 'chat-message, .chat-message, [class*="message-content"]';
  const all = [...document.querySelectorAll(selector)];
  const texts = all.map(e => e.innerText.trim()).filter(Boolean);
  return {count: texts.length, last: texts[texts.length - 1] || ''};
}"""

STUDIO_JS = r"""() => {
  const panel = [...document.querySelectorAll('section, div')].find(e =>
    e.querySelector('button[aria-label="Audio Overview"]')
    && e.querySelectorAll('button').length < 200 && e.innerText.length < 20000);
  return panel ? panel.innerText.replace(/\n{2,}/g, '\n') : '';
}"""


def notebook_id(value: str) -> str:
    match = re.search(r"([0-9a-f]{8}-[0-9a-f-]{27})", value)
    if not match:
        raise ValueError(f"Not a notebook id or URL: {value!r} (see notebook_list).")
    return match.group(1)


async def click_text(page, text: str, timeout: int = 10_000) -> None:
    target = page.get_by_role("button", name=re.compile(re.escape(text), re.I)).or_(
        page.get_by_text(text, exact=True)
    )
    await target.first.click(timeout=timeout)
    await page.wait_for_timeout(1200)


async def add_sources(page, files: list[str], urls: list[str], text: str | None) -> list[str]:
    """Uses the "Add sources" dialog. Returns notes on what was added."""
    added = []
    dialog_open = await page.get_by_text("Copied text", exact=False).count()
    if not dialog_open:
        await page.locator('button[aria-label="Add source"]').first.click()
        await page.wait_for_timeout(1500)
    if files:
        paths = [str(Path(f).expanduser().resolve()) for f in files]
        missing = [p for p in paths if not Path(p).is_file()]
        if missing:
            raise ValueError(f"Files not found: {missing}")
        async with page.expect_file_chooser(timeout=15_000) as chooser:
            await click_text(page, "Upload files")
        await (await chooser.value).set_files(paths)
        await page.wait_for_timeout(4000 + 1500 * len(paths))
        added.append(f"{len(paths)} file(s)")
        if urls or text:
            await page.locator('button[aria-label="Add source"]').first.click()
            await page.wait_for_timeout(1500)
    if urls:
        await click_text(page, "Websites")
        box = page.locator("textarea, input[type='url'], input[type='text']").last
        await box.fill("\n".join(urls))
        await click_text(page, "Insert")
        await page.wait_for_timeout(5000)
        added.append(f"{len(urls)} link(s)")
        if text:
            await page.locator('button[aria-label="Add source"]').first.click()
            await page.wait_for_timeout(1500)
    if text:
        await click_text(page, "Copied text")
        await page.locator("textarea").last.fill(text)
        await click_text(page, "Insert")
        await page.wait_for_timeout(3000)
        added.append("pasted text")
    return added


def register(mcp: MCPServer, settings: Settings) -> None:
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def notebook_list() -> str:
        """List the user's Gemini Notebooks (formerly NotebookLM). Free.

        Returns:
            One line per notebook: id, title, date and number of sources.
        """
        try:
            async with Tab(settings, HOST) as tab:
                await tab.goto(HOME, settle_ms=5000)
                mine = tab.page.get_by_role("button", name="My notebooks")
                if await mine.count():
                    await mine.first.click()
                    await tab.page.wait_for_timeout(2500)
                items = await tab.page.evaluate(LIST_JS)
                seen, lines = set(), []
                for item in items:
                    if item["id"] in seen:
                        continue
                    seen.add(item["id"])
                    lines.append(f"{item['id']}  {item['title']}  ({item['meta']})")
                return "\n".join(lines) or "No notebooks yet."
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=write)
    async def notebook_create(
        files: list[str] | None = None,
        urls: list[str] | None = None,
        text: str | None = None,
        title: str | None = None,
    ) -> str:
        """Create a Gemini Notebook with sources. Up to 300 sources per notebook on Pro.

        Args:
            files: Local files (PDF, Word, slides, images, audio...).
            urls: Web pages or YouTube links.
            text: Text to paste as a source.
            title: Notebook title (default: Notebook names it from the sources).

        Returns:
            The new notebook's id and URL.
        """
        try:
            async with Tab(settings, HOST) as tab:
                page = tab.page
                await tab.goto(HOME, settle_ms=5000)
                await page.locator(
                    'button[aria-label="New notebook"], button:has-text("Create notebook")'
                ).first.click()
                await page.wait_for_timeout(5000)
                added = await add_sources(page, files or [], urls or [], text)
                new_id = notebook_id(page.url)
                if title:
                    name = page.locator("input[type='text']").first
                    await name.fill(title)
                    await name.press("Enter")
                return (
                    f"Created notebook {new_id} with {', '.join(added) or 'no sources'}.\n"
                    f"URL: {NOTEBOOK.format(id=new_id)}"
                )
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=write)
    async def notebook_add_sources(
        notebook: str,
        files: list[str] | None = None,
        urls: list[str] | None = None,
        text: str | None = None,
    ) -> str:
        """Add sources to a Gemini Notebook.

        Args:
            notebook: Notebook id or URL (from notebook_list).
            files: Local files to upload.
            urls: Web pages or YouTube links.
            text: Text to paste as a source.

        Returns:
            What was added.
        """
        try:
            async with Tab(settings, HOST) as tab:
                await tab.goto(NOTEBOOK.format(id=notebook_id(notebook)), settle_ms=6000)
                added = await add_sources(tab.page, files or [], urls or [], text)
                return f"Added {', '.join(added) or 'nothing'}."
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True))
    async def notebook_ask(notebook: str, question: str, wait_seconds: int = 120) -> str:
        """Ask a question answered only from a notebook's sources, with citations.

        Args:
            notebook: Notebook id or URL (from notebook_list).
            question: The question.
            wait_seconds: How long to wait for the answer.

        Returns:
            Notebook's answer.
        """
        try:
            async with Tab(settings, HOST) as tab:
                page = tab.page
                await tab.goto(NOTEBOOK.format(id=notebook_id(notebook)), settle_ms=6000)
                before = await page.evaluate(ANSWER_JS)
                box = page.locator('textarea[aria-label="Query box"]').first
                await box.fill(question)
                await box.press("Enter")
                deadline = time.monotonic() + wait_seconds
                last, stable = "", 0
                while time.monotonic() < deadline and stable < 3:
                    await page.wait_for_timeout(2000)
                    state = await page.evaluate(ANSWER_JS)
                    if state["count"] <= before["count"] or state["last"] == question:
                        continue
                    stable = stable + 1 if state["last"] == last else 0
                    last = state["last"]
                return last or "No answer yet; ask again in a moment."
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=write)
    async def notebook_studio(
        notebook: str,
        output: StudioOutput,
        wait_seconds: int = 900,
    ) -> str:
        """Make a Studio output from a notebook's sources: Audio Overview (podcast),
        Video Overview, Slide Deck, Mind Map, Report, Flashcards, Quiz, Infographic
        or Data Table. Uses the plan's Notebook limits. Audio and video files are
        downloaded when ready.

        Args:
            notebook: Notebook id or URL (from notebook_list).
            output: Which Studio output to make.
            wait_seconds: How long to wait (audio/video overviews take minutes).

        Returns:
            The Studio panel afterwards and any downloaded files.
        """
        try:
            async with Tab(settings, HOST) as tab:
                page = tab.page
                await tab.goto(NOTEBOOK.format(id=notebook_id(notebook)), settle_ms=6000)
                before = await page.evaluate(STUDIO_JS)
                await page.locator(f'button[aria-label="{STUDIO[output]}"]').first.click()
                await page.wait_for_timeout(5000)
                deadline = time.monotonic() + wait_seconds
                panel = await page.evaluate(STUDIO_JS)
                while time.monotonic() < deadline and re.search(r"Generating", panel):
                    await page.wait_for_timeout(10_000)
                    panel = await page.evaluate(STUDIO_JS)
                saved = []
                if output in ("audio_overview", "video_overview") and "Generating" not in panel:
                    try:
                        more = page.locator('button[aria-label="More"]').first
                        await more.click()
                        await page.wait_for_timeout(1000)
                        async with page.expect_download(timeout=120_000) as info:
                            await page.get_by_role(
                                "menuitem", name=re.compile("Download", re.I)
                            ).first.click()
                        download = await info.value
                        folder = settings.output_dir
                        folder.mkdir(parents=True, exist_ok=True)
                        path = folder / download.suggested_filename
                        await download.save_as(path)
                        saved.append(path)
                    except Exception:
                        pass
                status = "still generating" if "Generating" in panel else "ready"
                changed = "" if panel != before else " (panel unchanged; check the notebook)"
                lines = [f"{STUDIO[output]}: {status}{changed}", *[f"Saved: {p}" for p in saved]]
                lines.append(f"Notebook: {NOTEBOOK.format(id=notebook_id(notebook))}")
                lines.append("Studio panel:\n" + panel[:3000])
                return "\n".join(lines)
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)
