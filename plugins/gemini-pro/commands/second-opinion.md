---
description: Compare Claude's view with Gemini's independent second opinion on a design, architecture or bug
argument-hint: "<question or decision> [file paths]"
---

Get an independent second opinion from Gemini through `gemini_ask` (runs on the user's
Google AI Pro plan, no API cost) and compare both perspectives:

$ARGUMENTS

1. Read the relevant local files yourself and form your own concise position first.
2. Call `gemini_ask` with:
   - `paths`: the exact files involved (up to 20 000 characters per file, ~22 000 total;
     split across calls if larger);
   - `prompt`: state the user's question neutrally — do NOT steer Gemini toward your own
     conclusion. Ask for concrete trade-offs, hidden failure modes and a recommendation.
3. Verify Gemini's claims against the actual code before repeating them.
4. Present a structured comparison:
   - **Where we agree**
   - **Where we disagree** (with evidence from the code)
   - **Recommended next step**
5. Keep the returned `conversation_id` so the user can follow up in the same thread.

If `gemini_ask` is not available yet because the gemini-pro server is still connecting,
tell the user it is starting up (the first start installs it and takes a minute or two)
and ask them to run the command again shortly. Don't present your own opinion as Gemini's.
