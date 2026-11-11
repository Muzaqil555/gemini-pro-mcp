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
- Build a Gemini Notebook from your documents and make an Audio Overview.
- Make a video of any length in Google Flow with the plan's monthly credits.

## What you need

- [uv](https://docs.astral.sh/uv/), which starts the server.
- The [Antigravity CLI](https://antigravity.google), signed in with your Google AI Pro or Ultra account, for the Gemini tools.
- Optional: a Gemini API key for the paid image and video tools, and a Jules API key for the Jules tools.

## What the plugin runs

The plugin starts the server with `uvx gemini-pro-mcp==<version>`. uv downloads that exact version of the package from PyPI, with its dependencies, and runs it on your computer over stdio. The plugin has no hooks, skills, commands or agents.

The server then runs or connects to these, only when you call the matching tool:

| Tool group | What it runs or connects to |
|---|---|
| `gemini_*` | The Antigravity CLI (`agy`) on your computer, in a sandbox. Only `gemini_code` can edit files, in the folder you name. |
| `jules_*` | The Jules API at `jules.googleapis.com`, with your Jules API key. |
| `video_*`, `image_generate` | The Gemini API, with your Gemini API key. These cost money and ask first. |
| `flow_*`, `notebook_*`, `gemini_app`, `google_*` | A separate Chrome profile on your computer that you sign in to yourself. Off until you enable them. |

## What data it sends, and where

- Your prompts, and the files you ask a tool to read or upload, go to the Google service behind that tool: Gemini through the Antigravity CLI, the Jules API, the Gemini API, or the Google web app open in your Chrome.
- Nothing is sent to the author of this plugin. The server has no telemetry and no analytics.
- API keys are read from your environment or from `~/.config/gemini-pro-mcp/.env` and are sent only to the Google API they belong to.
- The server never sees or types your Google password. You sign in yourself, in the Antigravity CLI and in the Chrome profile.
- Generated files are saved on your computer.

Google's own terms and privacy policy apply to what you send to Google. The browser tools automate Google's web apps on your account; they are experimental and off by default.

## Check your setup

```bash
uvx gemini-pro-mcp doctor
```

It shows what works on your computer and how to fix the rest.

This is an independent open-source project (MIT). It is not affiliated with, endorsed by or sponsored by Google or Anthropic.
