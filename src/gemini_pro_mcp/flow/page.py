"""Generic access to any Flow page, including Flow's tool apps.

Flow has dozens of tools (Image Editor, Video Resizer, Transition Machine,
community tools...), each a small app with its own interface, often inside an
iframe. Instead of one MCP tool per Flow tool, `flow_page` shows the model the
page as text with numbered elements and `flow_act` clicks, types or uploads
files on them, the way a person would. Restricted to flow.google.com.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

ALLOWED = "https://flow.google.com/"

# Numbers every visible interactive element (data-gpm-ref) and returns them
# with the page text. `prefix` distinguishes iframes ("f1:", "f2:", ...).
SNAPSHOT_JS = r"""(prefix) => {
  const selector = 'button, a[href], input, textarea, select, [role=button], [role=textbox],'
    + ' [contenteditable=true], [role=tab], [role=menuitem], [role=menuitemradio], [role=option],'
    + ' [role=radio], [role=checkbox], [role=switch], [role=slider], [role=combobox], video';
  const items = [];
  let n = 0;
  for (const el of document.querySelectorAll(selector)) {
    const isFile = el.tagName === 'INPUT' && el.type === 'file';
    const r = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    if (!isFile && (r.width < 2 || r.height < 2 || style.visibility === 'hidden')) continue;
    const label = el.getAttribute('aria-label') || el.getAttribute('placeholder')
      || el.getAttribute('title') || el.getAttribute('alt') || '';
    if (label.startsWith('Google Account')) continue;  // the user's name and e-mail
    const ref = prefix + (++n);
    el.setAttribute('data-gpm-ref', ref);
    const checked = el.getAttribute('aria-checked') || el.getAttribute('aria-selected')
      || (el.type === 'checkbox' || el.type === 'radio' ? String(el.checked) : null);
    items.push({
      ref, tag: el.tagName.toLowerCase(), role: el.getAttribute('role'), type: el.type || null,
      label: label.slice(0, 80),
      text: (el.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 80),
      value: ('value' in el && typeof el.value === 'string' && !isFile)
        ? el.value.slice(0, 80) : null,
      disabled: el.disabled || el.getAttribute('aria-disabled') === 'true' || null,
      checked: checked === 'true' ? true : null,
    });
  }
  const body = document.body ? document.body.innerText : '';
  const text = body.replace(/\n{2,}/g, '\n').slice(0, 4000);
  return {text, items};
}"""

# Downloads a URL inside the page (with its cookies) and returns base64.
FETCH_JS = r"""async (src) => {
  const response = await fetch(src);
  if (!response.ok) throw new Error('HTTP ' + response.status);
  const blob = await response.blob();
  const buffer = new Uint8Array(await blob.arrayBuffer());
  let binary = '';
  for (let i = 0; i < buffer.length; i += 0x8000)
    binary += String.fromCharCode.apply(null, buffer.subarray(i, i + 0x8000));
  return {type: blob.type, data: btoa(binary)};
}"""

SKIP_FRAMES = (
    "recaptcha",
    "accounts.google.com",
    "about:blank",
    "googletagmanager",
    "ogs.google.com",  # the Google bar (apps grid, account card)
    "apis.google.com",
    "notifications.google.com",
    "accounts.youtube.com",
)


def describe(item: dict) -> str:
    kind = item.get("role") or item["tag"]
    if item.get("type") and item["tag"] == "input":
        kind = f"input[{item['type']}]"
    parts = [f"[{item['ref']}] {kind}"]
    if item.get("label"):
        parts.append(f"'{item['label']}'")
    if item.get("text") and item["text"] != item.get("label"):
        parts.append(f'"{item["text"]}"')
    if item.get("value"):
        parts.append(f"value={item['value']!r}")
    if item.get("checked"):
        parts.append("(selected)")
    if item.get("disabled"):
        parts.append("(disabled)")
    return " ".join(parts)


async def wait_for_tool_frame(page, timeout: float = 20) -> None:
    """Flow tool apps load in an iframe a few seconds after the page."""
    if "/tool/" not in page.url:
        return
    waited = 0.0
    while waited < timeout:
        for frame in page.frames:
            if frame == page.main_frame or any(s in frame.url for s in SKIP_FRAMES):
                continue
            try:
                if await frame.locator("button, input, [role=button]").count():
                    return
            except Exception:
                pass
        await page.wait_for_timeout(1000)
        waited += 1


async def snapshot(page, max_items: int = 200, text_chars: int = 2500) -> str:
    """The page (and its tool iframes) as text with numbered elements."""
    await wait_for_tool_frame(page)
    sections = [f"URL: {page.url.split('?')[0]}"]
    frames = [page.main_frame] + [
        f for f in page.frames if f != page.main_frame and not any(s in f.url for s in SKIP_FRAMES)
    ]
    count = 0
    for index, frame in enumerate(frames):
        prefix = "" if index == 0 else f"f{index}:"
        try:
            data = await frame.evaluate(SNAPSHOT_JS, prefix)
        except Exception:
            continue
        if not data["items"] and index > 0:
            continue  # helper frames (bundlers, loaders) have nothing to operate
        title = "Page" if index == 0 else f"Tool frame f{index}"
        sections.append(f"--- {title} text ---\n{data['text'][:text_chars].strip()}")
        lines = []
        for item in data["items"]:
            if count >= max_items:
                lines.append("... (more elements; scroll or narrow down)")
                break
            lines.append(describe(item))
            count += 1
        if lines:
            sections.append(f"--- {title} elements ---\n" + "\n".join(lines))
    return "\n".join(sections)


def frame_for(page, ref: str):
    if ":" not in ref:
        return page.main_frame
    index = int(ref.split(":")[0].lstrip("f"))
    frames = [page.main_frame] + [
        f for f in page.frames if f != page.main_frame and not any(s in f.url for s in SKIP_FRAMES)
    ]
    if index >= len(frames):
        raise ValueError(f"Frame of {ref} is gone; call flow_page again.")
    return frames[index]


Action = Literal["click", "type", "replace", "press", "upload", "select", "hover", "scroll"]


async def act(
    page,
    ref: str,
    action: Action,
    text: str | None = None,
    files: list[str] | None = None,
    output_dir: Path | None = None,
    wait_seconds: float = 2,
) -> list[Path]:
    """Performs the action; returns files the page downloaded meanwhile (e.g. an
    Export button), saved to output_dir."""
    downloads: list = []

    def on_download(download) -> None:  # Playwright needs a plain function here
        downloads.append(download)

    page.on("download", on_download)
    try:
        await _act(page, ref, action, text, files)
        waited = 0.0
        while waited < wait_seconds and not downloads:
            await page.wait_for_timeout(500)
            waited += 0.5
        saved = []
        for download in downloads:
            name = Path(download.suggested_filename or "flow-download")
            folder = output_dir or Path.home() / "Downloads"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / name.name
            n = 2
            while path.exists():
                path = folder / f"{name.stem}-{n}{name.suffix}"
                n += 1
            await download.save_as(path)
            saved.append(path)
        return saved
    finally:
        page.remove_listener("download", on_download)


async def _act(page, ref: str, action: str, text: str | None, files: list[str] | None) -> None:
    if "accounts.google.com" in page.url:
        raise ValueError("Sign-in pages are never operated; the user signs in.")
    target = frame_for(page, ref).locator(f'[data-gpm-ref="{ref}"]').first
    if not await target.count():
        raise ValueError(f"No element [{ref}] (the page changed); call flow_page again.")
    if (await target.get_attribute("type")) == "password":
        raise ValueError("Typing into password fields is not allowed.")

    if action == "click":
        try:
            await target.click(timeout=10_000)
        except Exception:
            await target.dispatch_event("click")  # covered by an overlay
    elif action in ("type", "replace"):
        if text is None:
            raise ValueError("`text` is required for type/replace.")
        editable = await target.evaluate("e => e.isContentEditable")
        await target.click(timeout=10_000)
        if action == "replace":
            if editable:
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Delete")
            else:
                await target.fill("")
        await page.keyboard.type(text, delay=5)
    elif action == "press":
        await target.press(text or "Enter")
    elif action == "upload":
        paths = [str(Path(f).expanduser().resolve()) for f in files or []]
        missing = [p for p in paths if not Path(p).is_file()]
        if not paths or missing:
            raise ValueError(f"Give existing local files in `files`. Missing: {missing}")
        is_input = await target.evaluate("e => e.tagName === 'INPUT' && e.type === 'file'")
        if is_input:
            await target.set_input_files(paths)
        else:
            async with page.expect_file_chooser(timeout=15_000) as chooser:
                await target.click()
            await (await chooser.value).set_files(paths)
    elif action == "select":
        await target.select_option(label=text)
    elif action == "hover":
        await target.hover()
    elif action == "scroll":
        await target.scroll_into_view_if_needed()
    await page.wait_for_timeout(1500)


TOOL_CARDS_JS = r"""() => [...document.querySelectorAll('flow-applet-card')].map(card => {
  const spans = [...card.querySelectorAll('span')].map(s => s.innerText.trim()).filter(Boolean);
  return {name: spans[0] || '', author: spans[1] || '', about: spans[spans.length - 1] || ''};
})"""


def format_tools(groups: dict[str, list[dict]]) -> str:
    out = []
    for group, cards in groups.items():
        if not cards:
            continue
        out.append(f"## {group}")
        out.extend(f"- {c['name']} ({c['author']}): {c['about']}" for c in cards)
    return "\n".join(out) if out else "No tools found."
