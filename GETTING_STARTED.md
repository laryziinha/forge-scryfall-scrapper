Boa — vamos fazer isso do jeito “GitHub maduro”: **um guia separado** + **um bloco curto no README** apontando pro guia. Assim você ajuda iniciante sem transformar o README numa bíblia.

Pelo que você mandou, seu README já está bem estruturado.  E o roadmap também. 

---

# 1) O que vamos criar

## ✅ `GETTING_STARTED.md` (guia de iniciante)

Focado em:

* **Quem nunca mexeu com Python**
* Quem **não quer usar Git**
* Quem quer “baixar ZIP e rodar”

## ✅ Pequena seção no `README.md`

Um bloco “First run (Windows)” bem curto + link pro guia.

---

# 2) `GETTING_STARTED.md` pronto (copy/paste)

Crie um arquivo na raiz do repo: `GETTING_STARTED.md`

````md
# Getting started (Windows)

This guide is written for first-time users (no Git, no Python experience required).

---

## 1) Install Python

1. Download **Python 3.10+** from the official website.
2. During installation, make sure to check:
   - ✅ **Add Python to PATH**

After installing, open **Command Prompt** and verify:

```bat
python --version
pip --version
````

If both commands work, you're ready.

---

## 2) Download the project (no Git required)

1. Open the repository on GitHub
2. Click **Code** → **Download ZIP**
3. Extract the ZIP to a folder (example: `C:\forge-scryfall-scrapper\`)

---

## 3) Open a terminal in the project folder

Inside the extracted folder:

* Hold **Shift** and right-click in empty space
* Choose **Open in Terminal** (or **Open PowerShell here**)

You should be inside the folder that contains:

* `README.md`
* `requirements.txt`
* `src/`

---

## 4) Install dependencies

Run:

```bat
pip install -r requirements.txt
```

---

## 5) Run the tool

Run:

```bat
python src/Downloader.py
```

A menu will appear. Choose the desired mode and follow the prompts.

---

## Output folders

Downloads are stored locally (and ignored by Git). Common folders:

* `Cards/`
* `Singles/`
* `Tokens/`

---

## Troubleshooting

### “python is not recognized” / “pip is not recognized”

* Python is not installed, or PATH was not enabled.
* Reinstall Python and check ✅ **Add Python to PATH**.

### Dependency errors (Pillow / tqdm / requests / colorama)

Try:

```bat
pip install --upgrade pip
pip install pillow tqdm requests colorama
```

Then rerun:

```bat
pip install -r requirements.txt
```

### Downloads don’t start / very slow

* Check firewall/antivirus rules
* Check your internet connection
* Try again later (Scryfall can rate-limit requests)

### Forge audit doesn’t find everything

Forge may not report 100% of missing images depending on snapshot/version/layout.
See the README section **Known issues and limitations**.

---

## Optional: using Git (advanced)

If you prefer cloning instead of ZIP:

```bash
git clone https://github.com/laryziinha/forge-scryfall-scrapper.git
cd forge-scryfall-scrapper
pip install -r requirements.txt
python src/Downloader.py
```

````