---
description: Create a video with Google Flow credits (any length) or the Gemini API, and join clips locally
argument-hint: "<video idea> [duration, aspect ratio, or 'flow'/'api']"
---

Create a video using the gemini-pro MCP server:

$ARGUMENTS

1. Decide the right tool and settle the parameters with the user before spending anything:
   - **Google Flow (`flow_make_video`)**: uses the user's monthly Google AI Pro Flow
     credits and handles any length (multi-clip, stitched automatically into one `.mp4`).
     Requires the browser tools (`flow_*`).
   - **Gemini API (`video_generate` / `video_edit`)**: billed per use via
     `GEMINI_API_KEY`, up to 8 seconds per clip. Multiple clips can be joined locally
     for free with `video_stitch`.
2. Confirm the prompt, duration, aspect ratio and rough credit/API cost with the user
   before calling a paid or credit-spending tool (unless `GEMINI_PRO_AUTO_APPROVE=1`).
3. Never blindly retry a paid generation: if saving or downloading fails, use
   `video_check` with the returned interaction ID.
4. For `flow_make_video`, poll progress with `flow_job` until complete.
5. Report the final saved file path and cost or credits used.

If the video/flow tools are not available yet because the gemini-pro server is still
connecting, tell the user it is starting up and ask them to try again shortly.

If `flow_make_video` is missing, the browser tools are not enabled yet. Tell the user
to run these once, sign in to Google in the window that opens, and restart Claude Code:

    uvx gemini-pro-mcp setup --client claude --browser
    uvx --from "gemini-pro-mcp[flow]" gemini-pro-mcp flow-login
