from gemini_pro_mcp.notebook import download_path


def test_download_path_keeps_earlier_downloads(tmp_path):
    folder = tmp_path / "out"
    first = download_path(folder, "Overview.m4a")
    assert first == folder / "Overview.m4a"
    first.write_bytes(b"first")
    second = download_path(folder, "Overview.m4a")
    assert second == folder / "Overview-2.m4a"
    second.write_bytes(b"second")
    assert download_path(folder, "Overview.m4a") == folder / "Overview-3.m4a"


def test_download_path_ignores_folders_in_the_suggested_name(tmp_path):
    assert download_path(tmp_path, "../x/Overview.mp4") == tmp_path / "Overview.mp4"
    assert download_path(tmp_path, "") == tmp_path / "notebook-download"
