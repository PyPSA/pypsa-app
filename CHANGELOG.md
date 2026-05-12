# Changelog

All notable changes to this fork are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **LLM chat MVP (read-only).** `POST /api/v1/chat` gated by `CHAT_ENABLED`, configured via `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` / `LLM_API_BASE`. Tool-use loop over any OpenAI-compatible provider via [LiteLLM](https://github.com/BerriAI/litellm); soft-stops at `LLM_MAX_TOOL_ITERATIONS` with `truncated: true`. Three read-only tools: `list_networks`, `get_network_detail`, `get_network_statistics`.
- **Backend.** `chat_enabled` on `GET /api/v1/version`; sort/order on `GET /api/v1/networks`; JSON 404 for unmatched `/api/v1/*`; Alembic advisory lock; `fom` added to statistics allowlist.
- **Chat UI.** SvelteKit chat panel (FAB → modal) with custom renderers for network lists, cards, statistics, JSON, and charts, built on a subset of [AI Elements](https://github.com/vercel/ai/tree/main/packages/ai-elements).

([#1](https://github.com/open-energy-transition/pypsa-app/issues/1), [#3](https://github.com/open-energy-transition/pypsa-app/issues/3), [#4](https://github.com/open-energy-transition/pypsa-app/issues/4), [#6](https://github.com/open-energy-transition/pypsa-app/issues/6))

[Unreleased]: https://github.com/open-energy-transition/pypsa-app/compare/v0.0.1...HEAD
