"""Joining clips into one video, locally and for free.

Uses the ffmpeg binary bundled with imageio-ffmpeg (installed with the `flow`
extra), so nothing has to be installed system-wide.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from .config import Settings

INSTALL_HINT = (
    "Joining videos needs the bundled ffmpeg: install with `pip install gemini-pro-mcp[flow]` "
    "(or `uvx --with imageio-ffmpeg gemini-pro-mcp`)."
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
    try:
        import imageio_ffmpeg
    except ImportError as e:
        raise StitchError(INSTALL_HINT) from e
    return imageio_ffmpeg.get_ffmpeg_exe()


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
        listing.write_text(
            "".join(f"file '{clip.resolve().as_posix()}'\n" for clip in clips), encoding="utf-8"
        )
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
        if code != 0:
            raise StitchError(f"ffmpeg failed: {err.strip()[:600]}")
    return output


def register(mcp: MCPServer, settings: Settings) -> None:
    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False))
    async def video_stitch(clips: list[str], file_name: str = "stitched") -> str:
        """Join video clips, in the given order, into one .mp4. Local and free.

        Args:
            clips: Paths of the clips, first to last.
            file_name: Name of the joined file (saved in the output folder).

        Returns:
            The path of the joined video.
        """
        try:
            path = unique_path(settings.output_dir, Path(file_name).stem, ".mp4")
            path = await stitch([Path(c).expanduser() for c in clips], path)
            return f"Saved: {path}"
        except StitchError as e:
            return f"Error: {e}"
