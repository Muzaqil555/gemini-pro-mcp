"""What a Google AI Pro plan includes, and how this server reaches each part.

Taken from Google One Help ("Use Google AI Pro benefits", October 2026). Plans
and regions change; `google_pro_benefits` says so and links the live page.
"""

from __future__ import annotations

SOURCE = "https://support.google.com/googleone/answer/14534406"

# how: which tools of this server use it. "web" means google_page/google_act on
# the given site, in the signed-in Chrome profile (see `gemini-pro-mcp flow-login`).
BENEFITS: list[dict[str, str]] = [
    # Gemini and models
    {
        "name": "Gemini app (4 Argon, 3.1 Pro, 3.8 Flash; thinking levels)",
        "site": "https://gemini.google.com",
        "how": "gemini_app (chat, files, model and thinking level)",
    },
    {
        "name": "Deep Research",
        "site": "https://gemini.google.com",
        "how": "gemini_app(tool='deep_research') + gemini_app_result",
    },
    {
        "name": "Images and videos in Gemini (Nano Banana, Veo), music, Canvas, Guided learning",
        "site": "https://gemini.google.com",
        "how": "gemini_app(tool='image'|'video'|'music'|'canvas'|'guided_learning')",
    },
    {
        "name": "Gemini Notebook (former NotebookLM): 300 sources, Audio/Video Overviews, "
        "flashcards, quizzes, slides, infographics",
        "site": "https://gemini.google.com (Notebooks)",
        "how": "web: google_page/google_act",
    },
    {
        "name": "Gemini 4 Argon in AI Mode (Google Search)",
        "site": "https://www.google.com/search?udm=50",
        "how": "google_ai_mode",
    },
    {
        "name": "Tasks in Gemini (multi-step workflows)",
        "site": "https://gemini.google.com",
        "how": "gemini_app (US, English only)",
    },
    {
        "name": "Gemini in Gmail, Docs, Sheets, Vids...",
        "site": "https://workspace.google.com",
        "how": "web: google_page/google_act; Gmail/Calendar/Drive/Sheets also have "
        "official MCP connectors",
    },
    # Developer
    {
        "name": "Google Antigravity (higher limits, Gemini 4 Argon, Claude models)",
        "site": "https://antigravity.google",
        "how": "gemini_ask, gemini_research, gemini_models (Antigravity CLI)",
    },
    {
        "name": "Google AI Studio (higher limits, Nano Banana Pro, app building)",
        "site": "https://aistudio.google.com",
        "how": "web: google_page/google_act (the UI); API keys for the media tools",
    },
    {
        "name": "Jules coding agent (GitHub, higher task limits)",
        "site": "https://jules.google.com",
        "how": "web: google_page/google_act",
    },
    {
        "name": "Google Developer Program premium: $10/month Cloud credit, Code Assist, "
        "Firebase Studio",
        "site": "https://developers.google.com/profile",
        "how": "video_generate, video_edit, image_generate (Gemini API, paid from the credit)",
    },
    {
        "name": "Google Colab (200 compute units)",
        "site": "https://colab.research.google.com",
        "how": "web: google_page/google_act (Google also ships a Colab MCP server)",
    },
    {
        "name": "Gemini in Android Studio",
        "site": "Android Studio (desktop IDE)",
        "how": "not reachable from MCP: use it in the IDE",
    },
    # Creative
    {
        "name": "Google Flow (Omni, Veo 3.1; text/ingredients/frames to video, images, tools)",
        "site": "https://flow.google.com",
        "how": "flow_make_video, flow_generate, flow_tools, flow_open_tool, flow_collect, "
        "google_page/google_act",
    },
    {
        "name": "Google Flow Music (10,000 credits/month, commercial use)",
        "site": "https://www.flowmusic.app",
        "how": "web: google_page/google_act (sign in there once with Google)",
    },
    {
        "name": "Playground (AI games)",
        "site": "https://playground.google",
        "how": "web: google_page/google_act (US only)",
    },
    {
        "name": "Gemini in Google Earth",
        "site": "https://earth.google.com",
        "how": "web: google_page/google_act (US only)",
    },
    {
        "name": "Google Photos AI (Photo to video, Remix)",
        "site": "Google Photos app",
        "how": "not reachable: Android/iOS app only",
    },
    {
        "name": "Auto browse in Gemini in Chrome; 'Have AI check pricing' in Search; Dreambeans; "
        "Google TV Create Hub",
        "site": "Chrome / Search / TV",
        "how": "region-limited (US, some India): not reachable from here",
    },
    # Other
    {
        "name": "5 TB storage (Drive, Gmail, Photos)",
        "site": "https://drive.google.com",
        "how": "official Google Drive MCP connector, or web",
    },
    {
        "name": "Google Health Premium, Google Home Premium, YouTube Premium Lite",
        "site": "apps / devices",
        "how": "not AI tools: nothing to control here",
    },
    {
        "name": "AI credits (buy more Flow/Antigravity usage)",
        "site": "https://one.google.com/ai/credits",
        "how": "never automated: purchases are left to the user",
    },
]


def as_text() -> str:
    lines = [
        "Google AI Pro benefits and how this server reaches them "
        f"(from {SOURCE}, October 2026; check it for changes):",
        "",
    ]
    for b in BENEFITS:
        lines.append(f"- {b['name']}\n  where: {b['site']}\n  how: {b['how']}")
    return "\n".join(lines)


def register(mcp) -> None:
    @mcp.tool()
    async def google_pro_benefits() -> str:
        """Everything a Google AI Pro plan includes, and which tool of this server
        reaches each part. Free. Browser-based tools need GEMINI_PRO_ENABLE_BROWSER=1.

        Returns:
            One entry per benefit: what it is, where it lives, how to use it here.
        """
        return as_text()
