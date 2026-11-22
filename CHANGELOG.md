# Changelog

## Unreleased

- `video_edit` with `video_path` stops with an error when Google fails to process the uploaded video, or is still processing it after three minutes. It used to send the unusable file on to a paid generation request anyway.

## 0.1.6

- `gemini_ask`, `gemini_research` and `gemini_code` return as soon as Gemini's answer is in. After answering, agy can keep running for minutes while it stops the MCP servers in its config, and the tools waited for it, up to their 10-minute timeout, and then reported a timeout instead of the answer. When Gemini returns no text, the tools now say so instead of returning an empty answer, and include agy's own explanation.
- `gemini_research` came back empty whenever Gemini reached for a search tool from an MCP server in the user's agy config, or for a terminal command such as `curl`. Headless agy can't ask for those permissions, so it ended the turn. These agy runs now deny MCP tools and terminal commands (`--settings`), so Gemini uses agy's built-in web search. This also keeps `gemini_ask` and `gemini_research` read-only when the user's agy has MCP servers that send mail or spend credits.
- `gemini_ask` puts the text of the files in `paths` into the prompt: up to 20 000 characters per file, about 22 000 in all. Headless agy can't get approval to read files, and in tests it ignored a matching `read_file(...)` allow rule. So Gemini couldn't open the files, and the answer came back empty. Folders and bigger files are listed by path only.
- Known issue: with Antigravity CLI 1.5, `gemini_code` can't edit files. Headless agy can't get approval to read or write them. The tool now stops after about half a minute with agy's explanation, where it used to hang for 10 minutes. Use Jules (`jules_start`) for code changes until agy fixes this.
- `video_generate` and `video_edit` use `gemini-omni-1.2-flash`. Google shuts down `gemini-omni-1.1-flash` on 2026-12-03 and routes its requests to 1.2.
- The Claude Code plugin has a skill that tells Claude which tool fits a request, and four commands: `/gemini-pro:gemini-review`, `/gemini-pro:gemini-research`, `/gemini-pro:jules` and `/gemini-pro:notebook`.
- Sign-in and Flow page checks compare the page's host instead of searching the URL text.
- CI runs with a read-only `GITHUB_TOKEN`.
- `video_stitch` uses the `ffmpeg` on PATH when the bundled one (the `flow` extra) is not installed, as in the Claude Code plugin and the Gemini CLI extension.
- Plugin: the commands and the skill tell the user to try again while the server is still starting for the first time, and say how to add the browser tools, which the plugin's server leaves out.
- Installable as a Gemini CLI extension (`gemini extensions install https://github.com/Muzaqil555/gemini-pro-mcp`) and as a Claude Code plugin (`/plugin install gemini-pro --marketplace Muzaqil555/gemini-pro-mcp`).

## 0.1.5

- `setup` registers the PyPI package (`uvx gemini-pro-mcp`) instead of the GitHub URL, and the README installs from PyPI.
- A first run on Python 3.12+ no longer prints `SyntaxWarning` lines from the google-genai SDK.
- PyPI page: the description, keywords and links now match the README.

## 0.1.4

- Published on PyPI (`uvx gemini-pro-mcp`) and listed in the official MCP Registry as `io.github.Muzaqil555/gemini-pro-mcp`.
- 0.1.3 was a Glama-only build of 0.1.2 and has no GitHub release.

## 0.1.2

- Every tool description now says when to use the tool rather than a related one, what it costs or changes, the valid values of each parameter with an example, and what it returns: `gemini_research`, `gemini_code`, `gemini_agents`, `gemini_models`, `jules_sources`, `jules_start`, `video_generate`, `video_check` and `image_generate`.

## 0.1.1

- Clearer tool descriptions for `gemini_ask`, `video_stitch`, `google_pro_benefits` and the `jules_*` tools: when to use each one, what it costs and what it returns.
- `setup` and `doctor` commands, translations (Turkish, Russian, Azerbaijani), a comparison with other Gemini MCP servers, a Dockerfile, a Code of Conduct and a security policy.
- Dependabot and CodeQL code scanning.

## 0.1.0

- `gemini_ask`, `gemini_research` and `gemini_models` run Gemini through the Antigravity CLI on your Google AI Pro/Ultra plan, read-only and sandboxed.
- `video_generate`, `video_edit` and `video_check` use Gemini Omni Flash through the Gemini API.
- `image_generate` creates and edits images with Nano Banana 2.1, 2 Lite and Pro.
- Experimental Flow tools: `flow_generate`, `flow_approve`, `flow_reject`, `flow_collect` and `flow_status`. They drive flow.google.com in your own signed-in Chrome profile (`flow-login`), and spending credits always takes a separate `flow_approve` call.
- `flow_make_video` and `flow_job` make a video of any length: Gemini writes a shot list, Flow generates each clip, and the clips are joined into one file.
- `video_stitch` joins clips locally with a bundled ffmpeg.
- `GEMINI_PRO_AUTO_APPROVE=1` is for users who pre-approve spending.
- Every Flow feature is now reachable: `flow_tools` and `flow_open_tool` open any Flow tool, and `flow_page` and `flow_act` read and operate any Flow page or tool frame, including clicks, typing, uploads and downloads.
- `flow_make_video` is more reliable: it saves its shot plan to `plan.json` and resumes from the clips already made. A failed clip is retried up to 3 times; Flow does not charge for failures.
- The whole Google AI Pro plan is now covered: `google_pro_benefits` (a catalog of what the plan includes and how to reach each part), `gemini_app` and `gemini_app_result` (the Gemini app: 4 Argon, Deep Research, images, Veo, music, Canvas, files), `google_ai_mode` (AI Mode in Search), and `google_page` / `google_act` (any Google AI site, like a person; these replace `flow_page` / `flow_act`).
- `GEMINI_PRO_ENABLE_BROWSER=1` enables all browser tools. Each site gets its own tab and lock, and Chrome no longer pauses background tabs.
- Gemini Notebook (formerly NotebookLM): `notebook_list`, `notebook_create`, `notebook_add_sources`, `notebook_ask`, `notebook_studio` (Audio and Video Overviews, slide decks, mind maps, reports, flashcards, quizzes, infographics, data tables).
- Antigravity: `gemini_code` lets Gemini edit a local folder (accept-edits mode, sandboxed terminal), and `gemini_agents` lists custom agents.
- Jules: `jules_sources`, `jules_start`, `jules_status`, `jules_sessions`, `jules_approve_plan` and `jules_message` use the official REST API (`JULES_API_KEY`).
- Fixed: concurrent browser connections reset Chrome's download handling and left 0-byte clips. The server now shares one connection, checks every download and falls back to the signed file URL.
- Fixed: when Flow queues a clip at busy times, `flow_make_video` now waits for the clip it already paid for instead of generating it again.
- Fixed: `flow_status` timed out after Flow put the Google account bar inside its plan badge. It now clicks the plan chip itself, and an unreadable balance shows as "unknown" instead of failing the check.
- Setup instructions for Codex, the Antigravity CLI and the Gemini CLI.
- `gemini-pro-mcp setup` adds the server to every MCP client it finds (Claude Code, Codex, Antigravity CLI, Gemini CLI). It uses each client's `mcp add` command where there is one, and otherwise edits the config file, keeping everything else in it and saving a backup. `--browser` and `--auto-approve` set the matching settings.
- `gemini-pro-mcp doctor` checks the Antigravity sign-in, the API keys, Chrome and the Flow profile, and says how to fix each problem it finds. With `--flow` it also opens Flow and reads the credits.
