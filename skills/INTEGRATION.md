# Vendored Skills → Where Their Patterns Live

The brief asked to pull four GitHub repos and integrate their patterns. Those repos
are **Claude Code skills / study docs**, not pip packages. Rather than vendoring the
whole repos, we keep only the **skill definitions** (the `SKILL.md` folders and their
supporting reference/data files) under `skills/`, and their *patterns* are implemented
in real code in the app. This file maps each pattern to its source and its
implementation.

## What's vendored (skills only)
- `skills/superpowers/` — 14 skills from `obra/superpowers` (`skills/` folder only).
- `skills/ecc/` — the skill catalog from `affaan-m/ECC` (`skills/` folder only).
- `skills/ui-ux-pro-max/` — 7 design skills from `nextlevelbuilder/ui-ux-pro-max-skill`
  (`.claude/skills/` folder only, incl. the flagship `ui-ux-pro-max` skill + its data).
- `skills/system-design-primer/` — README only (this repo is a study guide, not a
  Claude skill, so there is no `SKILL.md` to extract).

The repos' source code, CLIs, screenshots, images, tests and docs are intentionally
**not** vendored — only the skill content is kept.

| Source repo | What it actually is | Pattern applied | Implemented in |
|---|---|---|---|
| [`obra/superpowers`](https://github.com/obra/superpowers) | Claude Code skills (modular capability packs) | Modular, self-contained task "skills"; thin routers delegating to focused modules | `backend/app/skills/` (`roadmap.py`, `projects.py`, `resume.py`, `interview.py`, `lessons.py`); routers in `backend/app/routers/` stay thin |
| [`affaan-m/ECC`](https://github.com/affaan-m/ECC) | Agent-harness "OS" (npm/plugin), **not** a concurrency lib | "ECC-style concurrency control" → safe Redis distributed lock (SET NX PX + Lua compare-and-delete) with bounded backoff, making AI generation idempotent per user/task | `backend/app/concurrency.py`; used in `backend/app/skills/roadmap.py` |
| [`donnemartin/system-design-primer`](https://github.com/donnemartin/system-design-primer) | Study guide (docs/images) | Fault tolerance & scalability: exponential backoff + jitter retries, Redis token-bucket rate limiting, graceful degradation, explicit resource lifecycle | `backend/app/resilience.py`, `backend/app/redis_client.py` (degrade-if-down), `backend/main.py` (rate-limit middleware + lifespan) |
| [`nextlevelbuilder/ui-ux-pro-max-skill`](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | Claude Code design-intelligence skill | Consistent API response envelope + clear messaging; consistent UI states (loading/error/empty), accessible components, light/dark tokens | Backend: `backend/app/responses.py`. Frontend: `frontend/src/components/States.jsx`, `frontend/src/styles/index.css`, `frontend/src/api/client.js` |

## Notes
- Each `LICENSE` file is retained alongside its skills for attribution (the sources
  are MIT-licensed).
- To use any of these as a live Claude Code skill/plugin, install it via its own repo
  instructions (e.g. `/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill`).
