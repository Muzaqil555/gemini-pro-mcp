# Privacy

gemini-pro-mcp is a program that runs on your own computer. Its author runs no server and receives no data from it.

## What the server collects

Nothing. It has no telemetry, no analytics and no crash reporting.

## What it sends, and where

The server sends data only when you call a tool, and only to the Google service behind that tool:

| Tool group | Where your prompt and files go |
|---|---|
| `gemini_*` | Gemini, through the Antigravity CLI signed in with your Google account |
| `jules_*` | The Jules API (`jules.googleapis.com`), with your Jules API key |
| `video_*`, `image_generate` | The Gemini API, with your Gemini API key |
| `flow_*`, `notebook_*`, `gemini_app`, `google_*` | The Google web app open in a Chrome profile on your computer that you signed in to yourself |

Files are sent only when you ask a tool to read or upload them. Google's terms and privacy policy apply to everything sent to Google.

## Credentials

- API keys are read from your environment or from `~/.config/gemini-pro-mcp/.env`. Each key is sent only to the Google API it belongs to.
- The server never sees, stores or types your Google password. You sign in yourself, in the Antigravity CLI and in the Chrome profile.

## What stays on your computer

Generated images, videos and reports, job plans and the Chrome profile used by the browser tools.

## Questions

Open an issue at https://github.com/Muzaqil555/gemini-pro-mcp/issues.
