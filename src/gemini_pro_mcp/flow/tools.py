"""EXPERIMENTAL Google Flow tools (opt-in with GEMINI_PRO_ENABLE_FLOW=1).

Flow has no public API. These tools drive flow.google.com in the user's own
signed-in Chrome profile and spend the Flow credits of their Google AI plan.
They depend on Flow's web page and can break when Google changes it.

Flow is an agent: you send a request, and before spending credits it asks for
permission ("...costing 12 credits?"). By default `flow_generate` stops at that
question and only `flow_approve` answers it, so credits are never spent without
a separate call. With GEMINI_PRO_AUTO_APPROVE=1 the user has pre-approved
spending and the tools answer it themselves.
"""

from __future__ import annotations

import asyncio
import base64
import inspect
import json
import re
import time
import uuid
from pathlib import Path
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from .. import agy
from ..config import Settings, spending_note
from ..stitch import StitchError, stitch, unique_path
from . import page as flow_page_lib
from .browser import FlowError, connect, lock_for

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
# The plan chip ("PRO"/"ULTRA") opens the account panel. Since November 2026
# its button also holds the Google account bar, so clicking the button's centre
# lands on the avatar; click the chip itself.
ACCOUNT_BUTTON = 'flow-user-tier-chip, [aria-label="Account details"]'
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
        self.lock = lock_for("flow.google.com")  # tool calls and jobs take turns
        await self.lock.acquire()
        try:
            self.playwright, self.browser = await connect(self.settings)
            self.page = await self._page()
        except BaseException:
            self.lock.release()
            raise
        return self

    async def __aexit__(self, *exc):
        self.lock.release()  # the shared connection stays open (see browser.connect)

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
        """Closes open menus and panels. A click in the middle of the backdrop
        can land on the panel itself, so press Escape and click its corner."""
        page = self.page
        backdrop = page.locator(".cdk-overlay-backdrop")
        if not await backdrop.count():
            return
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
        for _ in range(3):
            if not await backdrop.count():
                return
            await backdrop.first.click(position={"x": 5, "y": 5})
            await page.wait_for_timeout(300)

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
            signed: list[str] = []

            def on_request(request) -> None:  # Flow fetches the signed file URL first
                if "flow-content.google/" in request.url and "Signature=" in request.url:
                    signed.append(request.url)

            page.on("request", on_request)
            try:
                async with page.expect_download(timeout=120_000) as info:
                    await choice.click()
                download = await info.value
            finally:
                page.remove_listener("request", on_request)
            extension = Path(download.suggested_filename).suffix or (
                ".mp4" if item["kind"] == "video" else ".png"
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / f"{stem}{extension}"
            n = 2
            while path.exists() and path.stat().st_size:
                path = output_dir / f"{stem}-{n}{extension}"
                n += 1
            try:
                await download.save_as(path)
            except Exception:
                pass
            if (not path.exists() or path.stat().st_size == 0) and signed:
                result = await page.evaluate(flow_page_lib.FETCH_JS, signed[-1])
                path.write_bytes(base64.b64decode(result["data"]))
            if not path.exists() or path.stat().st_size == 0:
                path.unlink(missing_ok=True)
                raise FlowError("Flow's download came back empty; try flow_collect again.")
            return path
        finally:
            if project and "/edit/" in page.url:  # back from the editor
                await page.goto(PROJECT.format(id=project.group(1)))
                await page.locator(PROMPT_BOX).first.wait_for(timeout=30_000)
                await self.wait_for_media()

    async def send(self, request: str, *, new_session: bool, wait_seconds: float) -> str:
        """Types a request into the agent chat and waits for its answer."""
        page = self.page
        if new_session:
            await page.locator(NEW_SESSION).first.click()
            await page.wait_for_timeout(1000)
        await page.locator(PROMPT_BOX).first.click()
        await page.keyboard.type(request, delay=5)
        await page.locator(SUBMIT).first.click()
        await self.wait_for_agent(wait_seconds)
        return await self.last_reply()

    async def approve(self, output_dir: Path, stem: str, wait_seconds: float) -> list[Path]:
        """Answers the pending question with Approve, then waits for the new
        results and saves them. The grid lists newest first, so the new results
        are its first tiles."""
        permission = await self.pending_permission()
        if permission is None:
            raise FlowError("Nothing to approve: Flow has no pending question.")
        before = len(await self.wait_for_media(timeout=5))
        bubbles = await self.page.locator(BUBBLE).count()
        await permission.locator('[role="radio"]').first.click()  # "Approve"
        return await self.collect_new(before, output_dir, stem, wait_seconds, bubbles)

    async def collect_new(
        self,
        before: int,
        output_dir: Path,
        stem: str,
        wait_seconds: float,
        bubbles: int | None = None,
    ) -> list[Path]:
        """Waits for the tiles added after the grid had `before` tiles and saves
        them. Flow queues generations at busy times, so they can take long."""
        deadline = time.monotonic() + wait_seconds
        saved: dict[int, Path] = {}
        await self.page.wait_for_timeout(5000)
        while time.monotonic() < deadline:
            if bubbles is not None and await self.generation_failed(bubbles):
                raise GenerationFailed(await self.last_reply())
            count = max(0, len(await self.media()) - before)
            for index in range(count):
                if index not in saved:
                    item = (await self.media())[index]
                    path = await self.download(item, output_dir, stem)
                    if path:
                        saved[index] = path
            if count and len(saved) == count and not await self.busy():
                break
            await self.page.wait_for_timeout(10_000)
        return list(saved.values())

    async def generation_failed(self, bubbles_before: int) -> bool:
        """Whether Flow reported a failed generation after the approval. Its
        error card shows a "warning" icon and "Failed"."""
        bubbles = self.page.locator(BUBBLE)
        for i in range(bubbles_before, await bubbles.count()):
            text = await bubbles.nth(i).inner_text()
            if "warning" in text.split() or "Something went wrong" in text:
                return True
        return False

    async def goto(self, url: str) -> None:
        if not url.startswith(flow_page_lib.ALLOWED):
            raise FlowError("Only flow.google.com pages can be opened.")
        if "hl=" not in url:
            url += ("&" if "?" in url else "?") + "hl=en"
        await self.page.goto(url, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(4000)

    async def tool_cards(self, project: str) -> dict[str, list[dict]]:
        await self.goto(f"https://flow.google.com/project/{project}/tools")
        groups: dict[str, list[dict]] = {}
        for tab in ("My Tools", "Templates", "Community"):
            await self.close_overlays()
            await self.page.locator(f'button:has-text("{tab}")').first.click()
            await self.page.wait_for_timeout(2500)
            groups[tab] = [c for c in await self.page.evaluate(TOOL_CARDS_JS) if c["name"]]
        return groups

    async def credits(self) -> str | None:
        """The credit balance from the account panel, or None if it cannot be read."""
        page = self.page
        try:
            await page.locator(ACCOUNT_BUTTON).first.click(timeout=10_000)
        except Exception:
            return None  # the badge moved again; Flow itself still works
        try:
            panel = page.get_by_text(re.compile(r"[\d,.]+\s+Google Flow credits"))
            await panel.first.wait_for(timeout=10_000)
            match = re.search(r"([\d,.]+)\s+Google Flow credits", await panel.first.inner_text())
            return match.group(1) if match else None
        except Exception:
            return None
        finally:
            await self.close_account_panel()

    async def close_account_panel(self) -> None:
        """The account panel covers the chat; Escape does not reach a background window."""
        close = self.page.locator(ACCOUNT_CLOSE)
        if await close.count() and await close.first.is_visible():
            await close.first.click()
            await self.page.wait_for_timeout(500)


class GenerationFailed(FlowError):
    """Flow accepted the request but the generation failed (nothing charged)."""


TOOL_CARDS_JS = flow_page_lib.TOOL_CARDS_JS

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


def clip_lengths(total_seconds: int) -> list[int]:
    """Flow makes clips of 4 or 8 seconds; cover the total with as few as possible."""
    total = max(4, total_seconds)
    lengths = [8] * (total // 8)
    rest = total % 8
    if rest:
        lengths.append(8 if rest > 4 else 4)
    return lengths


# Observed for Omni 1.1 Flash on 2026-10-21; Flow states the real price each time.
CREDITS_PER_CLIP = {4: 7, 8: 12}

PLAN_PROMPT = """You write shot lists for an AI video generator that makes each shot
separately, so shots only match if every prompt repeats the same descriptions.

Video idea: {idea}
Aspect ratio: {aspect}
Number of shots: {count}
Shot lengths in seconds, in order: {lengths}

Write one prompt per shot so that together they tell the idea from start to end.
Rules for every prompt:
- Self-contained: repeat the full description of each recurring character
  (look, clothes), place, time of day, lighting and visual style, word for word
  in every shot.
- Describe only what happens during that shot, the camera, and the sound.
- No on-screen text unless the idea asks for it.

Answer with only a JSON array of exactly {count} strings, nothing else."""


def parse_shots(text: str, count: int) -> list[str] | None:
    match = re.search(r"\[.*\]", text, re.S)
    if not match:
        return None
    try:
        shots = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(shots, list) or len(shots) != count:
        return None
    shots = [str(s).strip() for s in shots]
    return shots if all(shots) else None


async def plan_shots(settings: Settings, idea: str, lengths: list[int], aspect: str) -> list[str]:
    """A shot list from Gemini (free, via Antigravity); a simple split if that fails."""
    if len(lengths) > 1 and settings.agy_path:
        prompt = PLAN_PROMPT.format(
            idea=idea, aspect=aspect, count=len(lengths), lengths=", ".join(map(str, lengths))
        )
        try:
            result = await agy.ask(settings, prompt)
            shots = parse_shots(result.response, len(lengths))
            if shots:
                return shots
        except agy.AgyError:
            pass
    if len(lengths) == 1:
        return [idea]
    return [f"{idea} (part {i + 1} of {len(lengths)}, continuing)" for i in range(len(lengths))]


def clip_request(shot: str, seconds: int, aspect: str) -> str:
    return (
        f"Generate exactly one {seconds} second {aspect} video and nothing else, "
        f"without asking me questions: {shot}"
    )


JOBS: dict[str, dict] = {}
_TASKS: set[asyncio.Task] = set()


def job_text(job: dict) -> str:
    lines = [f"Job {job['id']}: {job['status']}"]
    if job.get("done_clips") is not None:
        lines.append(f"Clips: {job['done_clips']}/{len(job['lengths'])}")
    if job.get("credits_before") and job.get("credits_after"):
        lines.append(f"Flow credits: {job['credits_before']} -> {job['credits_after']}")
    if job.get("output"):
        lines.append(f"Video: {job['output']}")
    if job.get("clips"):
        lines.append("Clip files: " + ", ".join(str(c) for c in job["clips"]))
    if job.get("error"):
        lines.append(f"Error: {job['error']}")
    return "\n".join(lines)


def load_plan(folder: Path, prompt: str, lengths: list[int]) -> list[str] | None:
    """The shot list of an earlier run of the same job, to resume it."""
    plan = folder / "plan.json"
    if not plan.is_file():
        return None
    try:
        data = json.loads(plan.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("prompt") == prompt and data.get("lengths") == lengths:
        return data.get("shots")
    return None


def save_plan(folder: Path, prompt: str, lengths: list[int], shots: list[str]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    data = {"prompt": prompt, "lengths": lengths, "shots": shots}
    (folder / "plan.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


async def run_job(settings: Settings, job: dict) -> None:
    lengths, aspect = job["lengths"], job["aspect"]
    folder = settings.output_dir / job["stem"]
    try:
        shots = load_plan(folder, job["prompt"], lengths)
        if shots:
            job["status"] = "resuming earlier plan"
        else:
            job["status"] = "planning shots"
            shots = await plan_shots(settings, job["prompt"], lengths, aspect)
            save_plan(folder, job["prompt"], lengths, shots)
        job["shots"] = shots
        async with Flow(settings) as flow:
            await flow.open_project(job.get("project_id"))
            job["credits_before"] = await flow.credits()
        clips: list[Path] = []
        job["done_clips"] = 0
        for index, (shot, seconds) in enumerate(zip(shots, lengths, strict=True), start=1):
            stem = f"{job['stem']}-{index:02d}"
            existing = [p for p in sorted(folder.glob(f"{stem}.*")) if p.stat().st_size > 0]
            if existing:  # done in an earlier run
                clips.append(existing[0])
                job["clips"], job["done_clips"] = clips, index
                continue
            job["status"] = f"generating clip {index}/{len(lengths)}"
            saved = await generate_clip(
                settings, job, clip_request(shot, seconds, aspect), folder, stem
            )
            clips.append(saved)
            job["clips"] = clips
            job["done_clips"] = index
        if len(clips) > 1:
            job["status"] = "joining clips"
            output = unique_path(settings.output_dir, job["stem"], ".mp4")
            job["output"] = await stitch(clips, output)
        else:
            job["output"] = clips[0]
        async with Flow(settings) as flow:
            await flow.open_project(job.get("project_id"))
            job["credits_after"] = await flow.credits()
        job["status"] = "done"
    except (FlowError, StitchError) as e:
        job["status"], job["error"] = "failed", str(e)
    except Exception as e:  # browser automation can fail in many ways
        job["status"], job["error"] = "failed", failure(e)


async def generate_clip(
    settings: Settings, job: dict, request: str, folder: Path, stem: str, attempts: int = 3
) -> Path:
    """One clip, retrying when Flow fails (failed generations are not charged).
    A clip that was approved but is still queued is paid for, so later attempts
    wait for it instead of generating (and paying) again."""
    last_error = "no answer"
    queued: int | None = None  # grid size before the approved, still queued clip
    for attempt in range(1, attempts + 1):
        try:
            async with Flow(settings) as flow:
                await flow.open_project(job.get("project_id"))
                if queued is not None:
                    saved = await flow.collect_new(queued, folder, stem, 900)
                    if saved:
                        return saved[0]
                    last_error = "Flow queued the clip and it is not ready yet"
                    job["status"] = f"{job['status'].split(' (')[0]} (waiting for Flow's queue)"
                    continue
                await flow.send(request, new_session=True, wait_seconds=120)
                if await flow.pending_permission() is None:
                    # The agent asked something instead; answer once in the same chat.
                    await flow.send(
                        "Yes, generate it now exactly as described.",
                        new_session=False,
                        wait_seconds=120,
                    )
                if await flow.pending_permission() is None:
                    last_error = (
                        "Flow did not offer to generate: " + (await flow.last_reply())[:200]
                    )
                else:
                    queued = len(await flow.media())
                    saved = await flow.approve(folder, stem, 900)
                    if saved:
                        return saved[0]
                    last_error = "the clip did not come back in 15 minutes"
                    job["status"] = f"{job['status'].split(' (')[0]} (waiting for Flow's queue)"
                    continue
        except GenerationFailed as e:
            queued = None
            last_error = f"Flow failed ({str(e)[:120]})"
        job["status"] = f"{job['status'].split(' (')[0]} (attempt {attempt} failed: {last_error})"
        await asyncio.sleep(30 * attempt)
    if queued is not None:
        last_error += "; it may still arrive, collect it later with flow_collect"
    raise FlowError(f"{stem}: {last_error} after {attempts} attempts.")


def register(mcp: MCPServer, settings: Settings) -> None:
    def paid(fn):
        mcp.add_tool(fn, annotations=PAID, description=spending_note(inspect.getdoc(fn), settings))
        return fn

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

    @paid
    async def flow_make_video(
        prompt: str,
        duration_seconds: int = 8,
        aspect_ratio: Literal["16:9", "9:16"] = "16:9",
        file_name: str | None = None,
        project_id: str | None = None,
    ) -> str:
        """EXPERIMENTAL: make a video of any length with Google Flow, as one .mp4.

        SPENDS FLOW CREDITS (about 12 per 8 seconds). Confirm with the user before calling.
        Splits the idea into 4-8 second shots with Gemini (free), generates each
        shot in Flow, downloads them and joins them. Runs in the background:
        returns a job id at once; check it with flow_job (a 2 minute video takes
        a while, about 15 clips).

        Args:
            prompt: The video idea: story, characters, place, style, sound.
            duration_seconds: Total length wanted, e.g. 120 for two minutes (max 600).
            aspect_ratio: "16:9" (landscape) or "9:16" (vertical).
            file_name: Optional name for the final .mp4.
            project_id: Flow project to use; default is the open or most recent one.

        Returns:
            The job id and the plan (number of clips, estimated credits).
        """
        if not 1 <= duration_seconds <= 600:
            return "Error: duration_seconds must be between 1 and 600."
        lengths = clip_lengths(duration_seconds)
        job_id = uuid.uuid4().hex[:8]
        stem = Path(file_name).stem if file_name else time.strftime("flow-%Y%m%d-%H%M%S")
        job = {
            "id": job_id,
            "status": "queued",
            "prompt": prompt,
            "lengths": lengths,
            "aspect": aspect_ratio,
            "stem": stem,
            "project_id": project_id,
        }
        JOBS[job_id] = job
        task = asyncio.create_task(run_job(settings, job))
        _TASKS.add(task)
        task.add_done_callback(_TASKS.discard)
        estimate = sum(CREDITS_PER_CLIP.get(n, 12) for n in lengths)
        return (
            f"Started job {job_id}: {len(lengths)} clip(s) ({sum(lengths)} s), "
            f"about {estimate} Flow credits. Check progress with flow_job('{job_id}')."
        )

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True))
    async def flow_tools(project_id: str | None = None) -> str:
        """EXPERIMENTAL: list every Flow tool: Google's (Image Editor, Mockup, Shot
        Explorer, Mask Magic, Video Resizer, Transition Machine, Type Overlays,
        Shader Effects, Poster Designer...), the community's and the user's own. Free.

        Returns:
            Tool names with authors and what they do; open one with flow_open_tool.
        """
        try:
            async with Flow(settings) as flow:
                project = await flow.open_project(project_id)
                return flow_page_lib.format_tools(await flow.tool_cards(project))
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True))
    async def flow_open_tool(name: str, project_id: str | None = None) -> str:
        """EXPERIMENTAL: open a Flow tool by name and show its interface.

        Opening a Google or community tool makes the user's own copy ("Remix of
        ...") under My Tools, as Flow does; an existing copy is reused. Then use
        flow_act on the returned elements (tool frames are named f1:, f2:...).
        Some tools spend Flow credits when they generate.

        Args:
            name: Tool name as listed by flow_tools, e.g. "Video Resizer".
            project_id: Flow project; default is the open or most recent one.

        Returns:
            The tool's page as text with numbered elements.
        """
        try:
            async with Flow(settings) as flow:
                project = await flow.open_project(project_id)
                groups = await flow.tool_cards(project)
                wanted = name.strip().lower()
                order = [("My Tools", f"remix of {wanted}"), ("My Tools", wanted)]
                order += [("Templates", wanted), ("Community", wanted)]
                for tab, card_name in order:
                    if any(c["name"].lower() == card_name for c in groups.get(tab, [])):
                        await flow.close_overlays()
                        await flow.page.locator(f'button:has-text("{tab}")').first.click()
                        await flow.page.wait_for_timeout(2000)
                        card = flow.page.locator("flow-applet-card").filter(
                            has=flow.page.get_by_text(card_name, exact=False)
                        )
                        await card.first.locator("span").first.dispatch_event("click")
                        await flow.page.wait_for_timeout(6000)
                        from .. import google_web

                        google_web._last_host["value"] = "flow.google.com"
                        return await flow_page_lib.snapshot(flow.page)
                names = ", ".join(c["name"] for cards in groups.values() for c in cards)
                return f"No Flow tool named {name!r}. Available: {names}"
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def flow_job(job_id: str | None = None) -> str:
        """EXPERIMENTAL: progress of flow_make_video jobs. Free.

        Args:
            job_id: The job to show; default lists all jobs of this session.

        Returns:
            Status, clips done, credits used and the final video path when done.
        """
        if job_id:
            job = JOBS.get(job_id)
            return job_text(job) if job else f"No job {job_id} in this session."
        return "\n\n".join(job_text(j) for j in JOBS.values()) or "No jobs in this session."

    @paid
    async def flow_generate(
        request: str,
        new_session: bool = True,
        project_id: str | None = None,
        wait_seconds: int = 90,
        file_name: str | None = None,
    ) -> str:
        """EXPERIMENTAL: ask Google Flow's agent to make videos or images.

        Flow answers with a permission question such as "...1 video generation,
        costing 12 credits?". Confirm with the user before calling.
        Without pre-approval this tool stops at that question: show it to the
        user and call flow_approve (or flow_reject). With pre-approval it approves,
        waits and saves the results itself.

        Args:
            request: What to make, in plain words, e.g. "an 8 second 9:16 video of a
                red tram in Baku at sunset, use Veo 3.1 Fast". For longer videos use
                flow_make_video.
            new_session: Start a fresh agent chat (default). False continues the
                current chat, e.g. to answer a question the agent asked.
            project_id: Flow project to use; default is the open or most recent one.
            wait_seconds: How long to wait for the agent's answer.
            file_name: Optional base name for saved files (pre-approved mode).

        Returns:
            The agent's reply, or (pre-approved) the saved file paths.
        """
        try:
            async with Flow(settings) as flow:
                await flow.open_project(project_id)
                reply = await flow.send(request, new_session=new_session, wait_seconds=wait_seconds)
                if await flow.pending_permission() is not None:
                    if not settings.auto_approve:
                        return (
                            f"Flow asks:\n{reply}\n\nNothing has been spent yet. Ask the user; "
                            "if they agree call flow_approve, otherwise flow_reject."
                        )
                    stem = (
                        Path(file_name).stem if file_name else time.strftime("flow-%Y%m%d-%H%M%S")
                    )
                    paths = await flow.approve(settings.output_dir, stem, 900)
                    if not paths:
                        return (
                            f"Approved ({reply.splitlines()[-1] if reply else ''}). Not ready "
                            "yet; call flow_collect in a few minutes."
                        )
                    return "\n".join(f"Saved: {p}" for p in paths) + f"\n\nFlow said:\n{reply}"
                if await flow.busy():
                    return f"Flow is still working. Latest reply so far:\n{reply}"
                return f"Flow replied:\n{reply}"
        except Exception as e:  # browser automation can fail in many ways
            return failure(e)

    @paid
    async def flow_approve(wait_seconds: int = 900, file_name: str | None = None) -> str:
        """EXPERIMENTAL: approve Flow's pending request; SPENDS FLOW CREDITS.

        Answers the question shown by flow_generate. Confirm with the user before calling.
        Waits for the results and saves new videos/images to the output folder.

        Args:
            wait_seconds: How long to wait for the media (videos take minutes).
            file_name: Optional base name for the saved files.

        Returns:
            The saved file paths, or a note to call flow_collect later.
        """
        try:
            async with Flow(settings) as flow:
                await flow.open_project()
                stem = Path(file_name).stem if file_name else time.strftime("flow-%Y%m%d-%H%M%S")
                paths = await flow.approve(settings.output_dir, stem, wait_seconds)
                reply = await flow.last_reply()
                if not paths:
                    return (
                        "Approved (credits are being spent). The media is not ready yet. "
                        f"Latest reply:\n{reply}\n"
                        "Call flow_collect in a few minutes to download it."
                    )
                return "\n".join(f"Saved: {p}" for p in paths) + f"\n\nFlow said:\n{reply}"
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
