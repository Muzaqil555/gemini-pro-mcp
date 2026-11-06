"""Renders docs/social-preview.html to docs/social-preview.png (1280x640).

Needs the `flow` extra for Playwright: `uv run --extra flow python docs/make_social_preview.py`.
Upload the PNG in the repository's Settings -> Social preview.
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from gemini_pro_mcp.flow.browser import find_chrome

HERE = Path(__file__).parent


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=find_chrome())
        page = await browser.new_page(viewport={"width": 1280, "height": 640})
        await page.goto((HERE / "social-preview.html").resolve().as_uri())
        await page.screenshot(path=HERE / "social-preview.png")
        await browser.close()
    print(f"wrote {HERE / 'social-preview.png'}")


asyncio.run(main())
