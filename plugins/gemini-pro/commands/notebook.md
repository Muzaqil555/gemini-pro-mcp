---
description: Build a Gemini Notebook from files or links, then ask it questions or make a Studio output
argument-hint: "<files or URLs> [question, or audio/video/slides/mind map/quiz]"
---

Work with a Gemini Notebook (formerly NotebookLM), using the notebook_* tools of
the gemini-pro MCP server:

$ARGUMENTS

1. Split the arguments:
   - sources: local file paths, web or YouTube links;
   - what the user wants: a question, or a Studio output (Audio Overview, Video
     Overview, Slide Deck, Mind Map, Report, Flashcards, Quiz, Infographic or Data
     Table).
2. If they named an existing notebook, find it with `notebook_list` and add any new
   sources with `notebook_add_sources`. Otherwise, call `notebook_create` with the
   sources.
3. Then do what they asked:
   - for a question, call `notebook_ask` and give the answer with its citations;
   - for a Studio output, call `notebook_studio` with a large `wait_seconds` (audio and
     video take minutes) and give the path of any downloaded file.
4. If no question or output was given, create the notebook, give its link, and stop.
