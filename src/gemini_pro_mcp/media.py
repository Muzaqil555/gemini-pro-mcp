"""Video and image generation through the official Gemini API.

Uses the Interactions API of google-genai: Gemini Omni Flash for video (Veo 3.1
preview models were shut down on 2026-10-22) and the Nano Banana family for
images. Every call is billed to the Google Cloud project behind the API key;
Google AI Pro's monthly Cloud credit can pay for it once billing is enabled.
"""

from __future__ import annotations

import asyncio
import base64
import inspect
import mimetypes
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from google import genai
from google.genai import errors
from mcp.server.mcpserver import Context, MCPServer
from mcp_types import ToolAnnotations

from .config import Settings, env_file, spending_note

try:  # The Interactions API raises its own error classes.
    from google.genai._gaos.lib import compat_errors

    API_ERRORS: tuple[type[Exception], ...] = (errors.APIError, compat_errors.APIError)
except ImportError:  # pragma: no cover - other SDK versions
    API_ERRORS = (errors.APIError,)

VIDEO_MODEL = "gemini-omni-1.1-flash"
POLL_SECONDS = 10
MAX_IMAGE_BYTES = 20 * 1024 * 1024

VideoAspect = Literal["16:9", "9:16"]
VideoResolution = Literal["360p", "720p", "1080p", "4k"]
ImageModel = Literal[
    "gemini-nano-banana-2.1",
    "gemini-3.1-flash-lite-image",
    "gemini-3-pro-image",
]
ImageAspect = Literal["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
ImageSize = Literal["1K", "2K", "4K"]

PAID = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)


class MediaError(RuntimeError):
    pass


class Media:
    """Gemini API client and file handling shared by the media tools."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: genai.Client | None = None
        # Interaction id -> file name to save under, for video_check.
        self.names: dict[str, str] = {}

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
                raise MediaError(
                    "No Gemini API key. Create one at https://aistudio.google.com/apikey, "
                    f"put GEMINI_API_KEY=... in {env_file()} (or in the MCP server's "
                    "env config), and restart the server."
                )
            self._client = genai.Client()
        return self._client

    # -- files -------------------------------------------------------------

    def save_path(self, name: str) -> Path:
        self.settings.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.settings.output_dir / name
        n = 2
        while path.exists():
            path = path.with_name(f"{Path(name).stem}-{n}{Path(name).suffix}")
            n += 1
        return path

    async def download(self, content: Any) -> bytes:
        """Bytes of an output_video/output_image block (inline data or file URI)."""
        if content is None:
            raise MediaError("The model finished without producing the media.")
        if content.data:
            return base64.b64decode(content.data)
        if not content.uri:
            raise MediaError("The result came back without data or a link.")
        match = re.search(r"files/([^/?#]+)", content.uri)
        if match:
            name = f"files/{match.group(1)}"
            for _ in range(60):
                info = await self.client.aio.files.get(name=name)
                state = str(getattr(info.state, "value", info.state) or "").upper()
                if state.endswith("ACTIVE"):
                    break
                if state.endswith("FAILED"):
                    raise MediaError("Google could not prepare the file.")
                await asyncio.sleep(5)
        return await self.client.aio.files.download(file=content.uri)

    async def upload_video(self, path: Path) -> str:
        uploaded = await self.client.aio.files.upload(file=str(path))
        for _ in range(60):
            state = str(getattr(uploaded.state, "value", uploaded.state) or "").upper()
            if not state.endswith("PROCESSING"):
                break
            await asyncio.sleep(3)
            uploaded = await self.client.aio.files.get(name=uploaded.name)
        return uploaded.uri

    # -- interactions ------------------------------------------------------

    async def create(self, request: dict) -> Any:
        """Starts an interaction in the background when the API allows it."""
        try:
            return await self.client.aio.interactions.create(background=True, **request)
        except API_ERRORS as e:
            # Google documents media calls as synchronous; if background mode is
            # refused nothing was generated, so ask again and wait for it.
            if code_of(e) != 400 or "background" not in message_of(e).lower():
                raise
            return await self.client.aio.interactions.create(**request)

    async def wait(self, interaction: Any, wait_seconds: int, ctx: Context | None) -> Any:
        started = time.monotonic()
        while interaction.status in ("queued", "in_progress"):
            waited = time.monotonic() - started
            if waited >= wait_seconds:
                return interaction
            if ctx is not None:
                try:
                    await ctx.report_progress(waited, wait_seconds, "Generating")
                except Exception:  # progress is a nicety; never fail the call over it
                    pass
            await asyncio.sleep(POLL_SECONDS)
            interaction = await self.client.aio.interactions.get(interaction.id)
        return interaction

    async def finish_video(self, interaction: Any, wait_seconds: int, ctx: Context | None) -> str:
        interaction = await self.wait(interaction, wait_seconds, ctx)
        if interaction.status in ("queued", "in_progress"):
            return (
                f"Still generating (status: {interaction.status}). "
                f"Call video_check with id '{interaction.id}' to fetch it later."
            )
        failed = failure_text(interaction)
        if failed:
            return failed
        name = self.names.pop(interaction.id, None) or make_file_name("video", None, "mp4")
        path = self.save_path(name)
        path.write_bytes(await self.download(interaction.output_video))
        return (
            f"Saved: {path} ({path.stat().st_size / 1024 / 1024:.1f} MB)\n"
            f"id: {interaction.id} (pass it to video_edit to change or extend this video)"
        )


# -- helpers -------------------------------------------------------------------


def code_of(e: Exception) -> int | None:
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    return code if isinstance(code, int) else None


def message_of(e: Exception) -> str:
    body = getattr(e, "body", None)
    if isinstance(body, list) and body:
        body = body[0]
    if isinstance(body, dict):
        inner = body.get("error", body)
        if isinstance(inner, dict) and inner.get("message"):
            return str(inner["message"])
    return str(getattr(e, "message", None) or e)


def describe_api_error(e: Exception) -> str:
    code = code_of(e)
    message = message_of(e)
    hint = {
        400: "The request was rejected; check the prompt and inputs.",
        401: "The API key is invalid.",
        403: "No access: enable billing for the key's project in Google AI Studio.",
        404: "Not found: the id may be wrong or expired.",
        429: "Quota or rate limit reached; wait, or check billing limits in AI Studio.",
    }.get(code, "Gemini API error.")
    if "api key" in message.lower():
        hint = f"Check GEMINI_API_KEY ({env_file()} or the server's env) and restart."
    return f"Error {code}: {message} ({hint})"


def failure_text(interaction: Any) -> str | None:
    if interaction.status == "completed":
        return None
    details = "; ".join(str(getattr(e, "message", e)) for e in interaction.errors or [])
    return f"Generation ended with status '{interaction.status}'" + (
        f": {details}" if details else "."
    )


def image_part(path: str) -> dict:
    file = Path(path).expanduser()
    if not file.is_file():
        raise MediaError(f"Image not found: {file}")
    if file.stat().st_size > MAX_IMAGE_BYTES:
        raise MediaError(f"Image is larger than 20 MB: {file}")
    mime = mimetypes.guess_type(file.name)[0] or "image/jpeg"
    if not mime.startswith("image/"):
        raise MediaError(f"Not an image: {file}")
    data = base64.b64encode(file.read_bytes()).decode("ascii")
    return {"type": "image", "data": data, "mime_type": mime}


def make_file_name(prompt: str, wanted: str | None, extension: str) -> str:
    if wanted:
        stem = Path(wanted).stem
    else:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", prompt.lower()).strip("-")[:40]
        stem = f"{datetime.now():%Y%m%d-%H%M%S}-{slug or 'output'}"
    return f"{stem}.{extension}"


def video_format(aspect_ratio: str, resolution: str) -> dict:
    fmt = {"type": "video", "aspect_ratio": aspect_ratio, "resolution": resolution}
    # Inline answers are limited to about 4 MB; bigger videos come as a file.
    if resolution in ("1080p", "4k"):
        fmt["delivery"] = "uri"
    return fmt


def frame_content(
    prompt: str,
    first_frame: str | None,
    last_frame: str | None,
    reference_images: list[str],
) -> list[dict]:
    content: list[dict] = []
    guide: list[str] = []
    if first_frame:
        content.append(image_part(first_frame))
        guide.append("Use the first image as the starting frame.")
    if last_frame:
        content.append(image_part(last_frame))
        guide.append(f"Use the {'second' if first_frame else 'first'} image as the last frame.")
    for ref in reference_images:
        content.append(image_part(ref))
    if reference_images:
        guide.append(
            f"Keep the subjects in the last {len(reference_images)} image(s) "
            "consistent as references."
        )
    content.append({"type": "text", "text": " ".join([*guide, prompt])})
    return content


# -- tools ---------------------------------------------------------------------


def register(mcp: MCPServer, settings: Settings) -> Media:
    media = Media(settings)

    def paid(fn):
        description = spending_note(inspect.getdoc(fn), settings)
        mcp.add_tool(fn, annotations=PAID, description=description)
        return fn

    async def start_video(
        content: list[dict],
        *,
        aspect_ratio: str,
        resolution: str,
        name: str,
        previous_id: str | None,
        wait_seconds: int,
        ctx: Context | None,
    ) -> str:
        request: dict = dict(
            model=VIDEO_MODEL,
            input=content,
            response_format=video_format(aspect_ratio, resolution),
            store=True,  # needed to edit or extend the result later
        )
        if previous_id:
            request["previous_interaction_id"] = previous_id
        interaction = await media.create(request)
        media.names[interaction.id] = name
        return await media.finish_video(interaction, wait_seconds, ctx)

    @paid
    async def video_generate(
        prompt: str,
        aspect_ratio: VideoAspect = "16:9",
        resolution: VideoResolution = "720p",
        first_frame: str | None = None,
        last_frame: str | None = None,
        reference_images: list[str] | None = None,
        file_name: str | None = None,
        wait_seconds: int = 300,
        ctx: Context | None = None,
    ) -> str:
        """Generate a short video with native sound from a text prompt, with Gemini
        Omni Flash through the Gemini API, and save it as an .mp4 in
        GEMINI_PRO_OUTPUT_DIR. One call makes one clip of about 8 seconds; for
        longer videos chain video_edit, or use flow_make_video on the user's Flow
        credits when browser tools are enabled.

        COSTS MONEY: billed to the API key's Google Cloud project (about $0.10 per
        second of 720p video, no free tier). Confirm with the user before calling.

        Args:
            prompt: Subject, action, setting, camera and sound, e.g. "A red tram
                crosses Baku at sunset, slow dolly shot, street noise". English works
                best; timecodes like "[0-3s] ... [3-6s] ..." sequence the shot.
            aspect_ratio: "16:9" (landscape, default) or "9:16" (vertical).
            resolution: "720p" (default), "360p", or upscaled "1080p" or "4k".
            first_frame: Local image path the video starts from.
            last_frame: Local image path the video ends on.
            reference_images: Up to 3 local images of characters or objects to keep.
            file_name: Optional .mp4 file name; default is the date plus prompt words.
            wait_seconds: How long to wait for the render (default 300) before
                returning an id to fetch later with video_check.

        Returns:
            The saved .mp4 path and an id to change or extend it with video_edit;
            or, if rendering takes longer than wait_seconds, an id for video_check.
        """
        refs = reference_images or []
        if len(refs) > 3:
            return "Error: at most 3 reference images are supported."
        try:
            return await start_video(
                frame_content(prompt, first_frame, last_frame, refs),
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                name=make_file_name(prompt, file_name, "mp4"),
                previous_id=None,
                wait_seconds=wait_seconds,
                ctx=ctx,
            )
        except API_ERRORS as e:
            return describe_api_error(e)
        except MediaError as e:
            return f"Error: {e}"

    @paid
    async def video_edit(
        instruction: str,
        previous_id: str | None = None,
        video_path: str | None = None,
        aspect_ratio: VideoAspect = "16:9",
        resolution: VideoResolution = "720p",
        file_name: str | None = None,
        wait_seconds: int = 300,
        ctx: Context | None = None,
    ) -> str:
        """Change or extend a video; the result is saved as a new file.

        COSTS MONEY: billed like video_generate. Confirm with the user before calling.
        Give exactly one of previous_id (from video_generate/video_edit) or
        video_path (a local video of 10 seconds or less).

        Args:
            instruction: e.g. "Make it night", or to extend: "Continue the scene:
                the car drives off" (adds 3-10 s, up to 40 s in total).
            previous_id: id returned by an earlier video_generate or video_edit.
            video_path: Local video (max 10 s) to edit instead.
            aspect_ratio: "16:9" or "9:16".
            resolution: "720p" (default), "360p", "1080p" or "4k".
            file_name: Optional .mp4 file name.
            wait_seconds: How long to wait before returning an id for video_check.

        Returns:
            The saved .mp4 path and a new id (or an id for video_check).
        """
        if bool(previous_id) == bool(video_path):
            return "Error: give exactly one of previous_id or video_path."
        try:
            content: list[dict] = []
            if video_path:
                path = Path(video_path).expanduser()
                if not path.is_file():
                    return f"Error: video not found: {path}"
                content.append({"type": "video", "uri": await media.upload_video(path)})
            content.append({"type": "text", "text": instruction})
            return await start_video(
                content,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                name=make_file_name(instruction, file_name, "mp4"),
                previous_id=previous_id,
                wait_seconds=wait_seconds,
                ctx=ctx,
            )
        except API_ERRORS as e:
            return describe_api_error(e)
        except MediaError as e:
            return f"Error: {e}"

    @mcp.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False,  # saves the finished file
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        )
    )
    async def video_check(id: str, wait_seconds: int = 120, ctx: Context | None = None) -> str:
        """Fetch a video that video_generate or video_edit started but had not
        finished rendering when they returned, and save it as an .mp4. Free: the
        video was paid for when it was started, and checking costs nothing. Call it
        again with the same id if the video is still rendering.

        Args:
            id: The id returned by video_generate or video_edit.
            wait_seconds: How long to keep waiting in this call (default 120)
                before returning the current status.

        Returns:
            The saved .mp4 path and an id for video_edit once the video is ready;
            otherwise its status (still rendering, or failed with the reason).
        """
        try:
            interaction = await media.client.aio.interactions.get(id)
            return await media.finish_video(interaction, wait_seconds, ctx)
        except API_ERRORS as e:
            return describe_api_error(e)
        except MediaError as e:
            return f"Error: {e}"

    @paid
    async def image_generate(
        prompt: str,
        model: ImageModel = "gemini-nano-banana-2.1",
        aspect_ratio: ImageAspect = "1:1",
        image_size: ImageSize = "1K",
        input_images: list[str] | None = None,
        previous_id: str | None = None,
        file_name: str | None = None,
    ) -> str:
        """Create a new image from a prompt, or edit local images, with Nano Banana
        through the Gemini API, and save the result in GEMINI_PRO_OUTPUT_DIR. Pass
        previous_id to refine an earlier result step by step ("make the sky
        darker") without starting over.

        COSTS MONEY: about $0.034 (1K), $0.05 (2K) or $0.11 (4K) per image with
        Nano Banana 2.1; Nano Banana Pro ("gemini-3-pro-image") is $0.13-0.24.
        No free tier. Confirm with the user before calling.

        Args:
            prompt: What to draw, or how to change the input images, e.g. "Turn
                this sketch into a clean flat app icon on a white background".
            model: "gemini-nano-banana-2.1" (default), "gemini-3.1-flash-lite-image"
                (cheapest, 1K only) or "gemini-3-pro-image" (best, for hard tasks).
            aspect_ratio: "1:1" (default), "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
                "9:16", "16:9" or "21:9".
            image_size: "1K" (default), "2K" or "4K".
            input_images: Local image paths to edit or to use as references.
            previous_id: The id of an earlier image_generate result to refine.
            file_name: Optional file name; default is the date plus prompt words.

        Returns:
            The saved image path and an id to pass as previous_id for further edits.
        """
        try:
            content = [image_part(p) for p in input_images or []]
            content.append({"type": "text", "text": prompt})
            request: dict = dict(
                model=model,
                input=content,
                response_format={
                    "type": "image",
                    "aspect_ratio": aspect_ratio,
                    "image_size": image_size,
                },
                store=True,
            )
            if previous_id:
                request["previous_interaction_id"] = previous_id
            interaction = await media.client.aio.interactions.create(**request)
            interaction = await media.wait(interaction, 300, None)
            failed = failure_text(interaction)
            if failed:
                return failed
            image = interaction.output_image
            extension = (mimetypes.guess_extension(image.mime_type or "") or ".png").lstrip(".")
            path = media.save_path(make_file_name(prompt, file_name, extension))
            path.write_bytes(await media.download(image))
            return f"Saved: {path}\nid: {interaction.id} (pass it as previous_id to refine)"
        except API_ERRORS as e:
            return describe_api_error(e)
        except MediaError as e:
            return f"Error: {e}"

    return media
