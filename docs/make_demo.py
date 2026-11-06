"""Builds docs/demo.svg, the animated terminal demo at the top of the README.

Every output line is copied from a real run (paths shortened). Run it again
after changing a scene: `python docs/make_demo.py`.
"""

# ruff: noqa: E501  (the scenes are terminal lines, kept whole for readability)

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

CYCLE = 26.0  # seconds; the animation loops
WIDTH, LINE, TOP, LEFT, CHAR = 900, 21, 62, 22, 8.45
COLORS = {
    "text": "#c9d1d9",
    "dim": "#8b949e",
    "ok": "#3fb950",
    "skip": "#d29922",
    "cmd": "#58a6ff",
    "you": "#e6edf3",
    "tool": "#bc8cff",
}

# (title, start, end, lines). A line is (kind, text, appears_at); kind "type"
# is typed out, the others appear at once in that colour.
SCENES = [
    (
        "Terminal",
        0.0,
        9.5,
        [
            ("type", "$ gemini-pro-mcp doctor --flow", 0.4),
            ("text", "gemini-pro-mcp 0.1.0: what works on this computer", 2.4),
            ("ok", "  [ok] Antigravity CLI  signed in, 13 models", 2.9),
            ("ok", "  [ok] Gemini API key   set", 3.2),
            (
                "skip",
                "  [--] Jules API key    not set: the jules_* tools need it. Get one at…",
                3.5,
            ),
            ("ok", "  [ok] Playwright       installed", 3.8),
            (
                "ok",
                r"  [ok] Chrome           C:\Program Files\Google\Chrome\Application\chrome.exe",
                4.1,
            ),
            ("ok", "  [ok] Flow profile     ~/.config/gemini-pro-mcp/flow-chrome-profile", 4.4),
            ("ok", "  [ok] Flow sign-in     project fcdb03dc…, 108 credits", 6.0),
        ],
    ),
    (
        "Claude Code",
        9.5,
        18.5,
        [
            ("type", "> Ask Gemini for a second opinion on my average() function", 9.8),
            ("tool", "● gemini_ask   on your Google AI Pro plan, no API cost", 12.6),
            ("text", "  - Raises `ZeroDivisionError` if `values` is empty.", 14.6),
            (
                "text",
                "  - Raises `TypeError` if `values` is a generator or iterator without `len()`.",
                14.9,
            ),
            (
                "text",
                "  - Raises `TypeError` if elements are non-numeric or cannot be added to `0`.",
                15.2,
            ),
            ("dim", "  took 36 s", 15.5),
        ],
    ),
    (
        "Claude Code",
        18.5,
        CYCLE,
        [
            ("type", "> How many Google Flow credits do I have left?", 18.8),
            ("tool", "● flow_status", 21.0),
            ("text", "  Flow is ready. Project: fcdb03dc…. Credits left: 108.", 22.4),
        ],
    ),
]


def pct(seconds: float) -> str:
    return f"{min(max(seconds / CYCLE * 100, 0), 100):.3f}%"


class Builder:
    def __init__(self) -> None:
        self.css: list[str] = []
        self.count = 0

    def visible(self, start: float, end: float) -> str:
        """A CSS class that shows an element from `start` to `end` in every loop."""
        self.count += 1
        name = f"v{self.count}"
        fade = 0.15
        frames = [(0, 0), (start, 0), (start + fade, 1), (end - fade, 1), (end, 0), (CYCLE, 0)]
        if start <= 0:
            frames = [(0, 1), (end - fade, 1), (end, 0), (CYCLE, 0)]
        steps = " ".join(f"{pct(t)}{{opacity:{o}}}" for t, o in frames)
        self.css.append(f"@keyframes {name}{{{steps}}}")
        self.css.append(f".{name}{{opacity:0;animation:{name} {CYCLE}s linear infinite}}")
        return name


def build() -> str:
    b = Builder()
    body: list[str] = []
    height = TOP + LINE * max(len(lines) for *_, lines in SCENES) + 28
    for title, start, end, lines in SCENES:
        body.append(
            f'<text class="{b.visible(start, end)}" x="{WIDTH / 2}" y="25" '
            f'text-anchor="middle" fill="{COLORS["dim"]}" font-size="13">{escape(title)}</text>'
        )
        row = 0
        for kind, text, at in lines:
            y = TOP + row * LINE
            row += 1
            if kind == "type":
                speed = 0.045  # seconds per character
                chunks = [text[i : i + 2] for i in range(0, len(text), 2)]
                spans = []
                for i, chunk in enumerate(chunks):
                    cls = b.visible(at + i * 2 * speed, end)
                    spans.append(f'<tspan class="{cls}">{escape(chunk)}</tspan>')
                color = COLORS["cmd"] if text.startswith("$") else COLORS["you"]
                body.append(
                    f'<text x="{LEFT}" y="{y}" fill="{color}" xml:space="preserve">'
                    + "".join(spans)
                    + "</text>"
                )
                row += kind == "type" and text.startswith(">")  # a blank line after a prompt
            else:
                body.append(
                    f'<text class="{b.visible(at, end)}" x="{LEFT}" y="{y}" '
                    f'fill="{COLORS[kind]}" xml:space="preserve">{escape(text)}</text>'
                )
    dots = "".join(
        f'<circle cx="{22 + i * 20}" cy="21" r="6" fill="{c}"/>'
        for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840"))
    )
    style = "\n".join(b.css)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" \
viewBox="0 0 {WIDTH} {height}" role="img" aria-label="gemini-pro-mcp demo: doctor checks the \
setup, then Claude asks Gemini for a code review and reads the Flow credits">
<style>
text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace;\
font-size:14px}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important;opacity:1!important}}}}
{style}
</style>
<rect width="{WIDTH}" height="{height}" rx="10" fill="#0d1117"/>
<rect width="{WIDTH}" height="40" rx="10" fill="#161b22"/>
<rect y="30" width="{WIDTH}" height="10" fill="#161b22"/>
{dots}
{chr(10).join(body)}
</svg>
"""


if __name__ == "__main__":
    out = Path(__file__).with_name("demo.svg")
    out.write_text(build(), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")
