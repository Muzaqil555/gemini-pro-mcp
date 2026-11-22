---
description: Research a question on the live web with Gemini and Google Search, with sources
argument-hint: "<question>"
---

Research this question with the `gemini_research` tool of the gemini-pro MCP server:

$ARGUMENTS

1. If the question is empty or too vague to search, ask the user one short question
   to narrow it. Otherwise, sharpen it with context from this conversation or project,
   such as versions, platform or language, and call `gemini_research`.
2. Give the answer in a few short paragraphs or a list, with the sources as links.
   Point out where sources disagree, and any source that looks stale.
3. Keep the returned `conversation_id`. If the user asks a follow-up, pass it to
   `gemini_ask`.
