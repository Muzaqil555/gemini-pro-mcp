from gemini_pro_mcp.server import build_server

EXPECTED_PROMPTS = {
    "gemini_review",
    "gemini_research",
    "second_opinion",
    "jules_task",
    "notebook_workflow",
    "make_video",
}


async def test_mcp_prompts_are_registered():
    server = build_server()
    prompts = await server.list_prompts()
    assert {p.name for p in prompts} == EXPECTED_PROMPTS


async def test_mcp_prompts_render_instructions_with_arguments():
    server = build_server()

    review = await server.get_prompt("gemini_review", {"focus": "auth security"})
    assert "gemini_ask" in review.messages[0].content.text
    assert "auth security" in review.messages[0].content.text

    opinion = await server.get_prompt(
        "second_opinion", {"question": "SQLite vs Postgres", "files": "src/db.py"}
    )
    assert "SQLite vs Postgres" in opinion.messages[0].content.text
    assert "src/db.py" in opinion.messages[0].content.text

    video = await server.get_prompt("make_video", {"idea": "Baku sunset", "duration": "30s"})
    assert "flow_make_video" in video.messages[0].content.text
    assert "Baku sunset" in video.messages[0].content.text
    assert "30s" in video.messages[0].content.text
