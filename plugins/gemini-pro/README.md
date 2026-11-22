# gemini-pro

Use your Google AI Pro subscription from Claude Code. This plugin adds one local MCP server, [gemini-pro-mcp](https://github.com/Muzaqil555/gemini-pro-mcp), with tools for Gemini, Deep Research, Jules, Gemini Notebooks and Google Flow video.

## Install

```
/plugin install gemini-pro --marketplace Muzaqil555/gemini-pro-mcp
```

## What Claude can do with it

- Ask Gemini for a second opinion on a file or a diff, on the plan's limits.
- Run Deep Research and get the sources back.
- Start a Jules task on a GitHub repository.
- Make videos and images through the Gemini API, and join clips into one video.

With the [browser tools](#browser-tools) set up, Claude can also do these:

- Build a Gemini Notebook from your documents and make an Audio Overview.
- Make a video of any length in Google Flow with the plan's monthly credits.

## Commands

| Command | What it does |
|---|---|
| `/gemini-pro:gemini-review [focus]` | Gemini reviews your current changes. Claude then checks each point against the code. |
| `/gemini-pro:gemini-research <question>` | Research on the live web with Gemini and Google Search. The answer lists its sources. |
| `/gemini-pro:jules <task>` | Hands a task on your GitHub repository to Jules. You confirm it first, and Jules waits for you to approve its plan. |
| `/gemini-pro:notebook <files or links> [question or output]` | Builds a Gemini Notebook, then answers a question or makes an Audio Overview, slides, a mind map and more. It needs the [browser tools](#browser-tools). |

The plugin also has a skill that tells Claude which tool fits which request. It also marks which tools cost money and which change files.

## What you need

- [uv](https://docs.astral.sh/uv/), which starts the server.
- The [Antigravity CLI](https://antigravity.google), signed in with your Google AI Pro or Ultra account, for the Gemini tools.
- Optional: a Gemini API key for the paid image and video tools, and a Jules API key for the Jules tools.

## What the plugin runs

The plugin starts the server with `uvx --from git+https://github.com/Muzaqil555/gemini-pro-mcp@<commit> gemini-pro-mcp`, where `<commit>` is the full commit of the released version. uv fetches that commit from GitHub, installs it with its dependencies from PyPI, and runs it on your computer over stdio. You need git for this. The first start downloads and installs everything, which takes a minute or two. After that, the server starts in a few seconds. Besides the server, the plugin holds one skill and four commands, all plain Markdown instructions for Claude. It has no hooks and no agents, and none of its files run code.

The server then runs or connects to these, only when you call the matching tool:

| Tool group | What it runs or connects to |
|---|---|
| `gemini_*` | The Antigravity CLI (`agy`) on your computer, in a sandbox. Only `gemini_code` can edit files, in the folder you name. |
| `jules_*` | The Jules API at `jules.googleapis.com`, with your Jules API key. |
| `video_generate`, `video_edit`, `video_check`, `image_generate` | The Gemini API, with your Gemini API key. These cost money and ask first. |
| `video_stitch` | ffmpeg on your computer. It is free and needs `ffmpeg` on your PATH. |
| `flow_*`, `notebook_*`, `gemini_app`, `google_*` | A separate Chrome profile on your computer that you sign in to yourself. These are the [browser tools](#browser-tools), and the plugin's server doesn't include them. |

## Browser tools

The Flow, Gemini Notebook, Gemini app and AI Mode tools work in a Chrome profile that you sign in to yourself. They need Playwright, a 40 MB download. The plugin's server leaves Playwright out, so that its first start stays short.

To use these tools, add the full server next to the plugin. Run these once, and sign in to Google in the window that opens:

```bash
uvx gemini-pro-mcp setup --client claude --browser
uvx --from "gemini-pro-mcp[flow]" gemini-pro-mcp flow-login
```

Then restart Claude Code. The plugin's commands and skill work with either server.

## What data it sends, and where

- Your prompts, and the files you ask a tool to read or upload, go to the Google service behind that tool: Gemini through the Antigravity CLI, the Jules API, the Gemini API, or the Google web app open in your Chrome.
- Nothing is sent to the author of this plugin. The server has no telemetry and no analytics.
- API keys are read from your environment or from `~/.config/gemini-pro-mcp/.env` and are sent only to the Google API they belong to.
- The server never sees or types your Google password. You sign in yourself, in the Antigravity CLI and in the Chrome profile.
- Generated files are saved on your computer.

The full statement is in the [privacy policy](https://github.com/Muzaqil555/gemini-pro-mcp/blob/main/PRIVACY.md).

Google's own terms and privacy policy apply to what you send to Google. The browser tools automate Google's web apps on your account; they are experimental and off by default.

## Check your setup

```bash
uvx gemini-pro-mcp doctor
```

It shows what works on your computer and how to fix the rest.

This is an independent open-source project (MIT). It is not affiliated with, endorsed by or sponsored by Google or Anthropic.
