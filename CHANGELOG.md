# Changelog

## [1.1.4-beta.1] - 2025-12-23
Changed
- Windows: hardened handling of reserved device names for set folders (CON, PRN, AUX, NUL, COM1–COM9, LPT1–LPT9).
- Reserved set codes are now processed through a Windows-safe naming layer when required.

Fixed
- Fixed a Windows compatibility issue where reserved set codes could cause invalid directory errors during downloads.
- Set downloads now use a safe temporary folder when required and automatically move files to the correct final set folder after completion.
- Prevented duplicate folder creation (e.g. `_SET` + `SET`) across Specific Set, ALL Sets, and Sets.txt batch download flows.

Notes
- This is a pre-release focused on validating Windows folder handling in real user environments.

## [1.1.3] - 2025-12-22
Added
- New experimental option: Rev Set Print Name (Option 7).
- Allows downloading card images using the printed card name as shown on the card.

Changed
- Improved Downloader menu organization for better clarity and navigation.
- Clearer separation between set downloads, single-card tools, and experimental features.
- More guided and readable selection flow across menus.
- Deprecated and removed the standalone Downloader_SetOnly.py (set-only flow is now integrated into Downloader.py).

Notes
- The Rev Set Print Name option is intended for special cases where the printed card name
    differs from the original card name used by Scryfall.
- This commonly affects Secret Lair, Universes Beyond (crossovers), promos, and special
    reskins (e.g., Ecto-1 being a printed-name version of Unlicensed Hearse).

## [1.1.2] - 2025-12-22
### Added
- Robust HTTP wrappers with retry/backoff for Scryfall JSON endpoints and image downloads.
- Batch safety for ALL SETs: continue on set failure + per-set pause + batch_errors.log.

### Changed
- Increased default RATE_SLEEP for stability (reduces WinError 10054 during long runs).
- get_all_sets() and get_set_meta() now use the JSON wrapper to avoid hard crashes.
- Search pagination now uses wrapper (more resilient).

### Fixed
- Prevented ALL SETs batch from dying on transient network failures.
- Improved error logging for HTTP status vs generic exceptions.

## [1.1.1] - 2025-12-21

### Fixed
- Windows: fixed ALL SETs crash (WinError 267) when creating certain set folders (e.g., `CON` / Conflux).
  The downloader now uses a Windows-safe folder name for reserved device names.

### Notes
- This is a filesystem naming fix only. Scryfall queries and card logic are unchanged.
- Recommended update for anyone running ALL SETs on Windows.
- Affected folders may be prefixed with `_` on Windows (e.g. `_CON`).

## [1.1.0] - 2025-12-21

### Added
- Modular project structure under `src/`
- Main interactive downloader (`Downloader.py`) acting as the central entry point
- Set-only downloader supporting full set downloads (`Downloader_SetOnly.py`)
- Single card and print downloader (`SingleCard.py`)
- Token downloader based on Forge `Audit.txt` (`DToken.py`)
- Audit-based card image downloader for non-token cards (`AuditDownloader.py`)
- Support for split, flip, adventure and double-faced card layouts
- Printed-name–first logic when available (flavor / printed name priority)
- Automatic duplicate handling with enumerated filenames
- Image rotation handling for flip and horizontal layouts
- Colored CLI interface with progress bars
- Robust `.gitignore` to exclude generated assets and runtime files
- Project documentation (`README.md`)
- Dependency definition via `requirements.txt`
- MIT License

### Changed
- Project evolved from a single-purpose set downloader into a modular Forge-friendly toolset
- Improved internal organization to support future modular expansion (Phase 02)

### Notes
- This release represents the first public, structured version of the project
- All downloaded assets remain local and are intentionally excluded from version control