# Codex subscription provider

Add Codex alongside OpenRouter for all text generation. Keep OpenRouter as the default and preserve both providers' settings when switching. Codex uses the official local Codex App Server and its managed ChatGPT device sign-in; no extracted tokens or unofficial endpoints. Augustus owns a private AUGUSTUS_CODEX_HOME under backend/data/codex, separate from the user's Codex login/config. Settings shows connection state, a device login link/code, disconnect, and a model selector sourced from Codex. Tokens never enter the browser or application logs.

Run the subprocess over stdio only with controlled configuration, no inherited API billing credentials, no model-visible filesystem/shell/MCP/app tools, ephemeral independent requests, bounded timeouts and cancellation cleanup. News is untrusted input. Fail clearly on unavailable CLI, expired login, quota exhaustion or model failure; never silently charge OpenRouter/API billing. Match the existing LLMProvider interface and structured JSON formats. Provider selection applies to editor, researchers, writer and follow-up questions; Codex research uses the existing app search pipeline rather than the OpenRouter plugin. TTS remains separately configured.

Installation requires Codex CLI on the backend host. Device sign-in may need enabling in ChatGPT security settings. Deployment docs cover this and persistence. Authentication/account endpoints must not expose credentials and must enforce same-origin browser mutations in this local app. No real model generation or signing in on the user's behalf during implementation.

Sources: https://learn.chatgpt.com/docs/auth and https://learn.chatgpt.com/docs/app-server
