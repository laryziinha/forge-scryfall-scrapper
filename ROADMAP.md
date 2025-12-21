# Roadmap

This roadmap describes the next planned steps for **forge-scryfall-scrapper**.
Priorities may change based on community feedback and real-world usage.

---

## Guiding principles

- Keep the tool **Forge-friendly** and practical.
- Avoid shipping downloaded assets in the repository.
- Prefer **safe defaults** and clear CLI behavior.
- Focus on reliability first, then UX, then architecture.

---

## v1.x — Stabilization & quality improvements

### v1.2.0 — Refactor & cleanup (no behavior changes)
**Goal:** Improve maintainability without changing the current user workflow.

Planned:
- Internal refactors (smaller functions, less duplication)
- Cleanup (unused imports, legacy code paths, minor formatting consistency)
- Add docstrings / comments to core routines:
  - set download
  - single/prints download
  - token download via Forge `Audit.txt`
  - audit-based card download (non-token)
  - duplicate naming / enumeration
  - layout handling (DFC / split / flip / adventure)

Success criteria:
- Same CLI flow and outputs
- No functional regressions
- Easier to extend for Phase 02

### v1.3.0 (optional) — UX polish & small improvements
**Goal:** Small user-facing improvements that do not require architecture changes.

Ideas (based on feedback):
- Better error messages and retry behavior (network / rate-limits)
- Clearer prompts and confirmations
- Optional “dry-run” mode (show what would be downloaded)
- Optional “overwrite / skip / clean” presets
- Simple config file support (e.g., default output folder)

---

## Phase 02 — Modular architecture (likely v2.0.0)

**Goal:** Turn the project into a clean Python package with a stable internal API.

Planned:
- Separate **core logic** from **runners** (CLI entrypoints)
- Introduce a real package layout (e.g., `forge_scrapper/` instead of only `src/`)
- Centralize shared utilities (logging, filename rules, layout handling, downloads)
- Clear entrypoints:
  - `python -m forge_scrapper`
  - or a console command (future)

Possible structure:
- `forge_scrapper/core/` (API clients, download engine, layout handlers)
- `forge_scrapper/cli/` (menus, prompts, user flow)
- `forge_scrapper/utils/` (paths, naming, logging)
- `tests/` (light tests for critical rules)

Success criteria:
- Same capabilities as v1.1, but cleaner and easier to maintain
- Adding new modes becomes straightforward

---

## Phase 03 — Friendly UI (desktop / local web)

**Goal:** Provide a more approachable interface while keeping local execution.

Options (community-driven):
- NiceGUI local app
- Simple local web UI (Flask/FastAPI + minimal frontend)
- Desktop wrapper (only if it adds real value)

Notes:
- “Run online” is not the primary target, because it would require hosting, storage, quotas,
  and would raise concerns about distributing assets. A **local UI** is the realistic path.

Success criteria:
- Easy to run locally
- Clear progress and logs
- Same output folders and rules as CLI

---

## Ongoing maintenance (continuous)

- Bug fixes and compatibility improvements
- Scryfall API changes handling
- Forge user feedback triage
- Documentation updates