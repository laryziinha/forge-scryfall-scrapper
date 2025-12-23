# ============================================================
#  Scryfall Image Downloader (Forge Friendly)
#  Author: Laryzinha
#  Version: 1.1.4-beta.1
#  Description:
#      High-quality Scryfall image downloader with colored UI,
#      batch SET download, Singles integration and Token/Audit support.
# ============================================================

import time
import pathlib
import requests
import re

# ---------- Colors & UI (aligned with Downloader.py) ----------
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

import re as _re
_ansi_re = _re.compile(r"\x1b\[[0-9;]*m")

def _visible_len(s: str) -> int:
    return len(_ansi_re.sub("", s))

def box(text_lines, color=CYAN):
    width = max(_visible_len(t) for t in text_lines) if text_lines else 0
    top = "╔" + "═" * (width + 2) + "╗"
    bot = "╚" + "═" * (width + 2) + "╝"
    print(color + top + RESET)
    for t in text_lines:
        vis = _visible_len(t)
        pad = width - vis
        print(color + "║ " + RESET + t + " " * pad + color + " ║" + RESET)
    print(color + bot + RESET)

def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s:02d}s"

# ---------- Config ----------
from tqdm import tqdm

ROOT_DIR = pathlib.Path(__file__).resolve().parent
TOKENS_DIR = ROOT_DIR / "Tokens"
AUDIT_FILE = ROOT_DIR / "Audit.txt"

SCRYFALL_SEARCH_URL = "https://api.scryfall.com/cards/search"
TIMEOUT = 25
RETRY = 3
REQUESTS_PER_SECOND = 8
DOWNLOAD_EXT = "jpg"
INVALID_WIN_CHARS = r'<>:"/\\|?*'

# ---------- Utils ----------
def sanitize_filename(name: str) -> str:
    out = []
    for ch in name:
        out.append("_" if ch in INVALID_WIN_CHARS else ch)
    cleaned = "".join(out).strip()
    while "  " in cleaned:
        cleaned = cleaned.replace("  ", " ")
    return cleaned

def safe_mkdir(path: pathlib.Path):
    path.mkdir(parents=True, exist_ok=True)

def http_get_json(url: str, params: dict = None):
    for attempt in range(RETRY):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 429:
                time.sleep(1.2)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == RETRY - 1:
                raise
            time.sleep(1.5)
    return {}

def http_get_json_direct(url: str):
    for attempt in range(RETRY):
        try:
            r = requests.get(url, timeout=TIMEOUT)
            if r.status_code == 429:
                time.sleep(1.2)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == RETRY - 1:
                raise
            time.sleep(1.5)
    return {}

def download_file(url: str, dst_path: pathlib.Path):
    for attempt in range(RETRY):
        try:
            with requests.get(url, stream=True, timeout=TIMEOUT) as r:
                r.raise_for_status()
                with open(dst_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            return
        except Exception:
            if attempt == RETRY - 1:
                raise
            time.sleep(1.5)

# ---------- Scryfall ----------
def fetch_scryfall_tokens(token_set_code: str):
    """
    Fetch all tokens for tSET (prints + extras).
    If Scryfall returns 404 (e.g., SLD → tSLD doesn’t exist), return [] and let caller skip.
    """
    all_cards = []
    query = f"set:{token_set_code} is:token unique:prints include:extras"
    params = {"q": query, "order": "set", "dir": "asc"}

    while True:
        try:
            data = http_get_json(SCRYFALL_SEARCH_URL, params)
        except requests.exceptions.HTTPError as e:
            if getattr(e, "response", None) is not None and e.response.status_code == 404:
                return []
            raise

        if "data" not in data:
            break
        all_cards.extend(data["data"])

        if data.get("has_more") and data.get("next_page"):
            try:
                data = http_get_json_direct(data["next_page"])
            except requests.exceptions.HTTPError as e:
                if getattr(e, "response", None) is not None and e.response.status_code == 404:
                    break
                raise
            params = {}
            continue
        break

    return all_cards

def image_url_for_card_jpg(card: dict, face_index: int = 1):
    """Return JPG (large) URL — fallback to PNG if needed (we still save as .jpg)."""
    if "image_uris" in card and card["image_uris"]:
        return card["image_uris"].get("large") or card["image_uris"].get("png")
    if "card_faces" in card:
        faces = card["card_faces"]
        idx = max(0, min(len(faces) - 1, face_index - 1))
        uris = faces[idx].get("image_uris", {})
        return uris.get("large") or uris.get("png")
    raise ValueError("Image URIs not found.")

# ---------- Parse Audit.txt ----------
FORGE_TOKEN_LINE = re.compile(r"^\s*([^\|]+)\|([A-Za-z0-9]+)\|(\d+)\|(\d+)\s*$")

def parse_audit_tokens(path: pathlib.Path):
    """
    Reads Audit.txt and collects entries:
      slug|SET|collector|face
    Returns:
      wanted: dict[(PARENT_SET, tSET)] -> { collector:int -> {slug, parent, face} }
      order:  list[(PARENT_SET, tSET)] in first-appearance order
    """
    wanted = {}
    order = []

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.upper().startswith("---"):
                continue
            m = FORGE_TOKEN_LINE.match(line)
            if not m:
                continue

            slug = m.group(1)
            parent = m.group(2).upper()
            collector = int(m.group(3))
            face = int(m.group(4))

            token_set = f"t{parent.lower()}"
            key = (parent, token_set)
            if key not in wanted:
                wanted[key] = {}
                order.append(key)

            wanted[key][collector] = {
                "slug": slug,
                "parent": parent,
                "face": face,
            }
    return wanted, order

# ---------- Preview helper ----------
def preview_items_vs_scryfall(items_dict: dict, cards: list):
    """Return (available, missing_list, by_collector_map) for preview."""
    by_collector = {}
    for c in cards:
        cnum_raw = str(c.get("collector_number", "0"))
        try:
            cnum = int(cnum_raw.split("★")[0])
        except Exception:
            continue
        by_collector[cnum] = c

    available = 0
    missing = []
    for collector in sorted(items_dict.keys()):
        if collector in by_collector:
            available += 1
        else:
            missing.append(collector)
    return available, missing, by_collector

# ---------- Download from Audit ----------
def download_tokens_from_audit():
    safe_mkdir(TOKENS_DIR)

    if not AUDIT_FILE.exists():
        # Create and write EN instructions
        with open(AUDIT_FILE, "w", encoding="utf-8") as f:
            f.write(
                "### Forge Audit Instructions ###\n"
                "1) Open Forge\n"
                "2) Go to Game Settings → Content Downloaders\n"
                "3) Click on “Audit Card and Image Data”\n"
                "4) When it finishes, click “Copy to Clipboard”\n"
                "5) Come back here and PASTE (Ctrl+V) into this file, then SAVE\n"
                "\n"
                "Expected line format:\n"
                "slug|SET|collector|face\n"
                "ex.: c_1_1_a_insect_flying|40K|22|1\n"
            )
        box([
            "Audit.txt was not found and has been created.",
            "Open it and paste the Forge audit (Copy to Clipboard), then save.",
            "Return here and run again: Download tokens from Audit.txt."
        ], color=YELLOW)
        input("Press ENTER to go back to the menu...")
        return

    # Ensure the user saved the latest clipboard content
    box([
        f"{BRIGHT}Audit file found:{RESET}",
        f"{AUDIT_FILE}",
        "",
        "If you just updated it in Forge, SAVE the file now.",
        "Press ENTER to proceed with reading the file..."
    ], color=CYAN)
    input()

    # Parse
    wanted, order = parse_audit_tokens(AUDIT_FILE)
    total_sets = len(order)
    total_requested = sum(len(wanted[k]) for k in wanted)

    if total_sets == 0 or total_requested == 0:
        box([
            "No valid token entries found in Audit.txt.",
            "Make sure the file contains lines like: slug|SET|collector|face"
        ], color=YELLOW)
        input("Press ENTER to go back to the menu...")
        return

    # PREVIEW
    box([
        f"Sets found: {CYAN}{total_sets}{RESET}",
        f"Tokens requested (from Audit): {CYAN}{total_requested}{RESET}",
        "",
        "We'll cross-check with Scryfall token sets (tSET)."
    ], color=CYAN)

    start_now = input("Start downloading tokens? (Y/N): ").strip().lower()
    if start_now not in ("y", "yes"):
        box(["Okay. Returning to menu..."], color=YELLOW)
        time.sleep(0.7)
        return

    # Global metrics + logs
    global_downloaded = 0
    global_errors = 0
    global_missing_total = 0
    global_start = time.time()

    # Logs: keep exact tokens that were NOT downloaded
    missing_log_lines = []  # tokens missing on Scryfall (collector → slug)
    error_log_lines = []    # tokens that failed to download (slug + error)

    # Per-set loop
    processed = 0
    for (parent_set, token_set_code) in order:
        processed += 1
        header = f"[{processed}/{total_sets}] {parent_set}  (Scryfall: {token_set_code})"
        print(f"\n{BRIGHT}{header}{RESET}")

        items = wanted[(parent_set, token_set_code)]
        cards = fetch_scryfall_tokens(token_set_code)

        if not cards:
            count = len(items)
            global_missing_total += count
            # Log all tokens from this set as missing
            for collector in sorted(items.keys()):
                slug = items[collector]["slug"]
                missing_log_lines.append(f"{parent_set} — collector {collector} → {slug} (token set {token_set_code} not found)")
            box([
                f"No token set found on Scryfall for {parent_set} ({token_set_code}).",
                "Skipping this set..."
            ], color=YELLOW)
            continue

        available, missing, by_collector = preview_items_vs_scryfall(items, cards)
        total_targets = len(items)
        preview_lines = [
            f"Preview for {parent_set} ({token_set_code}):",
            f"- Tokens requested: {CYAN}{total_targets}{RESET}",
            f"- Found on Scryfall: {GREEN}{available}{RESET}",
            f"- Missing on Scryfall: {YELLOW}{len(missing)}{RESET}" if missing else "- Missing on Scryfall: 0",
        ]
        if missing:
            preview_lines.append(f"- Missing collectors: {', '.join(str(m) for m in missing)}")
        box(preview_lines, color=YELLOW)

        # Log missing tokens (collector → slug) for this set
        if missing:
            global_missing_total += len(missing)
            for m in missing:
                slug_m = items[m]["slug"]
                missing_log_lines.append(f"{parent_set} — collector {m} → {slug_m}")

        # Download set
        downloaded = 0
        errors = 0
        error_list = []
        set_start = time.time()

        tqdm_desc = f"{parent_set} — downloading tokens"
        for collector in tqdm(sorted(items.keys()), desc=tqdm_desc, unit="img"):
            data = items[collector]
            slug = data["slug"]
            face = data["face"]
            parent = data["parent"]

            card = by_collector.get(collector)
            if not card:
                # accounted as 'missing' already
                continue

            try:
                url = image_url_for_card_jpg(card, face_index=face)
                base = sanitize_filename(slug)

                dst = TOKENS_DIR / f"{base}.{DOWNLOAD_EXT}"
                if dst.exists():
                    dst = TOKENS_DIR / f"{base} ({parent}).{DOWNLOAD_EXT}"

                download_file(url, dst)
                downloaded += 1
                time.sleep(1.0 / REQUESTS_PER_SECOND)
            except Exception as e:
                errors += 1
                err_text = f"{slug} — {e}"
                error_list.append(err_text)
                error_log_lines.append(f"{parent_set} — {err_text}")

        set_elapsed = time.time() - set_start
        set_avg_speed = (downloaded / set_elapsed) if set_elapsed > 0 else 0.0

        # Per-set summary
        lines = [
            f"{BRIGHT}SET {parent_set}{RESET} completed.",
            f"Requested: {CYAN}{total_targets}{RESET}",
            f"Downloaded: {GREEN}{downloaded}{RESET}",
            f"Missing (from preview): {YELLOW}{len(missing)}{RESET}",
            f"Errors while downloading: {RED}{errors}{RESET}",
            f"Elapsed time: {CYAN}{format_duration(set_elapsed)}{RESET}",
            f"Average speed: {CYAN}{set_avg_speed:.2f} images/s{RESET}",
        ]
        box(lines, color=GREEN)

        if errors:
            print("")
            box(["Errors detail:"] + error_list, color=RED)

        global_downloaded += downloaded
        global_errors += errors

    # Global summary
    total_elapsed = time.time() - global_start
    global_avg = (global_downloaded / total_elapsed) if total_elapsed > 0 else 0.0

    summary_lines = [
        f"{BRIGHT}TOKEN DOWNLOAD SUMMARY{RESET}",
        f"Total sets: {CYAN}{total_sets}{RESET}",
        f"Tokens requested: {CYAN}{total_requested}{RESET}",
        f"Downloaded: {GREEN}{global_downloaded}{RESET}",
        f"Missing on Scryfall: {YELLOW}{global_missing_total}{RESET}",
        f"Errors: {RED}{global_errors}{RESET}",
        f"Elapsed time: {CYAN}{format_duration(total_elapsed)}{RESET}",
        f"Average speed: {CYAN}{global_avg:.2f} images/s{RESET}",
    ]
    print("")
    box(summary_lines, color=CYAN)

    # Write LOG with exact tokens not downloaded
    if missing_log_lines or error_log_lines:
        log_path = ROOT_DIR / "DToken_log.txt"
        with open(log_path, "w", encoding="utf-8") as f:
            if missing_log_lines:
                f.write("# Missing tokens (not found on Scryfall token set)\n")
                # group by set for readability
                # (lines already contain "SET — collector N → slug")
                for line in missing_log_lines:
                    f.write(line + "\n")
                f.write("\n")
            if error_log_lines:
                f.write("# Errors while downloading\n")
                for line in error_log_lines:
                    f.write(line + "\n")
        box([f"Log written to: {log_path}"], color=YELLOW)

    print("")
    box(["All done!"], color=GREEN)

# ---------- Menu ----------
def main_menu():
    safe_mkdir(TOKENS_DIR)

    lines = [
        f"{BRIGHT}1){RESET} Download tokens from Audit.txt",
        f"{BRIGHT}2){RESET} Back to main menu",
    ]
    box(lines, color=CYAN)

    choice = input("Option (1/2): ").strip()
    if choice == "1":
        download_tokens_from_audit()
        # After finishing, show this menu again (if running standalone)
        main_menu()
    elif choice == "2":
        # If called by Downloader.py, just return.
        return
    else:
        print(RED + "\nInvalid option.\n" + RESET)
        time.sleep(0.6)
        main_menu()

# ---------- Run ----------
if __name__ == "__main__":
    main_menu()
