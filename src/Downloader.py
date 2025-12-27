# ============================================================
#  Scryfall Image Downloader (Forge Friendly)
#  Author: Laryzinha
#  Version: 1.1.4
#  Description:
#      High-quality Scryfall image downloader with colored UI,
#      batch SET download, Singles integration and Token/Audit support.
# ============================================================

import os
import re
import time
import unicodedata
import difflib
import shutil
import requests
import random
from pathlib import Path
from typing import Dict, List, Tuple, Optional, NamedTuple
from tqdm import tqdm
from PIL import Image
from io import BytesIO

# --- TOKENS INTEGRATION ---
try:
    import DToken as dt  # Tokens Module
except Exception as _e:
    dt = None

# --- SINGLES INTEGRATION ---
try:
    import SingleCard as sc  # Singles Module
except Exception as _e:
    sc = None

# --- FORGE AUDIT INTEGRATION ---
try:
    import AuditDownloader as ad
except ImportError:
    ad = None

# --- PRINTED-NAME SET DOWNLOADER (EXPERIMENTAL / ADVANCED) ---
try:
    import SetDownloader_PrintedName as spn
except Exception as _e:
    spn = None

# --- FAST CSV SET DOWNLOADER (EXPERIMENTAL / ADVANCED) ---
try:
    import fast_csv_set as fcsv
except Exception as _e:
    fcsv = None

# --- Colors (pink etc.) ---
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
    PINK = Fore.MAGENTA
    GREEN = Fore.GREEN
    CYAN = Fore.CYAN
    YELLOW = Fore.YELLOW
    RED = Fore.RED
    BRIGHT = Style.BRIGHT
    RESET = Style.RESET_ALL
except Exception:
    PINK = GREEN = CYAN = YELLOW = RED = BRIGHT = RESET = ""

SCRYFALL_API = "https://api.scryfall.com"

# --- Networking / rate control ---
RATE_SLEEP = 0.20      # Stability - Longer Downloader but Safe (antes 0.12)
TIMEOUT = 30           # Seconds per Request
RETRY = 6              # Retry by request (transitory errors)
BACKOFF_BASE = 1.2     # exponential backoff
BACKOFF_JITTER = 0.35  # jitter

# --- Batch behavior ---
SET_PAUSE = 1.5        # Small pause between SETS (managing WinError 10054 on ALL sets)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ForgeImageFetcher/1.1 (laryzinha-scrapper)"})

# ---------- Wrapper ----------

def scry_get_json(url: str, *, params: dict | None = None) -> dict:
    """
    GET com retry/backoff para erros transitórios:
    - Connection reset (WinError 10054)
    - timeouts
    - 429 (rate limit)
    - 5xx
    """
    last_exc = None

    for attempt in range(1, RETRY + 1):
        try:
            r = SESSION.get(url, params=params, timeout=TIMEOUT)

            # Rate-limit / servidor instável
            if r.status_code == 429 or 500 <= r.status_code <= 599:
                raise requests.exceptions.HTTPError(f"HTTP {r.status_code}", response=r)

            r.raise_for_status()

            # throttle leve entre requests bem-sucedidos
            time.sleep(RATE_SLEEP)

            return r.json()

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError
        ) as e:
            last_exc = e

            # backoff exponencial + jitter
            sleep_s = (BACKOFF_BASE ** attempt) + (random.random() * BACKOFF_JITTER)

            if attempt == RETRY:
                raise

            print(f"{YELLOW}[net]{RESET} retry {attempt}/{RETRY} in {sleep_s:.1f}s — {e}")
            time.sleep(sleep_s)

    raise last_exc  # segurança (não deve chegar aqui)

def download_bytes_with_retry(url: str) -> bytes:
    """
    Baixa bytes (imagem) com retry/backoff.
    Mantém tua pipeline atual (save_image(...) continua igual).
    """
    last_exc = None

    for attempt in range(1, RETRY + 1):
        try:
            with SESSION.get(url, stream=True, timeout=TIMEOUT) as r:
                if r.status_code == 429 or 500 <= r.status_code <= 599:
                    raise requests.exceptions.HTTPError(f"HTTP {r.status_code}", response=r)

                r.raise_for_status()
                content = r.content  # ok aqui (imagem)
            time.sleep(RATE_SLEEP)
            return content

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            OSError,
        ) as e:
            last_exc = e
            sleep_s = (BACKOFF_BASE ** attempt) + (random.random() * BACKOFF_JITTER)
            if attempt == RETRY:
                raise
            print(f"{YELLOW}[net-img]{RESET} retry {attempt}/{RETRY} in {sleep_s:.1f}s — {e}")
            time.sleep(sleep_s)

    raise last_exc

# ---------- Utils ----------

def script_root_cards() -> Path:
    # Default directory = script folder + \Cards
    try:
        base = Path(__file__).resolve().parent
    except NameError:
        base = Path.cwd()
    return base / "Cards"

# --- App brand ---
APP_NAME = "Laryzinha Scryfall Scrapper"
APP_VERSION = "1.1.4-beta.1"
APP_SUBTITLE = "Scryfall Downloader — Forge Friendly (Large)"

def banner():
    import shutil
    cols = shutil.get_terminal_size((80, 20)).columns
    cols = max(72, min(cols, 100))  # Width (72–100)

    title = f"{APP_NAME} — {APP_VERSION}"
    top = "═" * cols
    sub = APP_SUBTITLE.center(cols)

    print(PINK + top + RESET)
    print(BRIGHT + title.center(cols) + RESET)
    print(PINK + top + RESET)
    print(sub)
    print(PINK + "─" * cols + RESET)

_ansi_re = re.compile(r"\x1b\[[0-9;]*m")

def _visible_len(s: str) -> int:
    """Visible length without ANSI codes (for box alignment)."""
    return len(_ansi_re.sub("", s))

def box(text_lines: List[str], color=CYAN) -> None:
    width = max(_visible_len(t) for t in text_lines) if text_lines else 0
    top = "╔" + "═" * (width + 2) + "╗"
    bot = "╚" + "═" * (width + 2) + "╝"
    print(color + top + RESET)
    for t in text_lines:
        vis = _visible_len(t)
        pad = width - vis
        print(color + "║ " + RESET + t + " " * pad + color + " ║" + RESET)
    print(color + bot + RESET)

def safe_set_folder_name(set_code: str) -> str:
    """
    Windows-safe folder name for set codes.
    Avoids reserved device names like CON, PRN, AUX, NUL, COM1.., LPT1...
    """
    code = (set_code or "UNK").strip().upper()

    # remove invalid filename chars (also protects against weird input)
    code = slugify_filename(code)

    # Windows also dislikes trailing dots/spaces in names
    code = code.rstrip(" .")

    if os.name == "nt":
        reserved = {"CON", "PRN", "AUX", "NUL"}
        reserved |= {f"COM{i}" for i in range(1, 10)}
        reserved |= {f"LPT{i}" for i in range(1, 10)}

        if code.upper() in reserved:
            code = f"_{code}"   # prefix to keep it unique and obvious

    return code

def is_windows_reserved_set_code(set_code: str) -> bool:
    """True if code is a Windows reserved device name (CON, PRN, AUX, NUL, COM1.., LPT1..)."""
    if os.name != "nt":
        return False
    code = (set_code or "").strip().upper()
    reserved = {"CON", "PRN", "AUX", "NUL"}
    reserved |= {f"COM{i}" for i in range(1, 10)}
    reserved |= {f"LPT{i}" for i in range(1, 10)}
    return code in reserved


def promote_reserved_set_folder(base_dir: Path, set_code: str) -> tuple[bool, str]:
    """
    If we downloaded into _SET (reserved workaround), try moving everything into SET and remove _SET.

    Returns (promoted, message).
    - promoted=True => moved at least one file into final folder.
    - promoted=False => keep _SET (fallback).
    """
    code = (set_code or "").strip().upper()

    if not is_windows_reserved_set_code(code):
        return (False, "not_reserved")

    temp_dir = base_dir / f"_{code}"
    final_dir = base_dir / code

    if not temp_dir.exists() or not temp_dir.is_dir():
        return (False, "temp_missing")

    # Try to create the final folder (may fail in some Windows contexts)
    try:
        final_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return (False, f"cannot_create_final: {e}")

    moved = 0
    conflicts = 0
    errors = 0

    for item in temp_dir.iterdir():
        try:
            target = final_dir / item.name

            # Safe by default: do NOT overwrite
            if target.exists():
                conflicts += 1
                continue

            item.rename(target)
            moved += 1
        except Exception:
            errors += 1

    # Remove temp folder if empty
    try:
        if not any(temp_dir.iterdir()):
            temp_dir.rmdir()
    except Exception:
        pass

    if moved > 0:
        return (True, f"promoted: moved={moved}, conflicts={conflicts}, errors={errors}")

    return (False, f"no_move: conflicts={conflicts}, errors={errors}")


def slugify_filename(name: str) -> str:
    name = name.strip().replace(":", "-")
    return re.sub(r'[<>:\"/\\|?*\x00-\x1F]', "_", name)

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def ensure_dir(p: Path):
    # If the path already exists but is not a directory, fail with a clear message
    if p.exists() and not p.is_dir():
        raise RuntimeError(f"Path exists but is not a directory: {p}")

    # If parent exists but is not a directory, also fail clearly
    parent = p.parent
    if parent.exists() and not parent.is_dir():
        raise RuntimeError(f"Parent path exists but is not a directory: {parent}")

    p.mkdir(parents=True, exist_ok=True)

def clear_directory(p: Path):
    for item in p.iterdir():
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            try:
                item.unlink()
            except Exception:
                pass

def get_all_sets() -> List[dict]:
    js = scry_get_json(f"{SCRYFALL_API}/sets")
    return js.get("data", [])

def get_set_meta(code: str) -> dict:
    return scry_get_json(f"{SCRYFALL_API}/sets/{code.lower()}")

def fuzzy_match_set(user_text: str, sets_meta: List[dict]) -> Optional[dict]:
    raw = user_text.strip()
    lower = raw.lower()
    noacc = strip_accents(lower)

    aliases = {
        "quarta edicao": "4ed", "quarta edição": "4ed", "quarta": "4ed",
        "quinta edicao": "5ed", "quinta edição": "5ed", "quinta": "5ed",
        "sexta edicao": "6ed", "sexta edição": "6ed", "sexta": "6ed",
        "setima edicao": "7ed", "sétima edição": "7ed", "setima": "7ed", "sétima": "7ed",
        "oitava edicao": "8ed", "oitava edição": "8ed", "oitava": "8ed",
        "nona edicao": "9ed", "nona edição": "9ed", "nona": "9ed",
        "decima edicao": "10e", "décima edição": "10e", "decima": "10e", "décima": "10e",
    }
    if noacc in aliases:
        lower = aliases[noacc]
        noacc = aliases[noacc]

    for s in sets_meta:
        if lower == (s.get("code") or "").lower(): return s
        if lower == (s.get("mtgo_code") or "").lower(): return s
        if lower == (s.get("arena_code") or "").lower(): return s

    names = [strip_accents((s.get("name") or "").lower()) for s in sets_meta]
    best = difflib.get_close_matches(noacc, names, n=1, cutoff=0.7)
    if best:
        idx = names.index(best[0]); return sets_meta[idx]

    codes = [(s.get("code") or "").lower() for s in sets_meta]
    bestc = difflib.get_close_matches(lower, codes, n=1, cutoff=0.6)
    if bestc:
        idx = codes.index(bestc[0]); return sets_meta[idx]

    return None

def scry_search_cards_for_set(set_code: str) -> List[dict]:
    """Return 'prints' (no art dedupe) + extras/variations."""
    cards: List[dict] = []
    q = f"e:{set_code}"
    page = 1

    while True:
        url = f"{SCRYFALL_API}/cards/search"
        params = {
            "q": q,
            "order": "set",
            "dir": "asc",
            "unique": "prints",
            "include_extras": "true",
            "include_variations": "true",
            "page": str(page),
        }

        try:
            js = scry_get_json(url, params=params)
        except requests.exceptions.HTTPError as e:
            # Alguns sets podem retornar 404 (ou query sem resultados em certos casos)
            resp = getattr(e, "response", None)
            if resp is not None and resp.status_code == 404:
                break
            raise  # outros erros: deixa propagar (ou trata no batch loop)

        cards.extend(js.get("data", []))
        if not js.get("has_more", False):
            break
        page += 1

    return cards

def display_name_for_single_image(card: dict) -> str:
    """
    Single-image cases:
      - Split / Aftermath: concatenates both face names without spaces
        (e.g., "AssaultBattery")
      - Adventure: uses ONLY the primary face name (faces[0])
      - All other single-face cards: uses card["name"]
    """
    layout = (card.get("layout") or "").lower()
    if layout in {"split", "aftermath"}:
        faces = card.get("card_faces") or []
        if faces:
            combined = "".join((f.get("name") or "").replace(" ", "") for f in faces).strip()
            if combined:
                return combined
    if layout == "adventure":
        faces = card.get("card_faces") or []
        if faces and (faces[0].get("name") or "").strip():
            return faces[0]["name"].strip()
    return (card.get("name") or "Unknown").strip()

class ImgEntry(NamedTuple):
    url: str
    name: str
    rotate: Optional[str] = None  # None | "h90" | "rot180"

def pick_image_entries(card: dict) -> List[ImgEntry]:
    """
    Layout rules:
      - image_uris:
          * split/aftermath -> 1 file with concatenated name
          * flip -> 2 files: Face1 normal, Face2 rotated 180°
          * others -> 1 file with card['name']
      - card_faces with image_uris -> 1 file per face (DFC etc.)
    """
    def from_uris(uris: dict) -> Optional[str]:
        if not uris:
            return None
        return uris.get("large") or uris.get("png") or uris.get("normal") or uris.get("small")

    entries: List[ImgEntry] = []
    layout = (card.get("layout") or "").lower()

    if card.get("image_uris"):
        u = from_uris(card["image_uris"])
        if not u:
            return entries

        if layout in {"split", "aftermath"}:
            name = display_name_for_single_image(card)
            entries.append(ImgEntry(u, name, None))
            return entries
        
        if layout == "adventure":
            name = display_name_for_single_image(card)  # Main Face
            entries.append(ImgEntry(u, name, None))
            return entries

        if layout == "flip":
            faces = card.get("card_faces") or []
            if faces:
                face1 = (faces[0].get("name") or card.get("name") or "Unknown").strip()
                face2 = (faces[1].get("name") or card.get("name") or "Unknown").strip()
                entries.append(ImgEntry(u, face1, None))
                entries.append(ImgEntry(u, face2, "rot180"))
                return entries

        entries.append(ImgEntry(u, (card.get("name") or "Unknown").strip(), None))
        return entries

    for face in (card.get("card_faces") or []):
        face_url = from_uris(face.get("image_uris", {}))
        if face_url:
            face_name = (face.get("name") or card.get("name") or "Unknown").strip()
            entries.append(ImgEntry(face_url, face_name, None))
    return entries

def should_rotate_h90(card: dict, img: Image.Image) -> bool:
    layout = (card.get("layout") or "").lower()
    horizontal_layouts = {"split", "aftermath", "flip"}
    w, h = img.size
    return (w > h) and (layout in horizontal_layouts)

def infer_ext_from_url(url: str) -> str:
    return ".png" if ".png" in url.lower() else ".jpg"

def save_image(content: bytes, out_path: Path, card=None, rotate_mode: Optional[str] = None):
    """
    - rotate_mode == "rot180" → rotate 180° and force .jpg
    - rotate_mode None → if horizontal (split/aftermath/flip), rotate 90° and force .jpg
    - otherwise save as-is
    """
    if rotate_mode or card:
        try:
            img = Image.open(BytesIO(content))
            if rotate_mode == "rot180":
                img = img.rotate(180, expand=True)
                rgb = img.convert("RGB")
                rgb.save(out_path.with_suffix(".jpg"), quality=95, subsampling=0, optimize=True)
                return
            if should_rotate_h90(card, img):
                img = img.rotate(90, expand=True)
                rgb = img.convert("RGB")
                rgb.save(out_path.with_suffix(".jpg"), quality=95, subsampling=0, optimize=True)
                return
        except Exception:
            pass
    with open(out_path, "wb") as f:
        f.write(content)

# ---------- PRINTED-NAME SET DOWNLOADER (Experimental) ----------
def printed_name_set_menu(base_dir: Path):
    if spn is None:
        print("SetDownloader_PrintedName module not found. Place SetDownloader_PrintedName.py next to this script.")
        return

    # Redirect module output folder to our integrated Cards folder
    try:
        spn.cards_root = lambda: base_dir
    except Exception:
        pass

    # Just run it (the main menu already warned/confirmed)
    spn.main()

# ---------- FAST CSV DOWNLOADER (Experimental) ----------

def fastcsv_set_menu(base_dir: Path):
    """
    Fast CSV SET Downloader — Experimental
    Single-box UX, filesystem-driven resume, multi-set loop.
    """
    if fcsv is None:
        box(["fast_csv_set.py module not found next to this script."], color=RED)
        input("\nPress ENTER to return to the main menu...")
        return

    sets_meta = get_all_sets()

    def _match_sets(q: str):
        q = (q or "").strip().lower()
        if not q:
            return []
        exact = [s for s in sets_meta if str(s.get("code", "")).lower() == q]
        if exact:
            return exact
        out = []
        for s in sets_meta:
            code = str(s.get("code", "")).lower()
            name = str(s.get("name", "")).lower()
            if q in code or q in name:
                out.append(s)
        return out

    # =========================
    # MODE LOOP (download many)
    # =========================
    while True:

        # -------- Pick SET (single yellow box) --------
        while True:
            box([
                f"{BRIGHT}Fast CSV SET Downloader{RESET}  {YELLOW}(Experimental){RESET}",
                "",
                "Ultra-fast mode optimized for very large sets.",
                "Resume supported (safe to run multiple times).",
                "",
                f"{BRIGHT}Download a specific SET{RESET}",
                "Type the SET code or part of the name.",
                f"Examples: {CYAN}one{RESET}, {CYAN}m21{RESET}, {CYAN}Quarta Edição{RESET}",
                "",
                f"[{CYAN}B{RESET}] Back to Main Menu",
            ], color=YELLOW)

            user_in = input(BRIGHT + "SET: " + RESET).strip()
            if not user_in:
                continue
            if user_in.lower() in {"b", "back"}:
                return

            matches = _match_sets(user_in)
            if not matches:
                box([f"{RED}No sets found for:{RESET} {user_in}"], color=RED)
                continue

            if len(matches) == 1:
                chosen = matches[0]
                break

            # multiple matches
            matches = matches[:20]
            lines = [f"{BRIGHT}Multiple matches found:{RESET}"]
            for i, s in enumerate(matches, 1):
                code = str(s.get("code", "")).upper()
                name = str(s.get("name", "") or "Unknown")
                released = s.get("released_at") or "—"
                lines.append(f"{CYAN}{i:>2}{RESET}) {code} — {name} ({released})")
            lines.append("")
            lines.append(f"Type a number 1-{len(matches)} or {CYAN}B{RESET} to go back.")
            box(lines, color=YELLOW)

            sel = input(BRIGHT + "Choice: " + RESET).strip().lower()
            if sel in {"b", "back"}:
                return
            if sel.isdigit():
                n = int(sel)
                if 1 <= n <= len(matches):
                    chosen = matches[n - 1]
                    break

            box([f"{RED}Invalid selection.{RESET}"], color=RED)

        # -------- SET meta --------
        set_code = (chosen.get("code") or "").upper()
        set_name = chosen.get("name") or "Unknown"
        set_type = (chosen.get("set_type") or "—").replace("_", " ").title()
        released = chosen.get("released_at") or "—"
        expected = chosen.get("card_count") or chosen.get("printed_size") or "—"

        try:
            total_regs, _ = scry_search_cards_for_set_cached(chosen["code"])
        except Exception:
            total_regs = "—"

        # -------- Threads --------
        box([
            f"{BRIGHT}Concurrency (threads){RESET}",
            "",
            f"Default: {CYAN}24{RESET} (recommended)",
            "Higher values = faster downloads",
            "Lower values = more stable on slow/unstable connections",
            "",
            "Press ENTER to use the default.",
        ], color=YELLOW)

        raw = input(BRIGHT + "Threads: " + RESET).strip()
        try:
            threads = int(raw) if raw else 24
            if threads < 1:
                threads = 24
        except Exception:
            threads = 24

        root = base_dir.parent
        manifest_path, out_dir = fcsv.default_paths(root, set_code)

        # -------- Info --------
        box([
            f"{BRIGHT}Fast CSV run starting{RESET}",
            "",
            f"{set_name}  [{CYAN}{set_code}{RESET}]",
            f"Type: {set_type}   Release: {released}",
            f"Search results (records/prints): {CYAN}{total_regs}{RESET}",
            f"Scryfall reference size: {CYAN}{expected}{RESET}",
            "",
            f"Threads: {CYAN}{threads}{RESET}",
            f"Manifest: {CYAN}{manifest_path.name}{RESET}",
            f"Folder:   {CYAN}{out_dir}{RESET}",
        ], color=YELLOW)

        import io, time as _time, contextlib
        start = _time.time()
        buf = io.StringIO()

        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            manifest_path.parent.mkdir(parents=True, exist_ok=True)

            # Manifest = contract
            if manifest_path.exists():
                rows = fcsv.read_manifest_csv(manifest_path)
                total_rows = len(rows)
                print(f"\n{CYAN}[fast]{RESET} Using existing manifest: {manifest_path.name} (rows={total_rows})")
            else:
                print(f"\n{CYAN}[fast]{RESET} Building manifest for {set_code}...")
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    rows = fcsv.build_manifest_for_set(set_code, manifest_path)
                total_rows = len(rows)
                print(f"{CYAN}[fast]{RESET} Manifest created: {manifest_path.name} (rows={total_rows})")

            # Pending = missing files
            missing_before = []
            for r in rows:
                fp = out_dir / r.target_filename
                if not (fp.exists() and fp.stat().st_size > 0):
                    missing_before.append(r)

            pending = len(missing_before)
            already_done = total_rows - pending
            print(f"{CYAN}[fast]{RESET} Checking folder... done={already_done} pending={pending}")

            if pending > 0:
                print(f"{CYAN}[fast]{RESET} Downloading images (pending: {pending})...")
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    fcsv.run_download(manifest_path, out_dir, threads)
            else:
                print(f"{CYAN}[fast]{RESET} Nothing missing on disk. Skipping download.")

        except Exception as e:
            box([
                f"{BRIGHT}{RED}Fast CSV failed{RESET}",
                "",
                f"SET: {set_code}",
                f"Error: {e}",
            ], color=RED)

            again = input("\nDownload another set? (y/N): ").strip().lower()
            if again in {"y", "yes"}:
                continue
            return

        elapsed = _time.time() - start

        # -------- Final summary --------
        missing_after = []
        for r in rows:
            fp = out_dir / r.target_filename
            if not (fp.exists() and fp.stat().st_size > 0):
                missing_after.append(r)

        done_total = total_rows - len(missing_after)
        downloaded_new = max(0, done_total - already_done)
        skipped = already_done

        errors = 0
        try:
            state_path = manifest_path.with_suffix(".state.jsonl")
            state_map = fcsv.load_state_done(state_path)
            errors = sum(1 for v in state_map.values() if str(v).lower() == "failed")
        except Exception:
            errors = 0

        avg_speed = (downloaded_new / elapsed) if elapsed > 0 else 0.0

        lines = [
            f"{BRIGHT}SET{RESET} {set_code} {BRIGHT}completed{RESET}.",
            f"Search results (records/prints): {CYAN}{total_regs}{RESET}",
            f"Scryfall reference size: {CYAN}{expected}{RESET}",
            f"Images downloaded (includes faces/flip): {GREEN}{done_total}{RESET}",
            f"Skipped: {YELLOW}{skipped}{RESET}",
            f"Errors: {RED}{errors}{RESET}",
            f"Elapsed time: {CYAN}{format_duration(elapsed)}{RESET}",
            f"Average speed: {CYAN}{avg_speed:.2f} images/s{RESET}",
            f"Folder: {CYAN}{out_dir}{RESET}",
        ]
        box(lines, color=GREEN)

        again = input("\nDownload another set? (y/N): ").strip().lower()
        if again in {"y", "yes"}:
            continue
        return


# ---------- UtilHelper Menu ----------

def prompt_yes_no(question: str, default_no: bool = True) -> bool:
    """
    Yes/No prompt.
    ENTER = No (default) when default_no=True.
    Returns True for Yes, False for No.
    """
    while True:
        suf = "[y/N]" if default_no else "[Y/n]"
        ans = input(BRIGHT + f"{question} {suf}: " + RESET).strip().lower()
        if not ans:
            return not default_no
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        print(RED + "Invalid option. Please type Y or N." + RESET)


def filter_sets(query: str, sets_meta: list[dict]) -> list[dict]:
    """
    Searches for a set by code or name (case-insensitive).
    - Exact code match (3–5 letters) has priority
    - Otherwise, fallback to partial name match
    """
    q = query.strip().lower()
    if not q:
        return []
    exact = [s for s in sets_meta if (s.get("code") or "").lower() == q]
    if exact:
        return exact
    by_name = [s for s in sets_meta if q in (s.get("name") or "").lower()]
    return by_name

def prompt_specific_set(sets_meta: list[dict]) -> dict | None:
    """
    UI helper to select a set by code or name.
    - Empty ENTER does not continue
    - [B] = go back to the previous menu
    - If multiple matches exist, displays a list for selection
    - Asks for confirmation before starting the download
    Returns:
        dict for the selected set, or None if the user goes back.
    """
    while True:
        box([
            f"{BRIGHT}Download a specific SET{RESET}",
            "",
            "Type the SET code or part of the name.",
            f"Examples: {CYAN}one{RESET}, {CYAN}m21{RESET}, {CYAN}Quarta Edição{RESET}",
            "",
            f"{YELLOW}[B]{RESET} Back to Main Menu",
        ], color=CYAN)

        q = input(BRIGHT + "Your input: " + RESET).strip()
        if not q:
            print(RED + "Please type a set code or name (or 'B' to go back)." + RESET)
            continue
        if q.lower() in {"b", "back"}:
            return None

        matches = filter_sets(q, sets_meta)
        if not matches:
            print(RED + "No sets matched your query. Try again." + RESET)
            continue

        # If various, ask to choose
        if len(matches) > 1:
            lines = [f"{BRIGHT}Multiple matches found{RESET}", ""]
            for i, s in enumerate(matches, start=1):
                code = (s.get("code") or "").upper()
                name = s.get("name") or "Unknown"
                rel = s.get("released_at") or ""
                lines.append(f"{i:>2}) {name}  [{code}]  {rel}")
            lines.append("")
            lines.append("Type the number you want, or B to go back.")
            box(lines, color=PINK)

            while True:
                pick = input(BRIGHT + "Choose [#] or B: " + RESET).strip().lower()
                if pick in {"b", "back"}:
                    break  # Ask again - Back to choose
                if pick.isdigit():
                    idx = int(pick)
                    if 1 <= idx <= len(matches):
                        chosen = matches[idx - 1]
                        # Confirmation
                        code = (chosen.get("code") or "").upper()
                        name = chosen.get("name") or "Unknown"
                        box([
                            f"{BRIGHT}Confirm download{RESET}",
                            "",
                            f"{name}  [{CYAN}{code}{RESET}]",
                            "",
                            "Start download now?"
                        ], color=CYAN)
                        if prompt_yes_no("Proceed", default_no=True):
                            return chosen
                        else:
                            break  # Query Input
                print(RED + "Invalid choice." + RESET)
            continue  # Back to Query Input

        # Only one match
        chosen = matches[0]
        code = (chosen.get("code") or "").upper()
        name = chosen.get("name") or "Unknown"

        # Try to search complete meta from choosen
        set_type = chosen.get("set_type") or ""
        rel = chosen.get("released_at") or ""
        expected = chosen.get("card_count") or chosen.get("printed_size") or ""

        # fallback: search sets_meta
        if not (set_type and rel and expected):
            try:
                meta_full = next(
                    (s for s in sets_meta if (s.get("code") or "").lower() == (chosen.get("code") or "").lower()),
                    {}
                )
                if not set_type:
                    st = meta_full.get("set_type") or ""
                    set_type = st.replace("_", " ").title() if st else ""
                else:
                    set_type = set_type.replace("_", " ").title()

                if not rel:
                    rel = meta_full.get("released_at") or ""

                if not expected:
                    expected = meta_full.get("card_count") or meta_full.get("printed_size") or ""
            except Exception:
                pass

        # Standard values if missmatch
        set_type = set_type.replace("_", " ").title() if set_type else "—"
        rel = rel or "—"
        expected = expected or "—"

        # Real print quantity
        try:
            total_regs, _ = scry_search_cards_for_set_cached(chosen["code"])
        except Exception:
            total_regs = "—"

        box([
            f"{BRIGHT}Confirm download{RESET}",
            "",
            f"{name}  [{CYAN}{code}{RESET}]",
            f"Type: {set_type}   Release: {rel}",
            f"Scryfall reference size: {CYAN}{expected}{RESET}",
            f"Search results (prints): {CYAN}{total_regs}{RESET}",
            "",
            "Start download now?"
        ], color=CYAN)

        if prompt_yes_no("Proceed", default_no=True):
            return chosen
        # # Otherwise, restart the loop for a new search

# ---------- Prompts / Flow ----------

def prompt_base_dir() -> Path:
    default_dir = script_root_cards()

    # Download Message Directory Box
    box([
        f"{BRIGHT}Cards Download Directory{RESET}",
        "",
        "This folder will store all downloaded SETs, including",
        "each set’s subfolder and all card images.",
        "",
        f"{CYAN}{default_dir}{RESET}",
        "",
        "Press ENTER to use this folder, or choose an option below:"
    ], color=PINK)

    print(f"{BRIGHT}Change base directory?{RESET}")
    print(f"  {GREEN}[Y]{RESET} Yes, choose another folder")
    print(f"  {YELLOW}[N]{RESET} No, continue with default (recommended)")
    print("")

    change = input("Option (Y/N): ").strip().lower()
    if change in {"y", "yes"}:
        custom = input("Enter new directory: ").strip()
        base = Path(custom)
    else:
        base = default_dir

    ensure_dir(base)
    return base

from pathlib import Path

def tokens_menu(base_dir: Path):
    if dt is None:
        box(["Token module (DToken.py) was not found."], color=RED)
        return

    # Tokens folder: base_dir = ...\Cards
    tokens_dir = base_dir.parent / "Tokens"
    tokens_dir.mkdir(parents=True, exist_ok=True)

    # Redirects the output root of the DToken module
    dt.TOKENS_DIR = tokens_dir

    # Single option: process Audit.txt
    box([
        f"{BRIGHT}TOKEN Downloader{RESET}",
        "",
        "This flow downloads ONLY TOKENS from:",
        f"{CYAN}Audit.txt{RESET} (auto-created if missing)",
        "",
        "Output folder:",
        f"{CYAN}{tokens_dir}{RESET}",
        "",
        "Press ENTER to continue or 'B' to go back."
    ], color=CYAN)

    ans = input("Your choice: ").strip().lower()
    if ans in {"b", "back"}:
        return

    # DToken flow execution
    dt.download_tokens_from_audit()

    input("\nPress ENTER to return to the main menu...")

# ---------- SINGLES ----------
def singles_menu(base_dir: Path):
    """
    Submenu to download individual cards (ONE or ALL prints) via SingleCard.py.
    - Output folder: ..\\Singles (sibling of ..\\Cards)
    """
    if sc is None:
        print("SingleCard module (SingleCard.py) not found in the same folder. Please place it next to this script.")
        return

    # Where to save the singles? (sibling of the Cards folder)
    singles_dir = base_dir.parent / "Singles"
    singles_dir.mkdir(parents=True, exist_ok=True)

    # Rredirect SingleCard module "singles_root" to our integrated folder
    try:
        sc.singles_root = lambda: singles_dir
    except Exception:
        pass

    # Open SingleCard module menu (UI to search name, list prints, choose ONE/ALL)
    sc.singlecard_menu(base_dir)

def fastcsv_all_sets_menu(base_dir: Path):
    """
    Fast CSV ALL SETs — Experimental
    Builds per-set manifests and downloads via CDN with resume.
    """
    if fcsv is None:
        box(["fast_csv_set.py module not found next to this script."], color=RED)
        input("\nPress ENTER to return to the main menu...")
        return

    sets_meta = get_all_sets()

    # -------- Scope mini-menu --------
    box([
        f"{BRIGHT}Fast CSV — ALL SETs scope{RESET}",
        "",
        f"{CYAN}1){RESET} Absolutely ALL sets (includes tokens, minigames, memorabilia, etc.)",
        f"{CYAN}2){RESET} All except tokens",
        f"{CYAN}3){RESET} Curated (recommended) — playable/normal sets only",
        f"{CYAN}4){RESET} Back to main menu"
    ], color=CYAN)

    while True:
        scope = input(BRIGHT + "Your choice [1-4]: " + RESET).strip()
        if scope in {"1", "2", "3", "4"}:
            break
        print(RED + "Invalid option, try again." + RESET)

    if scope == "4":
        return

    curated_types = {
        "core", "expansion", "masters", "eternal", "draft_innovation",
        "funny", "starter", "commander", "planechase",
        "archenemy", "duel_deck", "arsenal", "spellbook",
        "from_the_vault", "premium_deck", "masterpiece", "promo"
    }

    if scope == "1":
        filt = lambda s: True
        scope_label = "ALL (everything)"
    elif scope == "2":
        filt = lambda s: (s.get("set_type") != "token")
        scope_label = "All except tokens"
    else:
        filt = lambda s: (s.get("set_type") in curated_types)
        scope_label = "Curated (recommended)"

    selected = [s for s in sets_meta if filt(s)]
    selected.sort(key=lambda x: x.get("released_at") or "1900-01-01")

    box([
        f"{BRIGHT}Fast CSV — ALL SETs (preview){RESET}",
        "",
        f"Selected scope: {CYAN}{scope_label}{RESET}",
        f"Total sets selected: {CYAN}{len(selected)}{RESET}",
        "",
        f"{YELLOW}Heads up:{RESET} this can still take a long time depending on your disk/network.",
        "Resume is supported per-set (safe to stop and rerun).",
    ], color=YELLOW)

    if not prompt_yes_no("Start Fast CSV batch now", default_no=True):
        return

    # -------- Threads (single choice for the whole batch) --------
    box([
        f"{BRIGHT}Concurrency (threads){RESET}",
        "",
        f"Default: {CYAN}24{RESET} (recommended)",
        "Higher values = faster downloads",
        "Lower values = more stable on slow/unstable connections",
        "",
        "Press ENTER to use the default.",
    ], color=YELLOW)

    raw = input(BRIGHT + "Threads: " + RESET).strip()
    try:
        threads = int(raw) if raw else 24
        threads = max(1, min(256, threads))
    except Exception:
        threads = 24

    # -------- Folder policy --------
    box([
        f"{BRIGHT}Folder handling for this Fast CSV batch{RESET}",
        "",
        "For every SET:",
        f"  {CYAN}1){RESET} Keep existing files (recommended / fastest)",
        f"  {RED}2){RESET} Clean each SET folder before downloading (redownload everything)",
        f"  {CYAN}3){RESET} Back to main menu"
    ], color=CYAN)

    while True:
        mode = input(BRIGHT + "Choose an option [1-3]: " + RESET).strip()
        if mode in {"1", "2", "3"}:
            break
        print(RED + "Invalid option, try again." + RESET)

    if mode == "3":
        return

    clean_each = (mode == "2")

    # -------- Batch loop --------
    total_sets = len(selected)
    ok_sets = 0
    fail_sets = 0


    import io, contextlib, time as _time

    root = base_dir.parent  # IMPORTANT: keep same contract as fastcsv_set_menu
    for i, s in enumerate(selected, 1):
        code = str(s.get("code") or "").upper()
        name = str(s.get("name") or "Unknown")
        released = s.get("released_at") or "—"
        set_type = (s.get("set_type") or "—").replace("_", " ").title()
        expected = s.get("card_count") or s.get("printed_size") or "—"

        # Search results (prints)
        try:
            total_regs, _ = scry_search_cards_for_set_cached(s.get("code") or "")
        except Exception:
            total_regs = "—"

        # Paths (manifest + output)
        manifest_path, out_dir = fcsv.default_paths(root, code)

        # Build/Read manifest (count rows)
        buf = io.StringIO()
        start = _time.time()

        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            manifest_path.parent.mkdir(parents=True, exist_ok=True)

            if not manifest_path.exists():
                print(f"\n{CYAN}[fastcsv]{RESET} Building manifest for {code}...")
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    rows = fcsv.build_manifest_for_set(code, manifest_path)
            else:
                rows = fcsv.read_manifest_csv(manifest_path)

            total_rows = len(rows)

            # Pending = missing files
            missing_before = []
            for r in rows:
                fp = out_dir / r.target_filename
                if not (fp.exists() and fp.stat().st_size > 0):
                    missing_before.append(r)

            pending = len(missing_before)
            already_done = total_rows - pending

            # ---- Yellow "run starting" banner (same style as single) ----
            box([
                f"{BRIGHT}Fast CSV run starting{RESET}",
                "",
                f"{name}  [{CYAN}{code}{RESET}]",
                f"Type: {set_type}   Release: {released}",
                f"Search results (records/prints): {CYAN}{total_regs}{RESET}",
                f"Scryfall reference size: {CYAN}{expected}{RESET}",
                "",
                f"Threads: {CYAN}{threads}{RESET}",
                f"Manifest: {CYAN}{manifest_path.name}{RESET}  ({CYAN}{total_rows}{RESET} rows)",
                f"Folder:   {CYAN}{out_dir}{RESET}",
            ], color=YELLOW)

            print(f"{CYAN}[fastcsv]{RESET} Checking folder... done={already_done} pending={pending}")

            # Optional clean (if user chose clean_each)
            if clean_each and out_dir.exists():
                try:
                    shutil.rmtree(out_dir)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    # after cleaning, everything becomes pending
                    pending = total_rows
                    already_done = 0
                    print(f"{YELLOW}[fastcsv]{RESET} Folder cleaned. pending={pending}")
                except Exception as e:
                    print(RED + f"[fastcsv] Could not clean folder {out_dir}: {e}" + RESET)

            # Download if needed (quiet mode)
            if pending > 0:
                print(f"{CYAN}[fastcsv]{RESET} Downloading images (pending: {pending})...")
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    fcsv.run_download(manifest_path, out_dir, threads=threads)
            else:
                print(f"{CYAN}[fastcsv]{RESET} Nothing missing on disk. Skipping download.")

        except Exception as e:
            fail_sets += 1
            box([
                f"{BRIGHT}{RED}Fast CSV failed{RESET}",
                "",
                f"SET: {code} — {name}",
                f"Error: {e}",
                "",
                f"Manifest: {manifest_path}",
                f"Folder:   {out_dir}",
            ], color=RED)
            time.sleep(0.5)
            continue

        elapsed = _time.time() - start

        # ---- Final summary per set (green box like single) ----
        try:
            # recompute missing after
            missing_after = []
            for r in rows:
                fp = out_dir / r.target_filename
                if not (fp.exists() and fp.stat().st_size > 0):
                    missing_after.append(r)

            done_total = total_rows - len(missing_after)
            downloaded_new = max(0, done_total - already_done)
            skipped = already_done  # what was already on disk before this run

            errors = 0
            try:
                state_path = manifest_path.with_suffix(".state.jsonl")
                state_map = fcsv.load_state_done(state_path)
                errors = sum(1 for v in state_map.values() if str(v).lower() == "failed")
            except Exception:
                errors = 0

            avg_speed = (downloaded_new / elapsed) if elapsed > 0 else 0.0

            box([
                f"{BRIGHT}SET{RESET} {code} {BRIGHT}completed{RESET}.",
                f"Search results (records/prints): {CYAN}{total_regs}{RESET}",
                f"Scryfall reference size: {CYAN}{expected}{RESET}",
                f"Images downloaded (includes faces/flip): {GREEN}{done_total}{RESET}",
                f"Skipped: {YELLOW}{skipped}{RESET}",
                f"Errors: {RED}{errors}{RESET}",
                f"Elapsed time: {CYAN}{format_duration(elapsed)}{RESET}",
                f"Average speed: {CYAN}{avg_speed:.2f} images/s{RESET}",
                f"Folder: {CYAN}{out_dir}{RESET}",
            ], color=GREEN)

            ok_sets += 1

        except Exception as e:
            # even if summary fails, don't kill batch
            ok_sets += 1
            print(YELLOW + f"[fastcsv] Summary warning for {code}: {e}" + RESET)

        # gentle pause between sets
        time.sleep(0.5)

    box([
        f"{BRIGHT}Fast CSV — ALL SETs completed{RESET}",
        "",
        f"Scope: {CYAN}{scope_label}{RESET}",
        f"Threads: {CYAN}{threads}{RESET}",
        f"Sets finished: {CYAN}{ok_sets}{RESET}",
        f"Sets failed: {RED}{fail_sets}{RESET}",
        "",
        "You can rerun this anytime — it will resume per-set.",
    ], color=GREEN if fail_sets == 0 else YELLOW)

    input("\nPress ENTER to return to the main menu...")


def prompt_main_menu() -> str:
    lines = [
        f"{BRIGHT}Main Menu{RESET}",
        "",
        f"{BRIGHT}{CYAN}SET downloads{RESET}",
        f"{CYAN} 1){RESET} Download a specific SET   {YELLOW}(recommended){RESET}",
        f"{CYAN} 2){RESET} Download ALL SETs         {YELLOW}(big / slower){RESET}",
        f"{CYAN} 3){RESET} Download SETs from Sets.txt",
        "",
        f"{BRIGHT}{CYAN}Tools{RESET}",
        f"{CYAN} 4){RESET} Download TOKENS from Forge Audit   {YELLOW}(tokens only){RESET}",
        f"{CYAN} 5){RESET} Download Singles (one card / all prints)",
        f"{CYAN} 6){RESET} Download CARDS from Forge Audit    {YELLOW}(not tokens){RESET}",
        "",
        f"{BRIGHT}{CYAN}Advanced{RESET}",
        f"{CYAN} 7){RESET} {YELLOW}[Experimental]{RESET} Printed/Flavor-name SET downloader  {YELLOW}(SLD-friendly){RESET}",
        f"{CYAN} 8){RESET} {YELLOW}[Experimental]{RESET} Fast SET downloader  {YELLOW}(ultra fast / resume){RESET}",
        f"{CYAN} 9){RESET} {YELLOW}[Experimental]{RESET} Fast ALL SETs  {YELLOW}(ultra fast / resume){RESET}",
        "",
        f"{CYAN} 0){RESET} Exit",
        "",
    ]

    box(lines, color=CYAN)

    shortcuts = {
        "s": "1",
        "a": "2",
        "t": "4",
        "p": "5",
        "q": "0",
        "x": "0",
    }

    valid = {str(i) for i in range(0, 10)}

    while True:
        raw = input(BRIGHT + "Your choice [0-9]: " + RESET).strip().lower()

        if raw in shortcuts:
            return shortcuts[raw]

        if raw in valid:
            return raw

        print(
            f"{RED}Invalid option.{RESET} "
            f"{YELLOW}Use 0–9 or shortcuts:{RESET} "
            f"{CYAN}s{RESET}=SET, "
            f"{CYAN}a{RESET}=ALL, "
            f"{CYAN}t{RESET}=TOKENS, "
            f"{CYAN}p{RESET}=SINGLES, "
            f"{CYAN}q{RESET}=EXIT (0)."
        )


def prompt_set_code(sets_meta: List[dict]) -> dict:
    while True:
        s = input("Type SET code or name (e.g., 10E, 4ed, 'Quarta Edição'): ").strip()
        match = fuzzy_match_set(s, sets_meta)
        if match:
            print(GREEN + f"✔ {match['name']} [{(match.get('code') or '').upper()}]" + RESET)
            return match
        print(RED + "SET not found. Try again." + RESET)

def prompt_existing_set_dir_action(set_dir: Path) -> Optional[str]:
    """
    Returns:
      - 'skip'       => keep files and skip existing ones
      - 'overwrite'  => overwrite existing files
      - 'clean'      => wipe folder and redownload
      - None         => back to main menu
    """
    box([
        "SET folder already exists:",
        f"{set_dir}",
        "",
        "Choose an action:",
        f"  {GREEN}1){RESET} Keep and skip existing files (fastest)",
        f"  {YELLOW}2){RESET} Overwrite existing files",
        f"  {RED}3){RESET} Clean folder and redownload",
        f"  {CYAN}4){RESET} Back to Main Menu",
    ], color=YELLOW)

    while True:
        c = input(BRIGHT + "Choose an option [1-4]: " + RESET).strip()
        if c == "1":
            return "skip"
        if c == "2":
            return "overwrite"
        if c == "3":
            confirm = input(
                BRIGHT + YELLOW +
                "This will DELETE all files in this set folder. Proceed? [y/N]: " +
                RESET
            ).strip().lower()
            if confirm in {"y", "yes"}:
                return "clean"
            else:
                print(YELLOW + "Cancelled clean. Please choose another option." + RESET)
                continue
        if c == "4":
            return None
        print(RED + "Invalid option. Please enter 1, 2, 3 or 4." + RESET)

# ---------- Sets.txt Batch  ----------

def load_sets_from_file(sets_meta: List[dict], file_path: Path) -> Tuple[List[dict], List[str]]:
    """
    Read file with one set per line (code or name),
    resolve via fuzzy match and return (found, not_found).
    Blank lines and lines starting with # are ignored.
    """
    found: List[dict] = []
    not_found: List[str] = []
    if not file_path.exists():
        return found, ["[FILE NOT FOUND] " + str(file_path)]

    lines = file_path.read_text(encoding="utf-8").splitlines()
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        m = fuzzy_match_set(s, sets_meta)
        if m:
            found.append(m)
        else:
            not_found.append(s)
    # dedupe preserving order
    seen = set()
    unique_found = []
    for m in found:
        code = (m.get("code") or "").lower()
        if code not in seen:
            unique_found.append(m)
            seen.add(code)
    return unique_found, not_found


# ---------- Core per SET ----------

def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s:02d}s"

def scry_search_cards_for_set_cached(set_meta_code: str) -> Tuple[int, List[dict]]:
    # helper if you ever want to cache; for now just passthrough
    cards = scry_search_cards_for_set(set_meta_code)
    return len(cards), cards

def download_set(set_meta: dict, base_dir: Path, exist_mode: str = "skip") -> None:
    set_code = (set_meta.get("code") or "").upper()
    set_dir = base_dir / safe_set_folder_name(set_code)
    ensure_dir(set_dir)

    # Existing folder policy
    if any(set_dir.iterdir()):
        if exist_mode == "clean":
            clear_directory(set_dir)
            print(YELLOW + "Folder cleaned." + RESET)

    # Reference + timer
    start_time = time.time()
    ref_meta = get_set_meta(set_meta["code"])
    expected_prints = ref_meta.get("card_count") or ref_meta.get("printed_size")

    total_regs, cards = scry_search_cards_for_set_cached(set_meta["code"])

    name_counts: Dict[str, int] = {}
    downloaded = 0
    skipped = 0
    errors = 0

    log_path = set_dir / f"errors_{set_code}.log"
    log = []

    tqdm_desc = f"[{set_code}] downloading"
    pbar = tqdm(
        cards,
        desc=tqdm_desc,
        unit="card",
        dynamic_ncols=True,
        bar_format="{l_bar}{bar} {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] | {postfix}"
    )
    for card in pbar:

        # Short cards name beside download bar
        label = (card.get("name") or "").replace("\n", " ").strip()
        if label:
            colored = f"{PINK}{label[:40]}{RESET}"
            pbar.set_postfix_str(colored)
            
        entries = pick_image_entries(card)
        if not entries:
            skipped += 1
            log.append(f"[NO_IMAGE] {card.get('name','Unknown')} ({card.get('id')})")
            continue

        for entry in entries:
            base_name = slugify_filename(entry.name)
            ext = infer_ext_from_url(entry.url)

            count_key = base_name
            cnt = name_counts.get(count_key, 0) + 1
            name_counts[count_key] = cnt
            suffix = "" if cnt == 1 else str(cnt)
            final_name = f"{base_name}{suffix}.fullborder{ext}"

            out_path = set_dir / final_name

            if out_path.exists():
                if exist_mode == "overwrite":
                    pass
                else:
                    skipped += 1
                    continue

            try:
                content = download_bytes_with_retry(entry.url)

                save_image(
                    content,
                    out_path,
                    card=card,
                    rotate_mode=entry.rotate
                )
                downloaded += 1

            except requests.exceptions.HTTPError as ex:
                errors += 1
                status = ex.response.status_code if ex.response is not None else "?"
                log.append(f"[HTTP {status}] {entry.name} -> {entry.url} :: {ex}")

            except Exception as ex:
                errors += 1
                log.append(f"[EXCEPTION] {entry.name} -> {entry.url} :: {ex}")

    pbar.close()

    # --- Reserved set folder promotion (_CON -> CON) ---
    promoted, promo_msg = promote_reserved_set_folder(base_dir, set_code)

    # If promoted, update set_dir so the summary shows the final folder
    if promoted:
        set_dir = base_dir / set_code
        log_path = set_dir / f"errors_{set_code}.log"  # keep path consistent for final output

    elapsed = time.time() - start_time
    avg_speed = downloaded / elapsed if elapsed > 0 else 0.0

    if log:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("\n".join(log))

    lines = [
        f"{BRIGHT}SET{RESET} {set_code} {BRIGHT}completed{RESET}.",
        f"Search results (records/prints): {CYAN}{total_regs}{RESET}",
        f"Scryfall reference size: {CYAN}{expected_prints if expected_prints else '—'}{RESET}",
        f"Images downloaded (includes faces/flip): {GREEN}{downloaded}{RESET}",
        f"Skipped: {YELLOW}{skipped}{RESET}",
        f"Errors: {RED}{errors}{RESET}",
        f"Elapsed time: {CYAN}{format_duration(elapsed)}{RESET}",
        f"Average speed: {CYAN}{avg_speed:.2f} images/s{RESET}",
        (f"Error log: {log_path}" if log else "No errors recorded."),
        f"Folder: {set_dir}",
        (f"Reserved-name handling: {promo_msg}" if is_windows_reserved_set_code(set_code) else "Reserved-name handling: —"),
    ]
    box(lines, color=GREEN)

# ---------- Main flow ----------

def main():
    banner()
    sets_meta = get_all_sets()
    base_dir = prompt_base_dir()

    while True:
        choice = prompt_main_menu()
        if choice == "0":
            box([
                f"{BRIGHT}Scryfall Scrapper — Session Ended{RESET}",
                "",
                f"{CYAN}May your pulls be mythic and your downloads flawless.{RESET}",
                "",
                f"{PINK}@Laryzinha{RESET}"
            ], color=PINK)
            break

        if choice == "1":
            # Specific set (Return and COnfirm)
            while True:
                chosen = prompt_specific_set(sets_meta)
                if chosen is None:
                    # User press [B] go back to main menu
                    break

                set_code = (chosen.get("code") or "").upper()
                set_dir = base_dir / safe_set_folder_name(set_code)
                ensure_dir(set_dir)

                exist_mode = "skip"
                if any(set_dir.iterdir()):
                    exist_mode = prompt_existing_set_dir_action(set_dir)

                # IF back with none, back to menu without download
                if exist_mode is None:
                    break

                download_set(chosen, base_dir, exist_mode=exist_mode)

                again = input("Download another set? (y/N): ").strip().lower()
                if again not in {"y", "yes"}:
                    break
            continue

        elif choice == "2":
            # === ALL SETs (scope selection, preview, confirmation, folder policy) ===

            # Mini-menu de escopo
            box([
                f"{BRIGHT}Select ALL-SETs scope{RESET}",
                "",
                f"{CYAN}1){RESET} Absolutely ALL sets (includes tokens, minigames, memorabilia, etc.)",
                f"{CYAN}2){RESET} All except tokens",
                f"{CYAN}3){RESET} Curated (recommended) — playable/normal sets only",
                f"{CYAN}4){RESET} Back to main menu"
            ], color=CYAN)

            while True:
                scope = input(BRIGHT + "Your choice [1-4]: " + RESET).strip()
                if scope in {"1", "2", "3", "4"}:
                    break
                print(RED + "Invalid option, try again." + RESET)

            if scope == "4":
                continue  # volta ao menu principal

            # Tipos oficiais da Scryfall
            # (mantemos aqui por clareza; não filtramos por 'all_types' diretamente)
            curated_types = {
                "core", "expansion", "masters", "eternal", "draft_innovation",
                "funny", "starter", "commander", "planechase",
                "archenemy", "duel_deck", "arsenal", "spellbook",
                "from_the_vault", "premium_deck", "masterpiece", "promo"
            }

            if scope == "1":
                filt = lambda s: True  # absolutamente tudo
                scope_label = "ALL (everything)"
            elif scope == "2":
                filt = lambda s: (s.get("set_type") != "token")
                scope_label = "All except tokens"
            else:  # scope == "3"
                filt = lambda s: (s.get("set_type") in curated_types)
                scope_label = "Curated (recommended)"

            # Seleção + ordenação por data
            all_sets = [s for s in sets_meta if filt(s)]
            all_sets.sort(key=lambda x: x.get("released_at") or "1900-01-01")

            # Preview antes de baixar
            preview_lines = [f"{BRIGHT}ALL SETs — batch run{RESET}", ""]
            preview_lines.append(f"Selected scope: {CYAN}{scope_label}{RESET}")
            preview_lines.append(f"Total sets selected: {CYAN}{len(all_sets)}{RESET}")
            preview_lines.append("")
            preview_lines.append("Heads up: this may take a long time.")
            box(preview_lines, color=YELLOW)

            # Confirmação para começar
            if not prompt_yes_no("Start batch download now", default_no=True):
                continue

            # Política para pastas existentes
            box([
                f"{BRIGHT}Folder handling for this batch{RESET}",
                "",
                "For every SET in this ALL batch:",
                f"  {GREEN}1){RESET} Keep existing files and skip duplicates (fastest)",
                f"  {YELLOW}2){RESET} Overwrite existing files",
                f"  {RED}3){RESET} Clean the folder completely and redownload",
                f"  {CYAN}4){RESET} Back to Main Menu"
            ], color=CYAN)

            back_to_menu = False
            exist_mode = None

            while True:
                c = input(BRIGHT + "Choose an option [1-4]: " + RESET).strip()
                if c == "1":
                    exist_mode = "skip"; break
                elif c == "2":
                    exist_mode = "overwrite"; break
                elif c == "3":
                    confirm = input(
                        BRIGHT + YELLOW +
                        "This will DELETE all files in each set folder before downloading. Proceed? [y/N]: " +
                        RESET
                    ).strip().lower()
                    if confirm in {"y", "yes"}:
                        exist_mode = "clean"; break
                    else:
                        print(YELLOW + "Cancelled clean. Please choose another option." + RESET)
                        continue
                elif c == "4":
                    back_to_menu = True; break
                else:
                    print(RED + "Invalid option. Please enter 1, 2, 3 or 4." + RESET)

            if back_to_menu:
                continue

            # Loop dos sets — NÃO deixa o batch morrer + pausa entre sets
            for sm in all_sets:
                code = (sm.get("code") or "").upper()
                set_name = sm.get("name", "Unknown")

                # IMPORTANT: use Windows-safe folder name (CON, PRN, AUX, etc.)
                safe_code = safe_set_folder_name(code)
                set_dir = base_dir / safe_code
                ensure_dir(set_dir)

                print(f"\n>>> {set_name} [{code}] <<<")

                try:
                    download_set(sm, base_dir, exist_mode=exist_mode)
                except Exception as e:
                    # não mata o batch por causa de 1 set (rede, 429, reset, etc.)
                    box([
                        f"{BRIGHT}{YELLOW}SET skipped due to network/error{RESET}",
                        f"Set: {code} — {set_name}",
                        f"Error: {e}"
                    ], color=YELLOW)

                    # log simples (opcional)
                    try:
                        with open(base_dir / "batch_errors.log", "a", encoding="utf-8") as f:
                            f.write(f"{code} :: {set_name} :: {repr(e)}\n")
                    except Exception:
                        pass

                # pausa curtinha entre sets (reduz WinError 10054 em execução longa)
                time.sleep(SET_PAUSE)


            # Pós-batch: oferecer ir ao modo específico (mesma experiência das outras opções)
            again = input("Switch to specific-set mode now? (y/N): ").strip().lower()
            if again in {"y", "yes"}:
                while True:
                    set_meta = prompt_set_code(sets_meta)
                    set_dir = base_dir / safe_set_folder_name((set_meta.get("code") or "UNK"))
                    ensure_dir(set_dir)
                    exist_mode2 = "skip"
                    if any(set_dir.iterdir()):
                        exist_mode2 = prompt_existing_set_dir_action(set_dir)
                    download_set(set_meta, base_dir, exist_mode=exist_mode2)

                    again2 = input("Download another set? (y/N): ").strip().lower()
                    if again2 not in {"y", "yes"}:
                        break


        elif choice == "3":
            # === Batch via Sets.txt (UX melhorada) ===
            default_path = (Path(__file__).resolve().parent / "Sets.txt") if '__file__' in globals() else (Path.cwd() / "Sets.txt")

            box([
                "Path to Sets.txt (PRESS ENTER for default):",
                f"{default_path}"
            ], color=PINK)
            p = input(BRIGHT + "Enter path to Sets.txt (or press ENTER for default): " + RESET).strip()
            file_path = Path(p) if p else default_path

            # 1) Se NÃO existir, cria com um template amigável e orienta o usuário
            if not file_path.exists():
                try:
                    template = "\n".join([
                        "# One set per line. You can use set code or part of the name.",
                        "# Lines starting with # are ignored.",
                        "# Examples:",
                        "# 40K",
                        "# Ninth Edition",
                        "# Arena Anthology 2",
                        "# aAa1   (codes and names are fuzzy-matched)",
                        "",
                    ])
                    file_path.write_text(template, encoding="utf-8")
                    box([
                        f"'{file_path.name}' was not found, so a template was created here:",
                        f"{file_path}",
                        "",
                        "Add your sets (one per line) and run this option again."
                    ], color=YELLOW)
                except Exception as ex:
                    box([
                        "Could not create the file:",
                        f"{file_path}",
                        f"Error: {ex}"
                    ], color=RED)
                input("\nPress ENTER to return to the main menu...")
                continue

            # 2) Arquivo existe: ler conteúdo cru para decidir o fluxo
            raw_lines = file_path.read_text(encoding="utf-8").splitlines()
            # Conteúdo útil (sem linhas vazias/comentários)
            effective_lines = [ln.strip() for ln in raw_lines if ln.strip() and not ln.strip().startswith("#")]

            # 2.a) Se vazio: orientar e voltar
            if not effective_lines:
                box([
                    "Sets.txt is empty or only has comments.",
                    "",
                    "How to fill it:",
                    f" - One set per line (code or name), e.g.:",
                    f"   40K",
                    f"   Ninth Edition",
                    f"   Arena Anthology 2",
                    "",
                    f"File: {file_path}"
                ], color=YELLOW)
                input("\nAdd some sets and press ENTER to return to the main menu...")
                continue

            # 3) Perguntar se deseja seguir com a listagem encontrada
            preview = [f"{BRIGHT}We found {len(effective_lines)} line(s) in Sets.txt{RESET}", ""]
            # Mostra até 10 exemplos para não poluir
            for i, ln in enumerate(effective_lines[:10], start=1):
                preview.append(f"{i:>2}) {ln}")
            if len(effective_lines) > 10:
                preview.append(f"... (+{len(effective_lines)-10} more)")

            preview.append("")
            preview.append("Proceed using this file?")
            box(preview, color=CYAN)

            if not prompt_yes_no("Proceed", default_no=True):
                input("\nNo problem. Press ENTER to return to the main menu...")
                continue

            # 4) Resolver sets (fuzzy) e validar
            found, missing = load_sets_from_file(sets_meta, file_path)

            if not found and missing:
                box(["No sets resolved. Check these lines:"] + [f"- {m}" for m in missing], color=RED)
                input("\nFix the file and press ENTER to return to the main menu...")
                continue
            elif not found:
                box(["Sets.txt is empty or invalid."], color=RED)
                input("\nFix the file and press ENTER to return to the main menu...")
                continue

            # 5) Preview de sets resolvidos + os não resolvidos
            box([f"Resolved sets ({len(found)}):"] + [f"- {m['name']} [{(m.get('code') or '').upper()}]" for m in found], color=CYAN)
            if missing:
                box(["Not resolved (check spelling or use codes):"] + [f"- {m}" for m in missing], color=YELLOW)
            print("")

            # 6) Política de pasta (com Back)
            box([
                f"{BRIGHT}Folder handling for this batch{RESET}",
                "",
                "For each SET listed above:",
                f"  {GREEN}1){RESET} Keep existing files and skip duplicates (fastest)",
                f"  {YELLOW}2){RESET} Overwrite existing files",
                f"  {RED}3){RESET} Clean the folder completely and redownload",
                f"  {CYAN}4){RESET} Back to Main Menu"
            ], color=CYAN)

            back_to_menu = False
            exist_mode = None

            while True:
                mode = input(BRIGHT + "Choose an option [1-4]: " + RESET).strip()
                if mode == "1":
                    exist_mode = "skip"; break
                elif mode == "2":
                    exist_mode = "overwrite"; break
                elif mode == "3":
                    confirm = input(BRIGHT + YELLOW + "This will DELETE all files in each set folder. Proceed? [y/N]: " + RESET).strip().lower()
                    if confirm in {"y", "yes"}:
                        exist_mode = "clean"; break
                    else:
                        print(YELLOW + "Cancelled clean. Please choose another option." + RESET)
                        continue
                elif mode == "4":
                    back_to_menu = True; break
                else:
                    print(RED + "Invalid option. Please enter 1, 2, 3 or 4." + RESET)

            if back_to_menu:
                continue

            # 7) Executa o batch
            for sm in found:
                set_code = (sm.get("code") or "").upper()
                set_dir = base_dir / safe_set_folder_name(set_code)
                ensure_dir(set_dir)

                print(f"\n>>> {sm.get('name','Unknown')} [{set_code}] <<<")
                download_set(sm, base_dir, exist_mode=exist_mode)

            # 8) Oferece ir para modo específico ao final (mesma experiência do seu fluxo)
            again = input("Switch to specific-set mode now? (y/N): ").strip().lower()
            if again in {"y", "yes"}:
                while True:
                    set_meta = prompt_set_code(sets_meta)
                    set_dir = base_dir / safe_set_folder_name((set_meta.get("code") or "UNK"))
                    ensure_dir(set_dir)
                    exist_mode2 = "skip"
                    if any(set_dir.iterdir()):
                        exist_mode2 = prompt_existing_set_dir_action(set_dir)
                    download_set(set_meta, base_dir, exist_mode=exist_mode2)

                    again2 = input("Download another set? (y/N): ").strip().lower()
                    if again2 not in {"y", "yes"}:
                        break

        elif choice == "4":
            tokens_menu(base_dir)

        elif choice == "5":
            singles_menu(base_dir)

        elif choice == "6":
            if ad is None:
                box(["AuditDownloader.py not found next to this script."], color=RED)
            else:
                box([
                    f"{BRIGHT}Forge Audit — CARDS by name/prints{RESET}",
                    "",
                    "This flow reads your Forge Audit and downloads CARD IMAGES by NAME",
                    "(oracle/printed/flavor), choosing specific prints when you suffix",
                    "with numbers (e.g., '...2', '...3').",
                    "",
                    f"{YELLOW}Note:{RESET} This is NOT for tokens. For TOKENS use menu option 4.",
                ], color=PINK)
                ad.audit_download_flow()
            input("\nDone. Press ENTER to return to the main menu...")

        elif choice == "7":
            box([
                f"{BRIGHT}Printed-Name SET Downloader — Experimental{RESET}",
                "",
                "This mode prioritizes printed / flavor names for filenames.",
                "Recommended for Secret Lair and special prints",
                "(e.g., 'Unlicensed Hearse' printed as 'Ecto-1').",
                "",
                f"{YELLOW}Heads up:{RESET} Filenames may differ from the standard SET downloader.",
                "Use this only when the normal SET download does not match printed names.",
            ], color=YELLOW)

            proceed = input(BRIGHT + "Open this mode now? [y/N]: " + RESET).strip().lower()
            if proceed not in {"y", "yes"}:
                continue

            printed_name_set_menu(base_dir)
            continue
        
        elif choice == "9":
            fastcsv_all_sets_menu(base_dir)
            continue

        elif choice == "8":
            fastcsv_set_menu(base_dir)
            continue


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
