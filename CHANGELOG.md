# Changelog

## 0.1.8

- The Gemini CLI extension allows up to 15 minutes for startup and tool calls, matching the setup command. Its default five-second connection check could report a disconnected server while uvx downloaded dependencies on the first run.

## 0.1.7

- Added a first-run guide for seven clients and a release check that exercises the Claude plugin launcher over MCP. Antigravity setup can also register the server from an existing desktop configuration when the CLI is missing.

- `gemini-pro-mcp setup` now also detects and configures Cursor (`~/.cursor/mcp.json`), Claude Desktop (`claude_desktop_config.json`) and Windsurf (`~/.codeium/windsurf/mcp_config.json`).
- Added `gemini-pro-mcp auth` to save optional `JULES_API_KEY` and `GEMINI_API_KEY` entries to `~/.config/gemini-pro-mcp/.env` interactively with hidden input while keeping existing comments and keys (core Gemini, Deep Research, Flow and Notebook tools run on your Google AI Pro plan and need no API key).
- Registered six built-in MCP prompts (`gemini_review`, `gemini_research`, `second_opinion`, `jules_task`, `notebook_workflow`, `make_video`) so every MCP client gets ready-made workflows, and added `/gemini-pro:video` and `/gemini-pro:second-opinion` to the Claude Code plugin.
- Video stitching, media saves and Notebook downloads keep separate filenames when clients request the same output concurrently. A failed video download or disk write reports the interaction ID for retry.
- Browser calls share Chrome startup. Flow advances its release notes when they block a project, and shot planning ignores numeric arrays before the scene descriptions.
- Setup supports pip-only environments, retains backups on repeated identical runs and reports partial registration failures. Jules follows continuation tokens for long sessions and repository lists.

- The `.env` file (`~/.config/gemini-pro-mcp/.env`) is read correctly when Windows Notepad saved it with a byte order mark. Before, the first key's name started with an invisible character, so a `GEMINI_API_KEY` on the first line was never found. Lines copied from other projects also work now: an `export ` prefix, a `# comment` after the value, and only matching quotes around a value are removed.
- A setting that should be a number but isn't, such as `GEMINI_PRO_AGY_TIMEOUT=10m`, no longer stops the server from starting. The server uses the default and says so on stderr, which MCP clients keep in their logs.
- `gemini_ask` no longer reads a whole file passed in `paths` to decide whether its text fits in the prompt. A large file, such as a video, used to be loaded into memory in full before it was listed by path; now at most about 80 KB of each file is read.
- When the MCP client cancels a `gemini_*` tool call, agy and the processes it started are stopped. They used to keep running for up to the 10-minute timeout, so `gemini_code` could go on editing files after the user cancelled.
- A `GEMINI_PRO_CHROME` that is not a program is reported as such. `doctor` used to show it as `[ok]` Chrome, and the browser tools then failed with a `FileNotFoundError` and a request to report a changed page. It may also be a program name on PATH, such as `chromium`.
- `setup` keeps the comments above a Codex `config.toml` table that comes after this server's tables. Running setup again used to delete them along with the server's old settings.
- `gemini-pro-mcp doctor --flow` reports a Flow error that has no message (such as a bare `TimeoutError`) by its type. It used to crash with `IndexError: list index out of range`.
- Browser tools put `hl=en` in the query string of a link with a `#` fragment, such as a Colab `#scrollTo=` link. It used to land inside the fragment, so the page did not switch to English. A parameter that merely ends in `hl=` (`shl=1`) no longer stops it either.
- `file_name` in `video_generate`, `video_edit` and `image_generate` keeps dots that are not a media extension: `demo-v1.2` was saved as `demo-v1.mp4`, and now as `demo-v1.2.mp4`.
- Videos that the Gemini API returns as a file link (1080p and 4k) are found again before download. The file name was read from the link together with its `:download` suffix, so the readiness check asked for a file that does not exist.
- The browser tools start Chrome in a worker thread. While Chrome was starting (up to 10 seconds), the server used to stop answering every other tool call.
- `flow_make_video` finds the clips of an earlier run again when `file_name` contains `[`, `]`, `*` or `?`. The name was used as a glob pattern, so a resumed job did not see the clips it had already saved and generated them again, spending Flow credits a second time.
- `notebook_create` and `notebook_add_sources` check that every file in `files` exists before opening Chrome. `notebook_create` used to make a new, empty notebook first and then fail on the missing file, leaving the empty notebook behind.
- `gemini_app` says which files in `files` don't exist before opening Chrome. A wrong path used to fail inside the browser, after the model and tool pickers had been clicked, with an error asking the user to report a changed page.
- `gemini_app_result` only accepts Gemini app chat URLs. A URL of another supported site (Docs, Drive, Flow...) was opened in the Gemini tab, where no answer can be found, so the tool waited the full `wait_seconds` and then reported "still working" with an empty answer.
- `setup` accepts a Gemini CLI `settings.json` with `//` or `/* */` comments, which the Gemini CLI allows. It used to report the file as invalid JSON and skip the Gemini CLI. The comments are not kept in the rewritten file; the old file is saved as `settings.json.bak`.
- `gemini-pro-mcp setup` handles a Gemini CLI `settings.json` that is valid JSON but not the expected shape. `"mcpServers": null` is treated as empty; a top-level array or a non-object `mcpServers` marks the Gemini CLI as failed with a message, and setup carries on with the other clients. It used to stop with a `TypeError` or `AttributeError`.
- `google_act` errors for a stale element number say to call `google_page` again. They named `flow_page`, which became `google_page` and no longer exists, so the model was sent to a tool it could not find.
- `google_page` checks its `site` argument against the supported Google AI sites, as it already did for `url`. Called with only `site`, it opened `https://<site>/` in the signed-in Chrome profile for any host, including sign-in pages and sites outside Google.
- `image_generate` returns "No image came back" with Gemini's own text when the model answers without an image, for example when it declines a prompt. Before, the tool failed with `AttributeError: 'NoneType' object has no attribute 'mime_type'`.
- `jules_status` follows the activity list's `nextPageToken`. It read only the first page of 100 activities, so for a long session the "recent activity" it showed stopped at activity 100 and never included the latest question, progress or completion.
- The `jules_*` tools return "Error: Jules API <code>: ..." when the API sends an error body that is not a JSON object, such as an error wrapped in a list. They used to fail with `AttributeError: 'list' object has no attribute 'get'`.
- The `jules_*` tools answer "Error: Could not reach the Jules API (...)" when the computer is offline or a proxy or timeout stops the request. They used to fail with a raw `httpx` exception instead of a tool answer.
- `jules_status`, `jules_approve_plan` and `jules_message` accept a Jules web link with a trailing slash, a query string or a `#` fragment. Before, the session id came out empty or with `?...` attached, and the call went to the wrong API path.
- `jules_sources` lists every connected repository. It read only the first page of the Jules API (100 repositories), so with more connected, `jules_start` couldn't be pointed at the rest by name from the list.
- `jules_status(activities=0)` shows only the state and pull request. It used to list every activity, because `[-0:]` is the whole list.
- `notebook_studio` no longer overwrites an earlier Audio or Video Overview that Notebook downloads under the same file name. The new file gets a `-2`, `-3`... suffix, as `flow_*` and the media tools already do.
- `notebook_ask` says when `wait_seconds` ran out while the notebook was still writing its answer. It used to return the cut-off text as if it were the whole answer.
- `flow_act` and `google_act` with `action='replace'` replace the text of a rich text box on macOS too. They pressed Control+A to select it, which on macOS only moves the cursor, so the new text was added to the old one.
- `gemini-pro-mcp setup` carries on when a client's own CLI (`claude mcp add`, `agy mcp add`) hangs for two minutes or cannot start. It marks that client as failed and prints the command to run by hand, where it used to stop with a `TimeoutExpired` traceback before the other clients.
- `flow_make_video` keeps Gemini's shot list when the answer has brackets outside the JSON array, such as "[0-8s]" or a closing note like "Each shot is [8 s]". The shot list was read from the first `[` to the last `]`, which failed to parse, and the video quietly fell back to the same prompt with "(part 1 of 3, continuing)" for every clip.
- `video_stitch` reports an error when one of the clips can't be read (for example a truncated download). ffmpeg stopped at that clip but exited successfully, so the tool said "Saved" for a video that was missing every clip from that one on. A failed join no longer leaves a partial file in the output folder.
- `video_stitch` joins clips whose path contains an apostrophe, such as `Muzaqil's clips/a.mp4`. ffmpeg's file list didn't escape the quote, so ffmpeg could not open the clip.
- When the MCP client cancels `video_stitch`, ffmpeg is stopped. It used to keep re-encoding in the background and could leave a half-written video at the output path.
- `video_check` saves the video under the `file_name` given to `video_generate` or `video_edit` when an earlier download of it failed. The name used to be dropped before the download, so a retry saved the file under a default date-and-prompt name.
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
