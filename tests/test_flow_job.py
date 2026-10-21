from gemini_pro_mcp.config import Settings
from gemini_pro_mcp.flow import tools


class FakeFlow:
    """Flow that accepts a clip, queues it, and delivers it on the second check."""

    sent = 0
    collected = 0

    def __init__(self, settings):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        pass

    async def open_project(self, project_id=None):
        return "project"

    async def send(self, request, *, new_session, wait_seconds):
        FakeFlow.sent += 1
        return ""

    async def pending_permission(self):
        return object()

    async def media(self):
        return [{}] * 3

    async def approve(self, output_dir, stem, wait_seconds):
        return []  # approved and paid, but still in Flow's queue

    async def collect_new(self, before, output_dir, stem, wait_seconds):
        assert before == 3
        FakeFlow.collected += 1
        return [output_dir / f"{stem}.mp4"] if FakeFlow.collected == 2 else []


async def test_a_queued_clip_is_collected_not_paid_for_again(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "Flow", FakeFlow)
    job = {"status": "generating clip 1/1"}
    path = await tools.generate_clip(Settings.from_env(), job, "a clip", tmp_path, "clip-01")
    assert path == tmp_path / "clip-01.mp4"
    assert FakeFlow.sent == 1
    assert FakeFlow.collected == 2
