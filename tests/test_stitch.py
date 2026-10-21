import subprocess

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
