<p align="center">
  <img src="assets/scryfall_scrapper_logo.png" alt="Scryfall Scrapper logo" width="420">
</p>

<p align="center">
  <strong style="font-size: 2.3em;">Scryfall Scrapper</strong>
</p>


<p align="center">
Forge-friendly Scryfall image downloader for Magic: The Gathering
<p>

<p align="center">
Designed to handle real-world Forge naming issues, special layouts and audit-based workflows.
</p>

<br/>

---

<br/>

## 💜 Overview

This is a personal Python project designed to download and organize
Magic: The Gathering card and token images **for local Forge installations**,
using the public Scryfall API.

Scryfall Scrapper is a command-line tool that downloads high-quality card and token images
from Scryfall in a way that matches Forge’s naming and layout expectations.

It focuses on real-world Forge use cases, including special card layouts, multiple print variants,
Secret Lair products, and audit-based workflows, avoiding silent overwrites and unexpected file mismatches.


## 📸 Screenshots
Below are real screenshots from the interactive CLI, showing the main workflows.

### 🚀 Startup
Initial setup and base directory selection.
![Startup](screenshots/startup.png)

### 🧭 Main menu
Interactive CLI menu providing access to all download modes.
![Main menu](screenshots/menu.png)

### 📊 Download progress
Real-time progress bar with speed, ETA and card count.
![Download progress](screenshots/progress.png)

### ✅ Completion summary
Detailed summary after completion, including counts and performance.
![Completed](screenshots/completed.png)

---

## ✨ Features

- Downloads Magic: The Gathering **card and token images** directly from the public Scryfall API
- Designed specifically for **Forge-compatible** naming, layout, and folder structure
- Handles complex real-world card layouts correctly:
  - Double-faced cards (DFC)
  - Flip cards (with automatic rotation)
  - Split / Aftermath cards
  - Adventure cards
- Supports multiple workflows:
  - Full set downloads
  - Single-card (all prints or selected print)
  - Audit-driven token downloads (Forge `Audit.txt`)
- Safe and explicit by design:
  - No silent overwrites
  - Optional folder cleaning with user confirmation
  - Idempotent downloads (only missing files are fetched)
- Fully local and transparent:
  - No telemetry
  - No background execution
  - No external dependencies beyond Python libraries

---

## 🛣️ Roadmap

Planned improvements include internal refactors, modularization, and tools to
help detect and resolve Forge image naming inconsistencies.
See [`ROADMAP.md`](ROADMAP.md) for details.
Community feedback is welcome.

---

## ⚙️ Requirements

- Python 3.8 or higher
- Dependencies listed in `requirements.txt`

---

## 🌱 Getting started (first run)

If you're new to Python or GitHub, follow the step-by-step beginner guide:

➡️ **[GETTING_STARTED.md](GETTING_STARTED.md)**

---

## 📦 Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/laryzinha/forge-scryfall-scrapper.git
cd forge-scryfall-scrapper
pip install -r requirements.txt
```

---

## ▶️ Usage

Run the main entry point:

```bash
python src/Downloader.py
```

Follow the interactive on-screen menu to download:

For large downloads or first-time Forge installations,
audit-based workflows are recommended and may take longer
due to built-in safety checks.

* Complete sets
* Individual cards or prints
* Tokens via Forge Audit
* Cards via Forge Audit (non-token)

---

## 🌐 Network stability, rate limiting & long runs

This project is designed to run safely over long download sessions,
including full set downloads and large Forge audit-based workflows.

To prevent random crashes, connection resets, or partial downloads,
the downloader includes built-in network safety mechanisms:

- Automatic **retry with exponential backoff** for transient network errors
  (timeouts, connection resets, temporary server errors).
- Explicit handling of **Scryfall rate limits (HTTP 429)**.
- Conservative default request pacing to avoid stressing the API.
- Safe continuation of batch jobs — individual failures will not stop
  the entire run.

### Default network behavior

The following defaults are intentionally conservative and optimized for stability:

- Request pacing (`RATE_SLEEP`): ~5 requests/second
- Per-request timeout: 30 seconds
- Retry attempts: 6 (with exponential backoff)
- Short pause between large set downloads

These values are tuned to reduce common issues such as
`WinError 10054` (connection reset by peer) during long executions.

Advanced users may tweak these values in the source code,
but doing so may increase the likelihood of transient network errors.

---

## ⚠️ Known issues and limitations

Forge image handling can be inconsistent depending on the card layout,
print variation and Forge snapshot version. While this tool attempts to
handle most real-world cases, some limitations remain.

Please note the following:

- **Future or unreleased sets**
  Some sets may appear in search results (for example `OM2 – Through the Omenpaths 2`, scheduled for release on 2026-06-26) but return zero cards when downloading.
  This happens because the set already exists in Scryfall’s database, but **no cards have been published yet**.
  In this case, the Scryfall card search API returns no results, and the downloader correctly skips the set.
  Once cards are officially released on Scryfall, downloads will work automatically without requiring updates.

- Forge's **"Audit Card and Image Data"** feature may not report all missing
  images in every scenario. Depending on the card layout, naming or snapshot,
  some missing images may not be flagged.

- The same card artwork may exist under different names
  (oracle name, printed name, or flavor name). This can occasionally result in
  apparent duplicates or missing images when Forge resolves filenames
  differently than expected.

- Special layouts such as **split / aftermath**, **flip**, and
  **double-faced cards (DFC)** may generate multiple image files and/or require
  rotation. The downloader includes layout-aware handling, but edge cases may
  still require manual verification.

- Some Secret Lair (SLD) and special products use a printed card name that
  differs from the oracle name. In these cases, using the **SetOnly downloader**
  (printed-name–first logic) is recommended.

- When using audit-based downloads, some cards may remain unmatched due to
  naming discrepancies between Forge audit data and Scryfall metadata. These
  cases are intentionally logged and skipped rather than silently overwritten.
  
 - Windows reserved folder names can break some runs (CON, PRN, AUX, NUL, COM1…)
  Fixed in v1.1.1. To prevent long runs from failing, the downloader may 
  temporarily prefix those folders with `_` (e.g. `_CON`).
  After the download finishes, you can safely rename the folder back
  to its original name (`CON`) and Forge will detect it normally.
  
- When using audit-based downloads, some search queries may return
  **HTTP 404 (Not Found)** from the Scryfall API. In audit workflows,
  this indicates that no matching card was found for a given Forge 
  entry and is considered an expected outcome, not a download failure.
  These cases are logged and skipped safely.

- Long-running downloads may appear slower than bulk JSON-based tools.
  This is intentional: the downloader prioritizes correctness,
  stability, and Forge-compatible results over raw throughput.
  

These behaviors reflect real limitations in how Forge references card images
and how naming varies across different products and layouts.

Also, these limitations are documented intentionally to avoid silent failures or unexpected overwrites.

---

## 📁 Output

All downloaded content (cards, tokens, audit files and logs) is stored locally and ignored by Git via `.gitignore`.

Typical folders created at runtime:

* `Cards/`
* `Singles/`
* `Tokens/`

---

## 🧩 Project Structure

```text
forge-scryfall-scrapper/
├─ src/
│  ├─ Downloader.py            # Main entry point and interactive CLI menu
│  ├─ Downloader_SetOnly.py    # One-shot set downloader (printed-name first logic)
│  ├─ SingleCard.py            # Download individual cards (all prints or selected)
│  ├─ DToken.py                # Token downloader driven by Forge Audit.txt
│  ├─ AuditDownloader.py       # Audit-based card image resolution and checks
│  └─ __init__.py              # Optional (future modularization)
│
├─ .gitignore
├─ README.md                   # Project documentation
├─ SECURITY.md                 # Security & transparency policy
├─ requirements.txt            # Python dependencies
├─ LICENSE                     # MIT license
└─ CHANGELOG.md                # Version history and changes
```

Each script is designed to be runnable on its own, while `Downloader.py` acts as a central menu
to access the most common workflows.


---

## 💭 About this project

This is a personal project developed to support local Forge installations with reliable,
Forge-friendly card and token image downloads.

Before starting this project, I explored many of the existing approaches available online:
manual downloads, bulk JSON files, large data dumps, and other scripts and tools.
While functional, none of them fully matched what I was looking for.

Most solutions felt unnecessarily complex, relied on massive JSON datasets,
or required manual steps that made maintenance and updates harder than they needed to be.
I wanted something simpler, more direct, and focused on the real-world way Forge handles
card images.

So this project started from a very practical need:
a tool that could download images cleanly, handle naming and layout quirks correctly,
and work without forcing users to deal with large datasets or fragile workflows.

Over time, it evolved organically,  improving how cards are detected, renamed, rotated,
enumerated, and handled across different layouts and products.
As it kept proving useful for my own setup, I realized it might also help other Forge users.

> If it helps even one other person, that’s already enough. 💜

All card data and images are fetched dynamically and directly from the official
[Scryfall API](https://scryfall.com/docs/api).

This tool does **not** rely on Scryfall bulk JSON downloads and does **not** redistribute
any Scryfall data or assets. All downloaded content is stored locally on the user's machine
and excluded from version control via `.gitignore`.

---

## 🔐 Security & Transparency

This project is designed to be **fully transparent and local-only**.

- No telemetry
- No data upload
- No background execution
- Network access limited strictly to the official Scryfall API

👉 Please read **[SECURITY.md](SECURITY.md)** for a full technical breakdown.

---

🔍 **Open source & auditable**

Every line of code in this repository is readable and verifiable.  
If something looks wrong, it probably *is* wrong, open an issue (Please).

---

## 📜 License

This project is released under the MIT License.  
See the `LICENSE` file for details.

<p>This project downloads images from Scryfall for personal, non-commercial use.</p>
All card images are © Wizards of the Coast.

---

## 🔗 Related Projects

Forge (open-source MTG rules engine):
https://github.com/Card-Forge/forge

This project is not affiliated with, endorsed by, or maintained by the Forge project or its contributors.
It does not modify, embed, bundle, or interact with Forge’s codebase,  it only prepares image assets in a format Forge already supports.

---

Designed to be safe, idempotent and Forge-compatible by default.

---

<p align="center">
─────────────── ✦ ───────────────
</p>

<p align="center">
  <em>Built with care for Forge and the MTG community</em><br/>
  <strong>Laryzinha</strong>
</p>

<p align="center">
─────────────── ✦ ───────────────
</p>