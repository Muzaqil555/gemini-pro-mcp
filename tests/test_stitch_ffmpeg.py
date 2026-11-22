"""Finding ffmpeg when the bundled imageio-ffmpeg is not installed (the plugin's install)."""

import sys

import pytest

from gemini_pro_mcp import stitch


def test_falls_back_to_ffmpeg_on_path(monkeypatch):
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)  # import now fails
    monkeypatch.setattr(stitch.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert stitch.ffmpeg_exe() == "/usr/bin/ffmpeg"


def test_explains_how_to_get_ffmpeg_when_there_is_none(monkeypatch):
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    monkeypatch.setattr(stitch.shutil, "which", lambda name: None)
    with pytest.raises(stitch.StitchError, match="ffmpeg"):
        stitch.ffmpeg_exe()
