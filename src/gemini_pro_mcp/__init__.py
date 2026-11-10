"""Google AI Pro and the Gemini API as MCP tools."""

import warnings

# google-genai 3.x has docstrings with an invalid escape, so Python 3.12+ prints
# SyntaxWarning lines the first time it compiles the SDK. They look like an error
# on a new user's first run and are not ours to fix.
warnings.filterwarnings("ignore", category=SyntaxWarning)

__version__ = "0.1.5"
