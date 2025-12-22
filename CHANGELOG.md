# Changelog

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