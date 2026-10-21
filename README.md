# gemini-pro-mcp

**Use everything in the Google AI Pro subscription you already pay for from Claude, or any other MCP client: the Gemini app, Deep Research, Flow, AI Mode, Gemini Notebooks, AI Studio, Jules and more.**

[![CI](https://github.com/Muzaqil555/gemini-pro-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Muzaqil555/gemini-pro-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

One MCP server, four ways into Google's AI:

| Group | Tools | Runs on | Cost |
|---|---|---|---|
| **Gemini (subscription)** | `gemini_ask`, `gemini_research`, `gemini_models` | [Antigravity CLI](https://antigravity.google) signed in with your Google AI Pro/Ultra account | Free: uses your plan's limits |
| **Media (Gemini API)** | `video_generate`, `video_edit`, `video_check`, `image_generate`, `video_stitch` | Official Gemini API: Omni Flash video, Nano Banana images | Paid per use (AI Pro's monthly Cloud credit can cover it) |
| **Google AI web apps** *(experimental)* | `gemini_app`, `gemini_app_result`, `google_ai_mode`, `google_page`, `google_act`, `google_pro_benefits` | Your own signed-in Chrome: Gemini app, Notebooks, AI Mode, AI Studio, Jules, Colab, Flow Music, Docs | Your plan's limits |
| **Flow** *(experimental)* | `flow_make_video`, `flow_job`, `flow_generate`, `flow_approve`, `flow_reject`, `flow_collect`, `flow_status`, `flow_tools`, `flow_open_tool`, `flow_page`, `flow_act`: **every Flow feature and tool** | Your own signed-in Chrome at flow.google.com | Your plan's monthly Flow credits (e.g. 12 credits for an 8 s video) |

Ask Claude things like:

> *"Get a second opinion from Gemini on `src/auth.py`."*
> *"Research what changed in Flutter 3.47, with sources."*
> *"Make an 8-second vertical video of a red tram crossing Baku at sunset."*
> *"Turn this logo sketch (`./sketch.png`) into a clean flat icon, 2K."*
> *"Make a 2 minute video of a fox's journey through a snowy forest with my Flow credits."*

## Quick start

### 1. Prerequisites

- [uv](https://docs.astral.sh/uv/) (or Python 3.10+ with pip)
- For the **Gemini tools**: install the [Antigravity CLI](https://antigravity.google), run `agy` once and sign in with your Google AI Pro/Ultra account.
- For the **media tools**: an API key from [Google AI Studio](https://aistudio.google.com/apikey) with billing enabled. See [Costs](#costs).

### 2. Add it to your client

**Claude Code**

```bash
claude mcp add gemini-pro --scope user -- uvx --from git+https://github.com/Muzaqil555/gemini-pro-mcp gemini-pro-mcp
```

**Claude Desktop, Cursor, Windsurf and other clients.** Add this to the client's MCP config:

```json
{
  "mcpServers": {
    "gemini-pro": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/Muzaqil555/gemini-pro-mcp", "gemini-pro-mcp"]
    }
  }
}
```

### 3. Add your API key (media tools only)

Put it in `~/.config/gemini-pro-mcp/.env` so it stays out of client configs:

```
GEMINI_API_KEY=your-key
```

Or pass it as an `env` entry in the client config. Restart the client afterwards.

## Tools

### Gemini on your subscription

| Tool | What it does |
|---|---|
| `gemini_ask` | Ask Gemini anything. Pass `paths` to let it read local files or folders, and `conversation_id` to continue a chat. |
| `gemini_research` | Live web research with Google Search. The answer ends with source URLs. |
| `gemini_models` | Lists the models your account can use, for example Gemini 4 Argon and Gemini 3.8 Flash. |

Every request runs `agy --print` in **plan mode with the sandbox on**, so Gemini can read and search but cannot change your files or run commands.

### Media through the Gemini API

| Tool | What it does |
|---|---|
| `video_generate` | Text to video with native audio. Optional first frame, last frame and up to 3 reference images. 16:9 or 9:16, 360p to 4K. |
| `video_edit` | Edit a previous result (`previous_id`) or a local clip of 10 s or less, or extend it, up to 40 s in total. |
| `video_check` | Fetches a video that was still rendering. Free. |
| `image_generate` | Create or edit images with Nano Banana 2.1, Nano Banana 2 Lite or Nano Banana Pro, at 1K, 2K or 4K. |
| `video_stitch` | Joins clips into one MP4, locally and for free (bundled ffmpeg, `flow` extra). |

Files are saved to `~/gemini-pro-output` (change it with `GEMINI_PRO_OUTPUT_DIR`).

> Video uses **Gemini Omni Flash**. Google shut down the Veo 3.1 preview models on 2026-10-22 and recommends Omni Flash instead.

## Costs

Prices are taken from [Google's pricing page](https://ai.google.dev/gemini-api/docs/pricing) as of October 2026. Check it for current numbers.

| What | Price | Free tier |
|---|---|---|
| Gemini tools (`gemini_*`) | Included in Google AI Pro/Ultra (plan limits apply) | n/a |
| Video, Omni Flash 720p | about $0.10 per second (8 s ≈ $0.80) | none |
| Image, Nano Banana 2.1 | $0.034 (1K) / $0.05 (2K) / $0.11 (4K) | none |
| Image, Nano Banana Pro | $0.13 (1K/2K) / $0.24 (4K) | none |

**Does Google AI Pro pay for the API?** Not directly. Google says plan benefits apply in the AI Studio web UI, and API-key usage is billed separately. AI Pro does include a monthly Google Cloud credit through the Google Developer Program, which can be spent on the Gemini API once billing is enabled. Google's blog gives the amount as $10/month.

By default the server tells the model to **confirm with you before every paid call**. If you would rather not be asked, set `GEMINI_PRO_AUTO_APPROVE=1`: the model then just does it and reports the cost afterwards.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | (none) | Gemini API key for the media tools |
| `JULES_API_KEY` | (none) | Jules API key from jules.google.com/settings, for the `jules_*` tools |
| `GEMINI_PRO_OUTPUT_DIR` | `~/gemini-pro-output` | Where videos and images are saved |
| `AGY_PATH` | `agy` on PATH | Path to the Antigravity CLI |
| `GEMINI_PRO_AGY_MODEL` | agy's default | Default model for `gemini_*` tools |
| `GEMINI_PRO_AGY_TIMEOUT` | `600` | Seconds per Antigravity request |
| `GEMINI_PRO_ENABLE_BROWSER` | off | `1` registers the browser tools (Flow, Gemini app, AI Mode, Google AI sites) |
| `GEMINI_PRO_FLOW_PROJECT` | open or most recent project | Flow project id to work in |
| `GEMINI_PRO_AUTO_APPROVE` | off | `1` = spending is pre-approved: no confirmation questions, Flow requests are approved automatically |
| `GEMINI_PRO_ENV_FILE` | `~/.config/gemini-pro-mcp/.env` | Optional file with any of the above |

## Everything in Google AI Pro

`google_pro_benefits` lists every benefit of the plan and the tool that reaches it. Here is the short version:

| Benefit | How this server reaches it |
|---|---|
| Gemini app: 4 Argon, 3.1 Pro, thinking levels, files | `gemini_app` |
| Deep Research | `gemini_app(tool="deep_research")`, then `gemini_app_result` |
| Images (Nano Banana), Veo videos, music, Canvas, Guided learning in Gemini | `gemini_app(tool=...)` |
| Gemini Notebook (former NotebookLM): sources, Audio/Video Overviews, slides, quizzes... | `notebook_list`, `notebook_create`, `notebook_add_sources`, `notebook_ask`, `notebook_studio` |
| AI Mode in Google Search | `google_ai_mode` |
| Google Flow: video, images, every Flow tool | `flow_*` tools |
| Antigravity: Gemini 4 Argon on your quota | `gemini_ask`, `gemini_research`, `gemini_code` (edits a folder), `gemini_agents` |
| Jules coding agent (GitHub, PRs) | `jules_start`, `jules_status`, `jules_approve_plan`, `jules_message`, `jules_sources`, `jules_sessions` (official API, `JULES_API_KEY`) |
| AI Studio, Colab, Flow Music, Gemini in Docs | `google_page` / `google_act` |
| $10/month Cloud credit (Developer Program) | `video_generate`, `image_generate` (Gemini API) |
| 5 TB storage, Gmail, Calendar | Google's official MCP connectors |
| Mobile-only or US-only features (Photos AI, Auto browse, TV Create Hub, Earth...) | Listed by `google_pro_benefits` as out of reach |
| Buying AI credits | Never automated |

`google_page` and `google_act` work like a person in your browser. They read a page as numbered elements, then click, type, upload files, choose options and download results, so a new feature in any of these apps is usable on day one. They only operate the Google AI sites listed in `google_web.py`. Sign-in, payment and account pages are off limits.

## Flow (experimental)

[Google Flow](https://flow.google.com) has no public API. The Flow tools drive the website in a **dedicated Chrome profile that you sign in to yourself**:

```bash
uvx --from "gemini-pro-mcp[flow] @ git+https://github.com/Muzaqil555/gemini-pro-mcp" gemini-pro-mcp flow-login
```

Then set `GEMINI_PRO_ENABLE_BROWSER=1` (the older `GEMINI_PRO_ENABLE_FLOW=1` still works). This enables every browser-based tool: Flow, the Gemini app, AI Mode and the other Google AI sites, all in that one signed-in profile.

| Tool | What it does | Credits |
|---|---|---|
| `flow_make_video` | **Any length** (e.g. `duration_seconds=120`). Gemini splits the idea into 4–8 s shots with matching descriptions, Flow generates each one, and the clips are joined into one MP4. Runs in the background. | ~12 per 8 s |
| `flow_job` | Progress of `flow_make_video`: clips done, credits used, final file | none |
| `flow_generate` | Sends your request to Flow's agent and returns its answer, including the cost question (*"…1 video generation, costing 12 credits?"*) | none |
| `flow_approve` | Answers that question with Approve, waits for the result and saves it (720p MP4 / original image) | **spends credits** |
| `flow_reject` | Declines the pending request | none |
| `flow_collect` | Downloads the newest items of the project | none |
| `flow_status` | Checks the sign-in and shows the credits left | none |
| `flow_tools` | Lists every Flow tool: Google's (Image Editor, Mockup, Shot Explorer, Mask Magic, Video Resizer, Transition Machine, Type Overlays, Shader Effects, Poster Designer…), the community's and your own | none |
| `flow_open_tool` | Opens a tool by name and shows its interface (a Google or community tool becomes your own "Remix of …" copy, as in Flow) | none |
| `google_page` / `google_act` | Read any Flow page or tool as numbered elements, then click, type, upload files, pick options or export, like a person. This reaches whatever has no dedicated tool: Characters, Scenes, Library, upscaling, each tool's controls | depends on the button |

**Every Flow feature is reachable.** Flow's agent (`flow_generate`) handles anything you can ask in words, and `google_page` + `google_act` operate anything with buttons. For example, *"put my last clip through Video Resizer at 9:16"* opens the tool, imports the clip, exports a 9:16 copy and downloads it. That flow was tested end to end.

By default spending is a **separate call**: `flow_generate` stops at Flow's own permission question, and the model has to ask you before it calls `flow_approve`. With `GEMINI_PRO_AUTO_APPROVE=1` the tools approve it themselves. Either way, keep Flow's *"Confirm before generating: Always"* setting on (the default), because the tools rely on that question.

Tested on 2026-10-21 with Omni 1.1 Flash: an 8 s, 1280×720, 24 fps video for 12 credits, end to end.

> **Read this first.** Automating Flow's website may conflict with Google's terms of service, and it breaks whenever Google changes the page. This project never types or stores your credentials and uses no stealth tricks. If Google shows a CAPTCHA, you solve it. Use at your own risk.

## How it works

```
Claude ── MCP (stdio) ──> gemini-pro-mcp ──┬── agy --print (plan + sandbox) ──> Gemini on your AI Pro plan
                                           ├── google-genai Interactions API ──> Omni Flash / Nano Banana
                                           └── Playwright over CDP ──> your Chrome ──> flow.google.com
```

## Roadmap

- [x] Flow: generate, approve and download videos with plan credits
- [x] Flow: videos of any length (`flow_make_video`)
- [ ] Flow: images, characters, smoother shot transitions (extend instead of separate clips)
- [ ] Music generation (Lyria)
- [ ] Publish to PyPI (`uvx gemini-pro-mcp`)
- [ ] Deep Research reports
- [ ] Demo GIF

Ideas and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Disclaimer

This is an independent open-source project. It is not affiliated with, endorsed by or sponsored by Google or Anthropic. Gemini, Google AI Pro, Flow and Antigravity are trademarks of Google LLC.

## License

[MIT](LICENSE)
