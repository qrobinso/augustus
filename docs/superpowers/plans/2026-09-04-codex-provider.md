# Codex provider implementation plan
Spec: docs/superpowers/specs/2026-09-04-codex-provider-design.md

Global constraints: preserve prior story-memory work; use official App Server; never read the user's auth files or .env secrets; no live paid model calls; keep OpenRouter default; no automatic fallback billing; isolate auth/config; disable model tools; preserve existing provider contract.

- [x] Task 1: Implement Codex App Server transport/provider in backend/app/services/llm/codex.py with fake-transport tests. Export get_codex_service() (status, start_login, cancel_login, logout, models, generate, close). Service status returns available, connected, plan_type, login_pending, error; start_login returns login_id, verification_url, user_code; models returns list of id/name. CodexProvider implements LLMProvider and accepts optional model. Config fields consumed: codex_cli_path, codex_home, codex_timeout_seconds, codex_model. Inspect actual CLI protocol schemas and make isolated unauthenticated handshake smoke test.
- [x] Task 2: Wire llm_provider and codex_model into config/settings, provider factory and writer; research capability fallback. Add /api/settings/codex/status GET, /login POST, /login DELETE, /logout POST, /models GET; shutdown cleanup; backend tests and deployment docs.
- [x] Task 3: Add provider selector and Codex connection/model panel in Settings, API types/helpers, meaningful UI state tests and production build. Keep existing OpenRouter configuration and audio settings.
- [x] Task 4: Review integrated diff, fix findings, run backend tests, frontend tests/build and diff checks. Leave changes uncommitted for review.

Validation: 141 backend tests and 20 frontend tests pass; production frontend build and diff checks pass. Official CLI 0.146.0 initialization/account-read tested with isolated unauthenticated state. Final independent review and scoped origin fix review have no outstanding findings. No real subscription login or model request was made; browser visual QA was unavailable.

Implementation rulings: app configuration uses AUGUSTUS_CODEX_HOME to avoid inheriting desktop Codex credentials. External execution tools are disabled; model-specific harmless CLI utilities are not claimed absent. Work remains uncommitted on feature/story-memory alongside the prior reviewed feature.
