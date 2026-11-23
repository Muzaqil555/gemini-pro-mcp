"""Joining clips into one video, locally and for free.

Uses the ffmpeg binary bundled with imageio-ffmpeg (installed with the `flow`
extra), so nothing has to be installed system-wide; without it, the ffmpeg on PATH.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from .config import Settings

INSTALL_HINT = (
    "Joining videos needs ffmpeg. Install ffmpeg so that `ffmpeg` is on PATH, or install "
    "the bundled one: `pip install gemini-pro-mcp[flow]` (or `uvx --with imageio-ffmpeg "
    "gemini-pro-mcp`)."
)


class StitchError(RuntimeError):
    pass


def unique_path(folder: Path, stem: str, suffix: str) -> Path:
    path = folder / f"{stem}{suffix}"
    n = 2
    while path.exists():
        path = folder / f"{stem}-{n}{suffix}"
        n += 1
    return path


def ffmpeg_exe() -> str:
    """The ffmpeg bundled with imageio-ffmpeg, else the one on PATH."""
    try:
        import imageio_ffmpeg
    except ImportError:
        on_path = shutil.which("ffmpeg")
        if on_path:
            return on_path
        raise StitchError(INSTALL_HINT) from None
    return imageio_ffmpeg.get_ffmpeg_exe()


def concat_listing(clips: list[Path]) -> str:
    """The concat demuxer's file list; a ' in a path is written as '\\''."""
    lines = []
    for clip in clips:
        path = clip.resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{path}'\n")
    return "".join(lines)


async def _run(args: list[str]) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    return process.returncode, stderr.decode("utf-8", errors="replace")


async def stitch(clips: list[Path], output: Path) -> Path:
    """Joins clips in order. Copies the streams when the clips match (fast and
    lossless, true for clips from one model); otherwise re-encodes."""
    if not clips:
        raise StitchError("No clips to join.")
    for clip in clips:
        if not clip.is_file():
            raise StitchError(f"Clip not found: {clip}")
    exe = ffmpeg_exe()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        listing = Path(tmp) / "clips.txt"
        listing.write_text(concat_listing(clips), encoding="utf-8")
        base = [exe, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0"]
        code, err = await _run([*base, "-i", str(listing), "-c", "copy", str(output)])
        if code != 0:
            code, err = await _run(
                [
                    *base,
                    "-i",
                    str(listing),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    "-c:a",
                    "aac",
                    "-movflags",
                    "+faststart",
                    str(output),
                ]
            )
        # The concat demuxer stops at a clip it can't read, and ffmpeg still exits
        # with 0 after writing only the clips before it.
        if code != 0 or "Impossible to open" in err:
            output.unlink(missing_ok=True)
            raise StitchError(f"ffmpeg failed: {err.strip()[:600]}")
    return output


def register(mcp: MCPServer, settings: Settings) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    async def video_stitch(clips: list[str], file_name: str = "stitched") -> str:
        """Join local video clips, in the given order, into one .mp4 with ffmpeg.
        Runs on this computer and costs nothing. Clips with the same format (e.g.
        all from video_generate or Flow) are joined losslessly; mixed formats are
        re-encoded to H.264/AAC. Use it to combine clips made by video_generate,
        video_edit or flow_collect; flow_make_video already joins its own clips.

        Args:
            clips: Paths of the clips, first to last (at least one).
            file_name: Name for the joined file, saved in GEMINI_PRO_OUTPUT_DIR; a
                number is added if it already exists.

        Returns:
            "Saved: <path>" with the joined video, or an error such as a missing clip.
        """
        try:
            path = unique_path(settings.output_dir, Path(file_name).stem, ".mp4")
            path = await stitch([Path(c).expanduser() for c in clips], path)
            return f"Saved: {path}"
        except StitchError as e:
            return f"Error: {e}"
