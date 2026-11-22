---
description: Hand a task on a GitHub repository to Jules, Google's cloud coding agent
argument-hint: "<task>"
---

Start a Jules session for this task, using the jules_* tools of the gemini-pro MCP
server:

$ARGUMENTS

1. Call `jules_sources`. Pick the repository that matches this project's git
   remote. If none matches, or several could, ask the user which one.
2. Write the task as a prompt with acceptance criteria, for example "tests pass" or
   "endpoint returns 400 on bad input".
3. Before you start anything, show the user the repository, the branch (default
   `main`) and the prompt, and get a yes.
4. Call `jules_start` with `require_plan_approval=True`. Turn on `create_pr` only if the
   user wants a pull request.
5. Give the user the session link. Tell them they can ask you to check it later
   (`jules_status`) and to approve the plan (`jules_approve_plan`) once they have
   read it. Don't poll in a loop.

If the jules_* tools are not available yet because the gemini-pro server is still
connecting, tell the user it is starting up: the first start installs it, which takes
a minute or two. Ask them to run the command again shortly.
