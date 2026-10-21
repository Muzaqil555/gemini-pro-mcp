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
        """List the GitHub repositories connected to the user's Jules account. Free.

        Returns:
            Source names to pass as `repo` to jules_start (e.g. "github/owner/repo").
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
        """Give Jules (Google's coding agent, Pro limits) a task on a GitHub repo.
        It works in the cloud, asynchronously; follow it with jules_status.

        Args:
            prompt: The task, with acceptance criteria.
            repo: "github/owner/repo" from jules_sources; omit for a repo-less session.
            branch: Starting branch.
            title: Session title.
            create_pr: Let Jules open a pull request automatically when done.
            require_plan_approval: Wait for jules_approve_plan before coding.

        Returns:
            The session id and its web link.
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
        """State of a Jules session: latest activities (plan, progress, completion)
        and any pull request it opened. Free.

        Args:
            session: Session id from jules_start or jules_sessions.
            activities: How many recent activities to show.

        Returns:
            State, recent activities and outputs (PR links).
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
        """List recent Jules sessions. Free.

        Args:
            limit: How many to list.

        Returns:
            One line per session: id, state and title.
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
        """Approve the plan of a Jules session that waits for approval.

        Args:
            session: Session id.

        Returns:
            Confirmation.
        """
        try:
            await call("POST", f"sessions/{session_id(session)}:approvePlan", {})
            return "Plan approved; Jules is working on it."
        except JulesError as e:
            return f"Error: {e}"

    @mcp.tool(annotations=write)
    async def jules_message(session: str, message: str) -> str:
        """Send Jules a message in a session (answer its question, give feedback).

        Args:
            session: Session id.
            message: The message.

        Returns:
            Confirmation; follow up with jules_status.
        """
        try:
            await call("POST", f"sessions/{session_id(session)}:sendMessage", {"prompt": message})
            return "Sent. Check jules_status for Jules' reply."
        except JulesError as e:
            return f"Error: {e}"
