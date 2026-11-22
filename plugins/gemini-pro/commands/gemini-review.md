---
description: Get Gemini's second opinion on the current changes, then weigh it against the code
argument-hint: "[what to focus on, or a branch/commit to compare against]"
---

Get an independent review of the current changes from Gemini, through the
`gemini_ask` tool of the gemini-pro MCP server, which runs on the user's Google AI Pro plan.

Focus or base from the user: $ARGUMENTS

1. Collect the changes:
   - Run `git status` and `git diff` (staged and unstaged).
   - If the user named a branch or commit, diff against it instead.
   - If there is nothing to review, say so and stop.
2. Write the diff to a temporary file. Call `gemini_ask` with:
   - `paths`: that file, plus the changed files themselves, so Gemini sees the context.
     The server puts the text of each file up to 20 000 characters into the prompt,
     about 22 000 characters in all. If the diff is bigger, review it in parts, one call
     per group of files;
   - `prompt`: ask for correctness bugs, edge cases, security problems and missing tests,
     each tied to a file and line and ranked by severity. Include the user's focus, if
     they gave one.
3. Check every point Gemini raises against the code yourself. Keep only the ones
   that hold up, and say which of Gemini's points you dropped and why.
4. Report the confirmed findings, most severe first. Change no code unless the user
   asks.

If `gemini_ask` is not available yet because the gemini-pro server is still
connecting, tell the user it is starting up: the first start installs it, which takes
a minute or two. Ask them to run the command again shortly. Don't present a review of
your own as Gemini's.
