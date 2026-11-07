# Changelog

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
