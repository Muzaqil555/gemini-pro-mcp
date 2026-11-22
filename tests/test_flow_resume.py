from gemini_pro_mcp.flow.tools import finished_clip


def test_finished_clip_matches_stems_with_glob_characters(tmp_path):
    clip = tmp_path / "trip [final]-01.mp4"
    clip.write_bytes(b"video")
    (tmp_path / "trip [final]-02.mp4").write_bytes(b"")  # an interrupted download
    assert finished_clip(tmp_path, "trip [final]-01") == clip
    assert finished_clip(tmp_path, "trip [final]-02") is None
    assert finished_clip(tmp_path, "trip [final]-03") is None


def test_finished_clip_does_not_match_other_clips(tmp_path):
    (tmp_path / "a-b-01.mp4").write_bytes(b"video")
    assert finished_clip(tmp_path, "a*-01") is None
