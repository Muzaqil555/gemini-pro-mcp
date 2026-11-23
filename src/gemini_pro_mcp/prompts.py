"""Reusable MCP prompts so every client (Claude, Codex, Cursor, Windsurf,
Antigravity, Gemini CLI) gets the same ready-made workflows, not only the
Claude Code plugin."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer


def register(mcp: MCPServer) -> None:
    @mcp.prompt(
        name="gemini_review",
        description=(
            "Get Gemini's independent review of your current git changes, "
            "then verify each point against the code."
        ),
    )
    def gemini_review(focus: str = "") -> str:
        extra = f"\n\nFocus or base from the user: {focus}" if focus.strip() else ""
        return (
            "Get an independent review of the current changes from Gemini through `gemini_ask` "
            "(runs on the user's Google AI Pro plan, no API cost).\n\n"
            "1. Run `git status` and `git diff` (staged and unstaged). If the user named a "
            "branch or commit, diff against it instead. If there is nothing to review, say so.\n"
            "2. Save the diff to a temporary file and call `gemini_ask` with `paths` containing "
            "that diff plus the changed files (split into multiple calls if total text exceeds "
            "~20,000 characters). Ask for bugs, edge cases, security issues and missing tests "
            "tied to file and line numbers, ranked by severity.\n"
            "3. Verify every point Gemini raises against the actual code. Keep only confirmed "
            "issues and note which points you dropped and why.\n"
            "4. Report confirmed findings most severe first. Do not edit code unless asked." + extra
        )

    @mcp.prompt(
        name="gemini_research",
        description="Run live web research with Gemini and Google Search, returning sourced facts.",
    )
    def gemini_research(topic: str) -> str:
        return (
            f"Research this topic on the live web using `gemini_research`: {topic}\n\n"
            "1. Call `gemini_research` with a clear question and ask for dates, version numbers "
            "and source URLs.\n"
            "2. Summarize the verified answer clearly with the sources Gemini cited.\n"
            "3. Note anything that appears uncertain or needs a follow-up check."
        )

    @mcp.prompt(
        name="second_opinion",
        description=(
            "Compare your own analysis with Gemini's independent second opinion "
            "on a design, bug or architecture choice."
        ),
    )
    def second_opinion(question: str, files: str = "") -> str:
        file_note = (
            f"\nPass these files in `paths`: {files}"
            if files.strip()
            else "\nInclude any relevant local files in `paths`."
        )
        return (
            f"Get a second opinion from Gemini on: {question}{file_note}\n\n"
            "1. First form your own concise view based on the local code or context.\n"
            "2. Call `gemini_ask` without biasing Gemini toward your answer — ask for trade-offs, "
            "risks and concrete recommendations.\n"
            "3. Present both perspectives side by side: where you and Gemini agree, where you "
            "disagree (with evidence from the code), and a clear final recommendation."
        )

    @mcp.prompt(
        name="jules_task",
        description="Hand a GitHub repository coding task to Jules with plan approval.",
    )
    def jules_task(task: str, repo: str = "") -> str:
        repo_hint = f"Target repository: {repo}\n" if repo.strip() else ""
        return (
            f"Delegate this coding task to Jules:\n{repo_hint}Task: {task}\n\n"
            "1. Call `jules_sources` to find the exact connected repository name.\n"
            "2. Confirm the repository, branch and scope with the user before calling "
            "`jules_start` (Jules can push a branch and open a PR).\n"
            "3. Start with `require_plan_approval=True` for non-trivial work, return the "
            "session link immediately instead of polling in a loop, and use `jules_status` + "
            "`jules_approve_plan` once the user approves the plan."
        )

    @mcp.prompt(
        name="notebook_workflow",
        description=(
            "Build a Gemini Notebook from files or links, "
            "then ask grounded questions or make a Studio output."
        ),
    )
    def notebook_workflow(sources: str, goal: str = "") -> str:
        goal_line = f"Goal: {goal}\n" if goal.strip() else ""
        return (
            f"Work with a Gemini Notebook using `notebook_*` tools.\n"
            f"Sources: {sources}\n{goal_line}\n"
            "1. If the user named an existing notebook, find it with `notebook_list` and call "
            "`notebook_add_sources`; otherwise call `notebook_create` with the sources.\n"
            "2. If the user asked a question, call `notebook_ask` and return the grounded answer "
            "with citations. If they asked for a Studio output (Audio Overview, Video Overview, "
            "Slide Deck, Mind Map, Report, Flashcards, Quiz, Infographic or Data Table), call "
            "`notebook_studio` with a generous `wait_seconds` and report the downloaded path.\n"
            "3. If `notebook_*` tools are missing, tell the user to run "
            "`uvx gemini-pro-mcp setup --browser` and "
            '`uvx --from "gemini-pro-mcp[flow]" gemini-pro-mcp flow-login`.'
        )

    @mcp.prompt(
        name="make_video",
        description=(
            "Plan and create a video using Google Flow credits (any length) "
            "or the Gemini API (8s), and stitch clips."
        ),
    )
    def make_video(idea: str, duration: str = "8s") -> str:
        return (
            f"Create a video for this idea: {idea} (target duration: {duration}).\n\n"
            "1. Choose the right path and confirm cost/credits with the user first:\n"
            "   - **Google Flow (`flow_make_video`)**: uses monthly AI Pro Flow credits, supports "
            "any length (multi-clip automatically stitched). Requires browser tools enabled.\n"
            "   - **Gemini API (`video_generate` / `video_edit`)**: paid per use via "
            "`GEMINI_API_KEY`, single clips up to 8s (combine multiple with free `video_stitch`).\n"
            "2. Confirm aspect ratio, resolution, duration and cost/credits before generating.\n"
            "3. Never retry a paid generation blindly; if a download fails, retry with "
            "`video_check` using the returned interaction id.\n"
            "4. Report the saved output file path and cost/credits spent."
        )
