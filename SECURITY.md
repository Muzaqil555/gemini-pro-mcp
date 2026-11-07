# Security Policy

## Supported versions

Only the latest release and the `main` branch get security fixes.

## Reporting a vulnerability

Please report security issues privately, not in a public issue:

1. Open the repository's **Security** tab and choose **Report a vulnerability** (GitHub private vulnerability reporting), or
2. email mhesenli7@std.beu.edu.az with "gemini-pro-mcp security" in the subject.

Include what you found, how to reproduce it and what an attacker could do. You will get a reply within 7 days, and a fix or a plan within 30 days for confirmed issues. Reporters are credited in the release notes unless they prefer otherwise.

## Scope

Especially relevant here:

- anything that could expose API keys, Google cookies or the signed-in Chrome profile;
- a way to make the browser tools act on sites outside the allowed list in `google_web.py`, or on sign-in, payment or account pages;
- a way to make a paid tool spend money or Flow credits without the confirmation described in the README.
