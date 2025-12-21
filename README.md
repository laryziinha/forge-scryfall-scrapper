# forge-scryfall-scrapper
Forge-friendly Scryfall image downloader with support for full sets, singles, tokens and audit-based workflows.

---

## Screenshots

### Startup
Initial setup and base directory selection.
![Startup](screenshots/startup.png)

### Main menu
Interactive CLI menu providing access to all download modes.
![Main menu](screenshots/menu.png)

### Download progress
Real-time progress bar with speed, ETA and card count.
![Download progress](screenshots/progress.png)

### Completion summary
Detailed summary after completion, including counts and performance.
![Completed](screenshots/completed.png)

---

## Features

- Download full sets from Scryfall
- Download single cards and all available prints
- Token downloader using Forge `Audit.txt`
- Audit-based card image downloader (non-token cards)
- Handles split, flip, adventure and double-faced cards
- Colored CLI interface with progress bars

---

## Requirements

- Python 3.8 or higher
- Dependencies listed in `requirements.txt`

---

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/laryzinha/forge-scryfall-scrapper.git
cd forge-scryfall-scrapper
pip install -r requirements.txt
```

---

## Usage

Run the main entry point:

```bash
python src/Downloader.py
```

Follow the on-screen menu to download:

* Complete sets
* Individual cards or prints
* Tokens via Forge Audit
* Cards via Forge Audit (non-token)

---

## Output

All downloaded content (cards, tokens, audit files and logs) is stored locally and ignored by Git via `.gitignore`.

Typical folders created at runtime:

* `Cards/`
* `Singles/`
* `Tokens/`

---

## Project Structure

```text
forge-scryfall-scrapper/
├─ src/
│  ├─ Downloader.py
│  ├─ Downloader_SetOnly.py
│  ├─ DToken.py
│  ├─ SingleCard.py
│  ├─ AuditDownloader.py
│  └─ __init__.py
│
├─ .gitignore
├─ README.md
├─ requirements.txt
├─ LICENSE
└─ CHANGELOG.md
```

---

## About this project

This is a personal project developed to support local Forge installations with reliable,
Forge-friendly card and token image downloads.

The project was originally created for personal use and later published as an open repository
to share a practical, modular solution with other Forge users.

All card data and images are fetched dynamically and directly from the official
[Scryfall API](https://scryfall.com/docs/api).

This tool does **not** rely on Scryfall bulk JSON downloads and does **not** redistribute
any Scryfall data or assets. All downloaded content is stored locally on the user's machine
and excluded from version control via `.gitignore`.

---

## License

This project is released under the MIT License.  
See the `LICENSE` file for details.

---
