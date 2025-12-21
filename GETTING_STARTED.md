# 🌱 Getting Started — Beginner Guide

This guide is for **first-time users** who may be new to:

- Python
- GitHub
- Command Line (Terminal / CMD)
- This project itself

If you’ve never run a Python script before, follow the steps below carefully.

---

## 🐍 Step 1 — Install Python (Windows)

1. Download Python from the official website:  
   https://www.python.org/downloads/windows/

2. Run the installer.

3. **IMPORTANT:** enable the option:  
   ✅ **Add Python to PATH**

4. Click **Install Now** and finish the installation.

---

### ✅ Verify the installation

Open **Command Prompt (CMD)** and run:

```bash
python --version
````

You should see something like:

```text
Python 3.10.x
```

If Python is not recognized:

* Reinstall Python
* Make sure **Add Python to PATH** is checked
* Restart the terminal

---

## 📦 Step 2 — Download the Project

You have two options.
If you are new to GitHub, **Option A is recommended**.

---

### 📁 Option A — Download ZIP (Beginner)

1. Open the project page:
   [https://github.com/laryziinha/forge-scryfall-scrapper](https://github.com/laryziinha/forge-scryfall-scrapper)

2. Click **Code → Download ZIP**

3. Extract the ZIP file to a folder of your choice.
   Example:

```text
C:\ForgeTools\forge-scryfall-scrapper
```

---

### 🔗 Option B — Clone with Git (Advanced)

If you already use Git, run:

```bash
git clone https://github.com/laryziinha/forge-scryfall-scrapper.git
cd forge-scryfall-scrapper
```

---

## 💻 Step 3 — Open the Terminal in the Project Folder

Make sure the terminal is opened **inside** the project folder.

Example (Windows):

```bash
cd C:\ForgeTools\forge-scryfall-scrapper
```

Tip:
You can also open the folder in Windows Explorer, click the address bar, type `cmd`, and press **ENTER**.

---

## 📥 Step 4 — Install Dependencies

From the project folder, run:

```bash
python -m pip install -r requirements.txt
```

This installs all required libraries (`requests`, `pillow`, `tqdm`, etc.).

If `pip` is not recognized, use this command instead:

```bash
python -m pip install -r requirements.txt
```

---

## ▶️ Step 5 — Run the Downloader

From the project folder, run:

```bash
python src/Downloader.py
```

If everything is correct, the **interactive menu** will appear.

---

## 🧭 Step 6 — Using the Menu

Follow the on-screen instructions to:

* Download a specific set
* Download all sets
* Download sets listed in `Sets.txt`
* Download tokens (Forge Audit based)
* Download individual cards or prints
* Download missing cards via Forge Audit

All downloaded files are stored locally and **ignored by Git**.

---

## 🛠️ Troubleshooting

**Python not recognized**

* Reinstall Python
* Make sure **Add Python to PATH** is checked
* Restart the terminal

**Nothing downloads**

* Check your internet connection
* Firewall or antivirus may block requests
* Scryfall API rate limits may apply

---

## 📝 Notes

* This project uses the **Scryfall public API**
* No Scryfall bulk JSON files are required
* Images are downloaded directly from the API
* Forge audit behavior may vary depending on Forge version

If something goes wrong, open an issue on GitHub or check the README for known limitations.

---

### 🧙‍♀️ Magic curiosity

In early Magic rules, the action we now know as “tap” was originally written as
*turn the card sideways*.

The curved tap symbol (⤵︎) was introduced later to make rules text shorter and
more language-independent.

Over time, this symbol became one of the most recognizable visual elements in
trading card games and is now used far beyond Magic itself.

Just a detail. ;)