# forge-scryfall-scrapper
Forge-friendly Scryfall image downloader with support for full sets, singles, tokens and audit-based workflows.

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

## Notes

This project is designed to be Forge-friendly and does not include any downloaded assets in the repository.
All image content is fetched dynamically from Scryfall and stored locally.

---

## License

This project is released under the MIT License.  
See the `LICENSE` file for details.

---
