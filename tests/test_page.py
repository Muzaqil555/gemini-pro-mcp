import pytest

from gemini_pro_mcp.flow import page


class FakePage:
    main_frame = object()
    frames = [main_frame]


def test_stale_refs_point_to_the_existing_snapshot_tool():
    with pytest.raises(ValueError, match="call google_page again"):
        page.frame_for(FakePage(), "f2:5")
