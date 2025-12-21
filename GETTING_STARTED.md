````md
# Getting Started — Beginner Guide

This guide is for **first-time users** who may be new to:
- Python
- GitHub
- Command Line (Terminal / CMD)
- This project itself

No prior Python or GitHub experience is required.

---

## 1. Install Python (Windows)

1. Download Python from the official website:  
   👉 https://www.python.org/downloads/windows/

2. Run the installer.
3. **IMPORTANT:** Check the option  
   ✅ *Add Python to PATH*
4. Click **Install Now**.
5. Finish the installation.

### Verify installation

Open **Command Prompt** (CMD) and run:

```bash
python --version
````

You should see something like:

```text
Python 3.10.x
```

If Python is not recognized, reinstall it and make sure **“Add to PATH”** is checked.

---

## 2. Download the Project

You have two options.
If you are new to GitHub, **Option A is recommended**.

---

### Option A — Download ZIP (Recommended for beginners)

1. Open the project page:
   👉 [https://github.com/laryzinha/forge-scryfall-scrapper](https://github.com/laryzinha/forge-scryfall-scrapper)

2. Click **Code → Download ZIP**

3. Extract the ZIP file to a folder of your choice
   (example: `C:\ForgeTools\forge-scryfall-scrapper`)

---

### Option B — Clone with Git (Advanced users)

If you already use Git:

```bash
git clone https://github.com/laryzinha/forge-scryfall-scrapper.git
cd forge-scryfall-scrapper
```

---

## 3. Install Dependencies

Open **Command Prompt** inside the project folder.

Then run:

```bash
pip install -r requirements.txt
```

This installs all required libraries (requests, pillow, tqdm, etc.).

---

## 4. Run the Downloader

From the project root folder, run:

```bash
python src/Downloader.py
```

You should see the interactive menu appear.

---

## 5. Using the Menu

Follow the on-screen instructions to:

* Download a specific set
* Download all sets
* Download sets listed in `Sets.txt`
* Download tokens (Forge Audit based)
* Download individual cards or prints
* Download missing cards via Forge Audit

All downloads are stored **locally** and ignored by Git.

---

## 6. Troubleshooting

### Python not recognized

* Reinstall Python
* Make sure **Add Python to PATH** is checked
* Restart the terminal

### pip not recognized

Try:

```bash
python -m pip install -r requirements.txt
```

### Nothing downloads

* Check your internet connection
* Firewall / antivirus may block requests
* Scryfall API rate limits may apply

---

## Notes

* This project uses the **Scryfall public API**
* No Scryfall bulk JSON files are required
* Images are downloaded directly from the API
* Forge audit behavior may vary depending on version and snapshot

---

If something goes wrong, open an issue on GitHub or check the README for known limitations.

````

---