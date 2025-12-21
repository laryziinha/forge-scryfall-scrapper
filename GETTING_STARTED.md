## Getting Started & Beginner Guide

This guide is for **first-time users** who may be new to:

* Python
* GitHub
* Command Line (Terminal / CMD)
* This project itself

No prior Python or GitHub experience is required.

1. Install Python (Windows)

1. Download Python from the official website:
   [https://www.python.org/downloads/windows/](https://www.python.org/downloads/windows/)

2. Run the installer.

3. IMPORTANT: check the option:
   Add Python to PATH

4. Click Install Now and finish the installation.

## Verify installation

Open Command Prompt (CMD) and run:

python --version

You should see something like:

Python 3.10.x

If Python is not recognized, reinstall it and make sure “Add Python to PATH” is checked.

2. Download the Project

You have two options.
If you are new to GitHub, Option A is recommended.

## Option A — Download ZIP (Recommended for beginners)

1. Open the project page:
   [https://github.com/laryziinha/forge-scryfall-scrapper](https://github.com/laryziinha/forge-scryfall-scrapper)

2. Click Code → Download ZIP

3. Extract the ZIP file to a folder of your choice
   Example: C:\ForgeTools\forge-scryfall-scrapper

## Option B — Clone with Git (Advanced users)

If you already use Git, run:

git clone [https://github.com/laryziinha/forge-scryfall-scrapper.git](https://github.com/laryziinha/forge-scryfall-scrapper.git)
cd forge-scryfall-scrapper

3. Open the terminal in the project folder

Make sure your terminal is inside the extracted or cloned folder.

Example (Windows):

cd C:\ForgeTools\forge-scryfall-scrapper

Tip: You can also open the folder in Windows Explorer, click on the address bar, type cmd, and press ENTER.

4. Install Dependencies

From the project folder, run:

python -m pip install -r requirements.txt

This installs all required libraries (requests, pillow, tqdm, etc.).

5. Run the Downloader

From the project folder, run:

python src/Downloader.py

You should see the interactive menu appear.

6. Using the Menu

Follow the on-screen instructions to:

* Download a specific set
* Download all sets
* Download sets listed in Sets.txt
* Download tokens (Forge Audit based)
* Download individual cards or prints
* Download missing cards via Forge Audit

All downloads are stored locally and ignored by Git.

7. Troubleshooting

Python not recognized:

* Reinstall Python
* Make sure Add Python to PATH is checked
* Restart the terminal

pip not recognized:
Use this instead:

python -m pip install -r requirements.txt

Nothing downloads:

* Check your internet connection
* Firewall or antivirus may block requests
* Scryfall API rate limits may apply

## Notes

* This project uses the Scryfall public API
* No Scryfall bulk JSON files are required
* Images are downloaded directly from the API
* Forge audit behavior may vary depending on version and snapshot

If something goes wrong, open an issue on GitHub or check the README for known limitations.