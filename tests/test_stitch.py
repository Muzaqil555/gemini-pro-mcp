import asyncio
import os
import subprocess
import sys
import time

import pytest

from gemini_pro_mcp import stitch

imageio_ffmpeg = pytest.importorskip("imageio_ffmpeg")


def make_clip(path, seconds, color):
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s=128x72:r=24:d={seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        check=True,
    )


def duration(path):
    frames = imageio_ffmpeg.count_frames_and_secs(str(path))
    return frames[1]


async def test_stitch_joins_in_order(tmp_path):
    a, b = tmp_path / "a.mp4", tmp_path / "b.mp4"
    make_clip(a, 2, "red")
    make_clip(b, 1, "blue")
    out = await stitch.stitch([a, b], tmp_path / "out.mp4")
    assert out.is_file()
    assert duration(out) == pytest.approx(3, abs=0.2)


async def test_stitch_reports_missing_clip(tmp_path):
    with pytest.raises(stitch.StitchError, match="not found"):
        await stitch.stitch([tmp_path / "nope.mp4"], tmp_path / "out.mp4")


def test_unique_path(tmp_path):
    (tmp_path / "v.mp4").write_bytes(b"")
    assert stitch.unique_path(tmp_path, "v", ".mp4").name == "v-2.mp4"


def _running(pid: int) -> bool:
    """Whether a process is still alive, without signalling it."""
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True
        ).stdout
        return str(pid) in out
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        time.sleep(0.1)
    return True


async def test_run_stops_ffmpeg_when_the_call_is_cancelled(tmp_path):
    pid_file = tmp_path / "ffmpeg.pid"
    script = (
        f"import os, time; open({str(pid_file)!r}, 'w').write(str(os.getpid())); time.sleep(120)"
    )
    task = asyncio.ensure_future(stitch._run([sys.executable, "-c", script]))
    for _ in range(100):
        if pid_file.exists() and pid_file.read_text():
            break
        await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not _running(int(pid_file.read_text()))
