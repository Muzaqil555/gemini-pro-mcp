import base64
import dataclasses
from types import SimpleNamespace

import pytest
from mcp.server.mcpserver import MCPServer

from gemini_pro_mcp import media
from gemini_pro_mcp.config import Settings


class FakeInteractions:
    """Stands in for client.aio.interactions; finishes after `polls` gets."""

    def __init__(self, output, polls=1, status="completed", reject_background=False):
        self.output, self.polls, self.status = output, polls, status
        self.reject_background = reject_background
        self.requests = []

    async def create(self, **request):
        self.requests.append(request)
        if request.get("background") and self.reject_background:
            raise FakeAPIError(400, "background is not supported for this model")
        if request.get("background"):
            return SimpleNamespace(id="int-1", status="in_progress", errors=None)
        return self._done()

    async def get(self, interaction_id):
        self.polls -= 1
        if self.polls > 0:
            return SimpleNamespace(id=interaction_id, status="in_progress", errors=None)
        return self._done()

    def _done(self):
        return SimpleNamespace(id="int-1", status=self.status, errors=None, **self.output)


class FakeAPIError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message, self.body = code, message, None


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "POLL_SECONDS", 0)
    monkeypatch.setattr(media, "API_ERRORS", (FakeAPIError,))
    settings = dataclasses.replace(Settings.from_env(), output_dir=tmp_path / "out")
    server = MCPServer("test")
    m = media.register(server, settings)

    def use(interactions):
        m._client = SimpleNamespace(aio=SimpleNamespace(interactions=interactions))
        return interactions

    return server, use, tmp_path


def text_of(result):
    content = result[0] if isinstance(result, tuple) else result
    if hasattr(content, "content"):
        content = content.content
    return content[0].text


def video_output():
    data = base64.b64encode(b"MP4DATA").decode()
    return {"output_video": SimpleNamespace(data=data, uri=None)}


async def test_video_generate_polls_and_saves(setup):
    server, use, tmp = setup
    fake = use(FakeInteractions(video_output(), polls=2))
    result = text_of(
        await server.call_tool(
            "video_generate", {"prompt": "A red ball", "file_name": "ball", "aspect_ratio": "9:16"}
        )
    )
    saved = tmp / "out" / "ball.mp4"
    assert f"Saved: {saved}" in result and "id: int-1" in result
    assert saved.read_bytes() == b"MP4DATA"
    request = fake.requests[0]
    assert request["model"] == media.VIDEO_MODEL and request["background"] is True
    assert request["store"] is True
    assert request["response_format"]["aspect_ratio"] == "9:16"


async def test_video_generate_falls_back_when_background_refused(setup):
    server, use, tmp = setup
    fake = use(FakeInteractions(video_output(), reject_background=True))
    result = text_of(await server.call_tool("video_generate", {"prompt": "x", "file_name": "v"}))
    assert "Saved:" in result
    assert [r.get("background") for r in fake.requests] == [True, None]


async def test_video_generate_returns_id_when_slow(setup):
    server, use, _ = setup
    use(FakeInteractions(video_output(), polls=100))
    result = text_of(await server.call_tool("video_generate", {"prompt": "x", "wait_seconds": 0}))
    assert "video_check" in result and "int-1" in result


async def test_video_edit_needs_exactly_one_source(setup):
    server, use, _ = setup
    use(FakeInteractions(video_output()))
    result = text_of(await server.call_tool("video_edit", {"instruction": "night"}))
    assert "exactly one" in result


async def test_failed_generation_is_reported(setup):
    server, use, _ = setup
    use(FakeInteractions(video_output(), status="failed", polls=1))
    result = text_of(await server.call_tool("video_generate", {"prompt": "x"}))
    assert "status 'failed'" in result


async def test_api_error_is_explained(setup):
    server, use, _ = setup

    class Refusing(FakeInteractions):
        async def create(self, **request):
            raise FakeAPIError(403, "Billing is not enabled")

    use(Refusing(video_output()))
    result = text_of(await server.call_tool("video_generate", {"prompt": "x"}))
    assert result.startswith("Error 403: Billing is not enabled") and "billing" in result


async def test_image_generate_saves_with_extension(setup):
    server, use, tmp = setup
    data = base64.b64encode(b"PNG").decode()
    output = {"output_image": SimpleNamespace(data=data, uri=None, mime_type="image/png")}
    fake = use(FakeInteractions(output))
    result = text_of(
        await server.call_tool(
            "image_generate", {"prompt": "logo", "image_size": "2K", "file_name": "logo"}
        )
    )
    assert (tmp / "out" / "logo.png").read_bytes() == b"PNG"
    assert "id: int-1" in result
    assert fake.requests[0]["response_format"]["image_size"] == "2K"


def test_frame_content_orders_images_and_guides(tmp_path):
    first = tmp_path / "a.png"
    ref = tmp_path / "r.jpg"
    first.write_bytes(b"1")
    ref.write_bytes(b"2")
    content = media.frame_content("drive", str(first), None, [str(ref)])
    assert [c["type"] for c in content] == ["image", "image", "text"]
    assert content[0]["mime_type"] == "image/png"
    assert content[-1]["text"].startswith("Use the first image as the starting frame.")
    assert content[-1]["text"].endswith("drive")


def test_missing_key_message(monkeypatch, tmp_path):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    m = media.Media(dataclasses.replace(Settings.from_env(), output_dir=tmp_path))
    with pytest.raises(media.MediaError, match="aistudio.google.com/apikey"):
        m.client  # noqa: B018


def test_message_of_reads_nested_body():
    error = FakeAPIError(400, "Error code: 400 - [...]")
    error.body = [{"error": {"code": 400, "message": "API key not valid."}}]
    assert media.message_of(error) == "API key not valid."
    assert "GEMINI_API_KEY" in media.describe_api_error(error)
