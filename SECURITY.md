# Security & Transparency

This repository contains a **local-only Python toolset** designed to download and organize
Magic: The Gathering **card and token images** for **Forge** using the **public Scryfall API**.

Transparency is intentional.
Everything below is derived directly from the source code in this repository.

---

## ✅ What this project DOES

- Downloads **card and token images only**
- Uses the **public Scryfall API** as the sole external data source
- Saves files **locally**, inside folders created next to the scripts:
  - `Cards/`
  - `Singles/`
  - `Tokens/`
- Supports multiple workflows:
  - Full SET downloads
  - Single-card (prints) downloads
  - Token downloads driven by Forge `Audit.txt`
  - Audit-based card resolution by printed / flavor / oracle names
- Handles complex layouts safely:
  - DFC
  - Flip (with rotation)
  - Split / Aftermath
  - Adventure
- Requires **explicit user interaction** for:
  - Starting downloads
  - Cleaning folders
  - Batch operations

---

## ❌ What this project DOES NOT do

- ❌ No data upload of any kind
- ❌ No telemetry, analytics, tracking, or logging of user activity
- ❌ No background execution
- ❌ No persistence (no startup entries, services, registry edits, cron jobs, etc.)
- ❌ No execution of shell or system commands
- ❌ No downloading or executing external code
- ❌ No obfuscation, encryption, `eval`, or `exec`
- ❌ No modification of files outside the project folders

---

## 📄 About JSON Usage (Important Clarification)

This project **does not store, generate, or consume local JSON files**.

- JSON is used **only in-memory** as the native response format of the Scryfall HTTP API.
- All processing is done directly on the response objects.
- No card databases or metadata are written to disk.

Downloaded content consists **only of image files** (`.jpg` / `.png`) and plain-text logs.

---

## 🌐 Network Access (Fully Transparent)

The scripts perform **outbound HTTP requests only** to Scryfall endpoints.

### Domains used
- `https://api.scryfall.com`

No other domains are contacted.

### Official references
- Scryfall website:  
  https://scryfall.com
- Scryfall API documentation:  
  https://scryfall.com/docs/api
- Scryfall data usage & terms:  
  https://scryfall.com/docs/api#terms

---

## 🔗 Related Projects

This tool is intended to support **local installations** of the Forge MTG engine:

- Forge (open-source MTG rules engine):  
  https://github.com/Card-Forge/forge

This project does not modify, embed, or interact with Forge’s codebase.
It only prepares image assets in a format Forge already supports.

---

## 🗂️ File System Behavior

- All files are created **inside the project directory**
- No hidden files are generated
- Folder cleaning (`delete`) exists **only** for:
  - A specific SET folder
  - Triggered **explicitly** by the user
  - Requires confirmation before execution

There are **no recursive deletes** outside the selected target folder.

---

## 🧾 Logs & Text Files

The project may generate **plain-text logs** for transparency and debugging, such as:
- Download error logs per SET
- Audit mismatch logs
- Token download summaries

These logs:
- Contain **no personal data**
- Are not uploaded anywhere
- Exist solely for user review

---

## 🔍 How to Verify Everything Yourself

This repository is fully open source.

You are encouraged to:
- Read the Python files directly
- Search for:
  - `subprocess`
  - `os.system`
  - `eval`
  - `exec`
  - `socket`
- Run the scripts in a Python virtual environment (`venv`)
- Monitor network traffic if desired (firewall / proxy)

Nothing is hidden.  
What you see is exactly what runs.

---

## 🧪 Recommended Safe Usage

Although no malicious behavior exists, best practices still apply:

- Use a Python virtual environment (`venv`)
- Review options before enabling any folder-cleaning mode
- Run the scripts only from directories you control

---

## ⚖️ Disclaimer

This is a **personal, unofficial project**.

- Not affiliated with Wizards of the Coast
- Not affiliated with Scryfall
- All card data and images are property of their respective owners
- Data access follows Scryfall’s public API terms

---

## 📬 Reporting Concerns

If you believe you have found:
- Unexpected behavior
- A security issue
- Or something unclear

Please open an issue on GitHub.

Security concerns are taken seriously.

---

**Transparency over trust.  
Read the code. Verify it yourself.**