"""Jules, Google's coding agent, through its official REST API (v1alpha).

Google AI Pro raises Jules' task and concurrency limits. Jules works on GitHub
repositories connected in the Jules web app and can open pull requests. The API
key is created by the user at https://jules.google.com/settings and put in
JULES_API_KEY (never typed by this server).
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from .config import Settings, env_file

BASE = "https://jules.googleapis.com/v1alpha"


class JulesError(RuntimeError):
    pass


def key() -> str:
    value = os.environ.get("JULES_API_KEY")
    if not value:
        raise JulesError(
            "No Jules API key. Create one at https://jules.google.com/settings (API keys), "
            f"put JULES_API_KEY=... in {env_file()} and restart the server."
        )
    return value


async def call(method: str, path: str, body: dict | None = None, params: dict | None = None):
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.request(
            method,
            f"{BASE}/{path.lstrip('/')}",
            headers={"x-goog-api-key": key(), "Content-Type": "application/json"},
            json=body,
            params=params,
        )
    if response.status_code >= 400:
        try:
            message = response.json().get("error", {}).get("message", response.text)
        except ValueError:
            message = response.text
        raise JulesError(f"Jules API {response.status_code}: {message[:500]}")
    return response.json() if response.content else {}


def session_id(value: str) -> str:
    return value.rsplit("/", 1)[-1]


def describe_activity(activity: dict[str, Any]) -> str:
    kinds = [k for k in activity if k not in ("name", "id", "createTime", "originator")]
    kind = next((k for k in kinds if isinstance(activity[k], dict)), kinds[0] if kinds else "")
    detail = activity.get(kind) or {}
    text = ""
    if isinstance(detail, dict):
        for field in ("title", "description", "message", "progress", "plan"):
            value = detail.get(field)
            if isinstance(value, str) and value:
                text = value
                break
            if isinstance(value, dict) and value.get("steps"):
                text = "; ".join(s.get("title", "") for s in value["steps"])[:400]
                break
    return f"- {activity.get('createTime', '')[:19]} {kind}: {text[:400]}"


def register(mcp: MCPServer, settings: Settings) -> None:
    write = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
    read = ToolAnnotations(readOnlyHint=True, openWorldHint=True)

    @mcp.tool(annotations=read)
    async def jules_sources() -> str:
        """List the GitHub repositories the user has connected to Jules, Google's
        cloud coding agent. Read-only and free. Call it before jules_start to get
        the exact repo name; Jules can only work on repositories listed here.

        Returns:
            One source name per line, e.g. "github/owner/repo", to pass as `repo`
            to jules_start; or a note that no repository is connected yet, with the
            link where the user connects GitHub.
        """
        try:
            data = await call("GET", "sources", params={"pageSize": 100})
            sources = data.get("sources", [])
            return "\n".join(s.get("id", s.get("name", "")) for s in sources) or (
                "No repositories connected. Connect GitHub at https://jules.google.com."
            )
        except JulesError as e:
            return f"Error: {e}"

    @mcp.tool(annotations=write)
    async def jules_start(
        prompt: str,
        repo: str | None = None,
        branch: str = "main",
        title: str | None = None,
        create_pr: bool = False,
        require_plan_approval: bool = False,
    ) -> str:
        """Start a Jules session: Google's coding agent works on a task in one of
        the user's GitHub repositories, in the cloud and asynchronously, within the
        Google AI Pro plan's Jules limits (no extra cost). It can push a branch and
        open a pull request, so confirm the task with the user first.

        Then poll with jules_status, answer questions with jules_message, and
        approve the plan with jules_approve_plan if you asked for approval. For a
        change in a local folder use gemini_code instead.

        Args:
            prompt: The task with acceptance criteria, e.g. "Add input validation
                to the /signup endpoint and tests for it".
            repo: Repository from jules_sources, e.g. "github/owner/repo"; omit for
                a session without a repository.
            branch: Branch Jules starts from (default "main").
            title: Optional session title; Jules makes one up otherwise.
            create_pr: True lets Jules open a pull request automatically when done.
            require_plan_approval: True makes Jules wait for jules_approve_plan
                before it changes any code.

        Returns:
            The session id and its web link (https://jules.google.com/session/<id>),
            or an error such as an unknown repository.
        """
        try:
            body: dict[str, Any] = {"prompt": prompt}
            if title:
                body["title"] = title
            if repo:
                source = repo if repo.startswith("sources/") else f"sources/{repo}"
                body["sourceContext"] = {
                    "source": source,
                    "githubRepoContext": {"startingBranch": branch},
                }
            if create_pr:
                body["automationMode"] = "AUTO_CREATE_PR"
            if require_plan_approval:
                body["requirePlanApproval"] = True
            data = await call("POST", "sessions", body)
            sid = session_id(data.get("name", data.get("id", "")))
            return (
                f"Started Jules session {sid}: {data.get('title', '')}\n"
                f"Web: https://jules.google.com/session/{sid}\n"
                "Follow it with jules_status."
            )
        except JulesError as e:
            return f"Error: {e}"

    @mcp.tool(annotations=read)
    async def jules_status(session: str, activities: int = 15) -> str:
        """Check on a Jules session started with jules_start: its state, its most
        recent activities (plan, progress messages, questions, completion) and the
        pull request it opened, if any. Read-only and free; call it again to poll a
        session that is still working.

        Use jules_sessions to find a session id, jules_approve_plan when the state
        says it awaits plan approval, and jules_message to answer a question.

        Args:
            session: Session id from jules_start or jules_sessions, or its full
                "sessions/<id>" name or web link.
            activities: How many of the latest activities to show (default 15).

        Returns:
            The session title and state, any pull request links, and one line per
            recent activity with its time, kind and text.
        """
        try:
            sid = session_id(session)
            data = await call("GET", f"sessions/{sid}")
            acts = await call("GET", f"sessions/{sid}/activities", params={"pageSize": 100})
            lines = [
                f"Session {sid}: {data.get('title', '')}",
                f"State: {data.get('state', 'unknown')}",
            ]
            for output in data.get("outputs", []):
                pr = output.get("pullRequest")
                if pr:
                    lines.append(f"Pull request: {pr.get('url')} ({pr.get('title', '')})")
            items = acts.get("activities", [])[-activities:]
            if items:
                lines.append("Recent activity:")
                lines += [describe_activity(a) for a in items]
            return "\n".join(lines)
        except JulesError as e:
            return f"Error: {e}"

    @mcp.tool(annotations=read)
    async def jules_sessions(limit: int = 10) -> str:
        """List the user's most recent Jules sessions, newest first, to find a
        session id or see which tasks are still running. Read-only and free.

        Pass an id from the result to jules_status for details, to
        jules_approve_plan or to jules_message.

        Args:
            limit: How many sessions to list (default 10).

        Returns:
            One line per session: id, state (as Jules reports it, for example in
            progress, awaiting plan approval or completed) and title, or
            "No sessions yet."
        """
        try:
            data = await call("GET", "sessions", params={"pageSize": limit})
            rows = [
                f"{session_id(s.get('name', ''))}  {s.get('state', '')}  {s.get('title', '')}"
                for s in data.get("sessions", [])
            ]
            return "\n".join(rows) or "No sessions yet."
        except JulesError as e:
            return f"Error: {e}"

    @mcp.tool(annotations=write)
    async def jules_approve_plan(session: str) -> str:
        """Approve the plan Jules proposed, so it starts writing code. Only for a
        session started with jules_start(require_plan_approval=True) whose state is
        awaiting plan approval; read the plan with jules_status first and show it
        to the user. To change the plan instead, send feedback with jules_message.

        Args:
            session: Session id from jules_start or jules_sessions.

        Returns:
            A confirmation that Jules is working, or an error such as the session
            not waiting for approval. Follow progress with jules_status.
        """
        try:
            await call("POST", f"sessions/{session_id(session)}:approvePlan", {})
            return "Plan approved; Jules is working on it."
        except JulesError as e:
            return f"Error: {e}"

    @mcp.tool(annotations=write)
    async def jules_message(session: str, message: str) -> str:
        """Send a message to Jules inside an existing session: answer a question it
        asked, give feedback on its plan or code, or ask for a change. Jules
        replies asynchronously, so read the answer later with jules_status. To give
        Jules a new task, use jules_start instead.

        Args:
            session: Session id from jules_start or jules_sessions.
            message: What to tell Jules, in plain language.

        Returns:
            A confirmation that the message was sent, or an error.
        """
        try:
            await call("POST", f"sessions/{session_id(session)}:sendMessage", {"prompt": message})
            return "Sent. Check jules_status for Jules' reply."
        except JulesError as e:
            return f"Error: {e}"
