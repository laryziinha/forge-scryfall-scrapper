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

**Goal:** Improve long-term maintainability, extensibility and alignment with
Forge image expectations.

This phase focuses on internal structure and advanced tooling, not on changing
the current user workflow.

---

### Phase 02.A — Modular architecture

**Goal:** Turn the project into a clean Python package with a stable internal API.

Planned:
- Separate **core logic** from **runners** (CLI entrypoints)
- Introduce a real package layout (e.g., `forge_scrapper/` instead of only `src/`)
- Centralize shared utilities:
  - logging
  - filename rules
  - layout handling
  - download routines
- Define clear entrypoints:
  - `python -m forge_scrapper`
  - optional console command (future)

Possible structure:
- `forge_scrapper/core/` (API clients, download engine, layout handlers)
- `forge_scrapper/cli/` (menus, prompts, user flow)
- `forge_scrapper/utils/` (paths, naming, logging)
- `tests/` (light tests for critical rules)

Success criteria:
- Same capabilities as v1.x, but cleaner and easier to maintain
- Adding new download modes becomes straightforward

---

### Phase 02.B — Forge Snapshot Crosscheck & Auto-Rename

**Goal:** Improve consistency between Forge image expectations and locally
downloaded Scryfall images.

Forge may reference card images using naming rules that vary depending on
snapshot version, layout type and product (e.g. promos, SLD, alternate prints).
This effort aims to detect and optionally resolve mismatches safely.

Planned investigations:
- Analyze how Forge Daily Snapshots reference card images
- Identify filename resolution patterns across layouts:
  - normal
  - split / aftermath
  - flip
  - double-faced cards (DFC)
- Map common divergence cases:
  - oracle name vs printed name vs flavor name
  - renamed cards (SLD and special products)
  - multiple prints sharing the same artwork

Planned tooling:
- Crosscheck mode or script comparing:
  - local `Cards/<SET>/` folders
  - Forge expectations (audit output / indices)
- Detect missing, duplicated or mismatched filenames
- Generate a **rename plan** instead of modifying files directly

Safety-first design:
- Dry-run mode by default
- Explicit logs for all detected mismatches
- No automatic overwrites
- Manual review encouraged before applying changes

Potential deliverables:
- `forge_crosscheck.py` (dry-run by default)
- `rename_plan.json`
- `apply_rename_plan.py`
- Logs: `crosscheck_report_<date>.txt`

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