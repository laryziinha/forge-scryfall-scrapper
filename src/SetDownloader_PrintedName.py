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
import difflib
import unicodedata
import random
from pathlib import Path
from typing import Dict, List, Optional, NamedTuple

import requests
from tqdm import tqdm

# ------------------------------------------------------------
# Colors / UI helpers
# ------------------------------------------------------------
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
    CYAN = Fore.CYAN
    YELLOW = Fore.YELLOW
    GREEN = Fore.GREEN
    RED = Fore.RED
    PINK = Fore.MAGENTA
    BRIGHT = Style.BRIGHT
    RESET = Style.RESET_ALL
except Exception:
    CYAN = YELLOW = GREEN = RED = PINK = BRIGHT = RESET = ""

_ansi_re = re.compile(r"\x1b\[[0-9;]*m")


def _visible_len(s: str) -> int:
    return len(_ansi_re.sub("", s))


def box(lines: List[str], color=YELLOW):
    width = max(_visible_len(l) for l in lines) if lines else 0
    print(color + "╔" + "═" * (width + 2) + "╗" + RESET)
    for l in lines:
        pad = width - _visible_len(l)
        print(color + "║ " + RESET + l + " " * pad + color + " ║" + RESET)
    print(color + "╚" + "═" * (width + 2) + "╝" + RESET)


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s:02d}s"


# ------------------------------------------------------------
# Networking (same profile as Downloader.py)
# ------------------------------------------------------------
SCRYFALL_API = "https://api.scryfall.com"

RATE_SLEEP = 0.20
TIMEOUT = 30
RETRY = 6
BACKOFF_BASE = 1.2
BACKOFF_JITTER = 0.35

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ForgeImageFetcher/1.1 (laryzinha)"})


def scry_get_json(url: str, *, params=None) -> dict:
    last_exc = None
    for attempt in range(1, RETRY + 1):
        try:
            r = SESSION.get(url, params=params, timeout=TIMEOUT)

            if r.status_code == 429 or 500 <= r.status_code <= 599:
                raise requests.exceptions.HTTPError(f"HTTP {r.status_code}", response=r)

            r.raise_for_status()
            time.sleep(RATE_SLEEP)
            return r.json()

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
        ) as e:
            last_exc = e
            if attempt == RETRY:
                raise
            time.sleep((BACKOFF_BASE ** attempt) + (random.random() * BACKOFF_JITTER))
    raise last_exc


def download_bytes_with_retry(url: str) -> bytes:
    last_exc = None
    for attempt in range(1, RETRY + 1):
        try:
            r = SESSION.get(url, timeout=TIMEOUT)
            if r.status_code == 429 or 500 <= r.status_code <= 599:
                raise requests.exceptions.HTTPError(f"HTTP {r.status_code}", response=r)

            r.raise_for_status()
            time.sleep(RATE_SLEEP)
            return r.content

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            OSError,
        ) as e:
            last_exc = e
            if attempt == RETRY:
                raise
            time.sleep((BACKOFF_BASE ** attempt) + (random.random() * BACKOFF_JITTER))
    raise last_exc


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def slugify(name: str) -> str:
    name = (name or "").strip().replace(":", "-")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "_", name)
    name = name.rstrip(" .")
    return name if name else "Unknown"


def cards_root() -> Path:
    return Path(__file__).resolve().parent / "Cards"


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def clear_directory(p: Path):
    # remove only files (keep it safe)
    for item in p.iterdir():
        try:
            if item.is_file():
                item.unlink()
        except Exception:
            pass


# ------------------------------------------------------------
# Scryfall logic
# ------------------------------------------------------------
def get_all_sets() -> List[dict]:
    return scry_get_json(f"{SCRYFALL_API}/sets").get("data", [])

def fuzzy_match_set(user: str, sets: List[dict], top_n: int = 10) -> List[dict]:
    """
    Returns a ranked list of candidate sets based on:
      - exact code match
      - arena_code / mtgo_code exact match
      - substring match on name/code
      - difflib close matches on name/code
    """
    u_raw = (user or "").strip()
    if not u_raw:
        return []

    u = strip_accents(u_raw.lower())

    def norm(x: Optional[str]) -> str:
        return strip_accents((x or "").lower()).strip()

    # 1) Exact code / arena / mtgo
    exact = []
    for s in sets:
        if u == norm(s.get("code")) or u == norm(s.get("arena_code")) or u == norm(s.get("mtgo_code")):
            exact.append(s)
    if exact:
        return exact[:top_n]

    # 2) Substring matches (best UX for partial typing)
    subs = []
    for s in sets:
        name_n = norm(s.get("name"))
        code_n = norm(s.get("code"))
        arena_n = norm(s.get("arena_code"))
        mtgo_n = norm(s.get("mtgo_code"))
        if u in name_n or u in code_n or (arena_n and u in arena_n) or (mtgo_n and u in mtgo_n):
            subs.append(s)

    # rank substring results: prefer code startswith, then name contains
    def subs_score(s: dict) -> tuple:
        code_n = norm(s.get("code"))
        name_n = norm(s.get("name"))
        return (
            0 if code_n.startswith(u) else 1,
            0 if u in name_n else 1,
            len(name_n),
        )

    subs.sort(key=subs_score)

    # 3) Close matches (fallback)
    if len(subs) < top_n:
        names = [norm(s.get("name")) for s in sets]
        codes = [norm(s.get("code")) for s in sets]

        close_names = difflib.get_close_matches(u, names, n=top_n, cutoff=0.60)
        close_codes = difflib.get_close_matches(u, codes, n=top_n, cutoff=0.60)

        close = []
        for n in close_names:
            idx = names.index(n)
            close.append(sets[idx])
        for c in close_codes:
            idx = codes.index(c)
            close.append(sets[idx])

        # de-dup preserving order
        seen = set()
        close_dedup = []
        for s in close:
            key = s.get("code")
            if key and key not in seen:
                seen.add(key)
                close_dedup.append(s)

        subs.extend(close_dedup)

    # de-dup and cap
    seen = set()
    out = []
    for s in subs:
        code = (s.get("code") or "").upper()
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(s)
        if len(out) >= top_n:
            break

    return out

def pick_set_interactive(sets_meta: List[dict]) -> Optional[dict]:
    """
    Downloader-like UI:
      - Blue box: instructions + examples
      - Purple box: list of matches (paginates when many)
      - Input: number / N / P / B
    """

    def norm(x: Optional[str]) -> str:
        return strip_accents((x or "").lower()).strip()

    def build_matches(query: str) -> List[dict]:
        """
        More like Downloader.py behavior:
        - exact code has priority
        - otherwise return ALL substring matches (not only top 10)
        - fallback to difflib close matches if no substring results
        """
        q = norm(query)
        if not q:
            return []

        # 1) exact code / arena / mtgo
        exact = []
        for s in sets_meta:
            if q == norm(s.get("code")) or q == norm(s.get("arena_code")) or q == norm(s.get("mtgo_code")):
                exact.append(s)
        if exact:
            return exact

        # 2) substring matches (return all)
        subs = []
        for s in sets_meta:
            name_n = norm(s.get("name"))
            code_n = norm(s.get("code"))
            arena_n = norm(s.get("arena_code"))
            mtgo_n = norm(s.get("mtgo_code"))
            if q in name_n or q in code_n or (arena_n and q in arena_n) or (mtgo_n and q in mtgo_n):
                subs.append(s)

        # rank substring results: prefer code startswith, then name contains, then shorter name
        def subs_score(s: dict) -> tuple:
            code_n = norm(s.get("code"))
            name_n = norm(s.get("name"))
            return (
                0 if code_n.startswith(q) else 1,
                0 if q in name_n else 1,
                len(name_n),
            )

        subs.sort(key=subs_score)

        # de-dup by set code
        seen = set()
        out = []
        for s in subs:
            code = (s.get("code") or "").upper()
            if not code or code in seen:
                continue
            seen.add(code)
            out.append(s)

        if out:
            return out

        # 3) fallback: close matches (cap to avoid absurd lists)
        names = [norm(s.get("name")) for s in sets_meta]
        codes = [norm(s.get("code")) for s in sets_meta]
        close_names = difflib.get_close_matches(q, names, n=30, cutoff=0.60)
        close_codes = difflib.get_close_matches(q, codes, n=30, cutoff=0.60)

        close = []
        for n in close_names:
            idx = names.index(n)
            close.append(sets_meta[idx])
        for c in close_codes:
            idx = codes.index(c)
            close.append(sets_meta[idx])

        seen = set()
        out = []
        for s in close:
            code = (s.get("code") or "").upper()
            if not code or code in seen:
                continue
            seen.add(code)
            out.append(s)
        return out

    def fmt_row(i: int, s: dict) -> str:
        code = (s.get("code") or "").upper()
        name = s.get("name") or "Unknown"
        rel = s.get("released_at") or "—"
        stype = (s.get("set_type") or "—").replace("_", " ").title()
        return f"{i:>2}) {name} [{code}]  {stype}  {rel}"

    def prompt_yes_no(question: str, default_no: bool = True) -> bool:
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

    PAGE_SIZE = 12

    while True:
        box([
            f"{BRIGHT}Download a specific SET{RESET}",
            "",
            "Type the SET code or part of the name.",
            f"Examples: {CYAN}one{RESET}, {CYAN}m21{RESET}, {CYAN}Quarta Edição{RESET}",
            "",
            f"{YELLOW}[B]{RESET} Back",
        ], color=CYAN)

        q = input(BRIGHT + "Your input: " + RESET).strip()
        if not q:
            print(RED + "Please type a set code or name (or 'B' to go back)." + RESET)
            continue
        if q.lower() in {"b", "back"}:
            return None

        matches = build_matches(q)
        if not matches:
            box([
                f"{BRIGHT}No matches{RESET}",
                "",
                f"Nothing matched: {CYAN}{q}{RESET}",
                "Tip: try fewer letters (e.g. 'promo', 'guild', 'ixalan')."
            ], color=RED)
            continue

        # Single match: confirm and return
        if len(matches) == 1:
            chosen = matches[0]
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
            continue

        # Multi match: paginated list inside purple box
        page = 0
        total_pages = (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE

        while True:
            start = page * PAGE_SIZE
            end = start + PAGE_SIZE
            chunk = matches[start:end]

            lines = [f"{BRIGHT}Multiple matches found{RESET}", ""]
            for idx, s in enumerate(chunk, start=start + 1):
                lines.append(fmt_row(idx, s))

            lines += [
                "",
                f"Page {page + 1}/{total_pages} — choose a number, {YELLOW}N{RESET} next, {YELLOW}P{RESET} prev, {YELLOW}B{RESET} back"
            ]
            box(lines, color=PINK)

            pick = input(BRIGHT + "Choose [# / N / P / B]: " + RESET).strip().lower()

            if pick in {"b", "back"}:
                break
            if pick in {"n", "next"}:
                if page < total_pages - 1:
                    page += 1
                continue
            if pick in {"p", "prev", "previous"}:
                if page > 0:
                    page -= 1
                continue
            if pick.isdigit():
                idx = int(pick)
                if 1 <= idx <= len(matches):
                    chosen = matches[idx - 1]
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
                    # se não confirmar, volta pra lista (mesma página)
                    continue

            print(RED + "Invalid choice." + RESET)


def search_cards(set_code: str) -> List[dict]:
    cards = []
    page = 1
    while True:
        js = scry_get_json(
            f"{SCRYFALL_API}/cards/search",
            params={
                "q": f"e:{set_code}",
                "unique": "prints",
                "include_extras": "true",
                "include_variations": "true",
                "order": "set",
                "dir": "asc",
                "page": page,
            },
        )
        cards.extend(js.get("data", []))
        if not js.get("has_more"):
            break
        page += 1
    return cards


# ------------------------------------------------------------
# Printed-name-first logic (INTACT BY DESIGN)
# ------------------------------------------------------------
class Entry(NamedTuple):
    url: str
    name: str


def preferred_title(card: dict) -> str:
    # IMPORTANT: keep printed/flavor first (SLD-friendly)
    return (card.get("flavor_name") or card.get("printed_name") or card.get("name") or "Unknown").strip()


def pick_png_uri(uris: Optional[Dict]) -> Optional[str]:
    if not uris:
        return None
    return uris.get("png") or uris.get("large") or uris.get("normal") or uris.get("small")


def build_entries(card: dict) -> List[Entry]:
    out: List[Entry] = []

    if card.get("image_uris"):
        url = pick_png_uri(card.get("image_uris"))
        if url:
            out.append(Entry(url, preferred_title(card)))
        return out

    # DFC / faces
    for f in card.get("card_faces", []) or []:
        url = pick_png_uri(f.get("image_uris"))
        if url:
            out.append(Entry(url, preferred_title(f)))

    return out


# ------------------------------------------------------------
# File naming helpers (handles duplicates: Name2, Name3, ...)
# ------------------------------------------------------------
def next_available_path(folder: Path, base_name: str, ext: str, mode: str) -> Path:
    """
    mode:
      - "skip": if Name exists, use Name2/Name3... (preserves all prints)
      - "overwrite": always use Name (overwrite)
    """
    base = slugify(base_name)

    if mode == "overwrite":
        return folder / f"{base}.fullborder{ext}"

    candidate = folder / f"{base}.fullborder{ext}"
    if not candidate.exists():
        return candidate

    i = 2
    while True:
        candidate = folder / f"{base}{i}.fullborder{ext}"
        if not candidate.exists():
            return candidate
        i += 1


def folder_has_files(p: Path) -> bool:
    return p.exists() and any(p.iterdir())


def choose_folder_mode(set_dir: Path) -> str:
    """
    Returns: "skip" | "overwrite" | "clean"
    """
    if not folder_has_files(set_dir):
        return "skip"

    box(
        [
            f"{BRIGHT}Folder already exists{RESET}",
            "",
            f"{CYAN}{set_dir}{RESET}",
            "",
            "1) Skip existing (default)  → keeps ALL prints (Name2/Name3...)",
            "2) Overwrite existing       → replaces Name.fullborder.png",
            "3) Clean folder & redownload",
        ],
        color=YELLOW,
    )

    opt = input("Choose [1-3]: ").strip()
    if opt == "2":
        return "overwrite"
    if opt == "3":
        return "clean"
    return "skip"


# ------------------------------------------------------------
# One download run
# ------------------------------------------------------------
def run_download_for_set(sets: List[dict]) -> None:
    match = pick_set_interactive(sets)
    if match is None:
        return


    set_code = (match.get("code") or "").upper()
    set_name = match.get("name") or "Unknown"
    set_type = (match.get("set_type") or "—").replace("_", " ").title()
    released = match.get("released_at") or "—"
    expected = match.get("card_count") or match.get("printed_size") or "—"

    try:
        cards = search_cards(match.get("code", ""))
    except requests.exceptions.HTTPError as e:
        resp = getattr(e, "response", None)
        if resp is not None and resp.status_code == 404:
            box(
                [
                    f"{BRIGHT}No cards returned by Scryfall{RESET}",
                    "",
                    "This can happen if the set exists in the database",
                    "but no cards are published yet.",
                ],
                color=YELLOW,
            )
            return
        raise

    # Confirm box
    box(
        [
            f"{BRIGHT}Confirm download{RESET}",
            "",
            f"{set_name}  [{CYAN}{set_code}{RESET}]",
            f"Type: {set_type}   Release: {released}",
            f"Scryfall reference size: {CYAN}{expected}{RESET}",
            f"Search results (prints): {CYAN}{len(cards)}{RESET}",
            "",
            f"Mode: {CYAN}Printed / Flavor name first{RESET} (SLD-friendly)",
            "",
            "Start download now?",
        ],
        color=YELLOW,
    )

    if input("Proceed [y/N]: ").strip().lower() != "y":
        return

    # Output folder + mode
    out_dir = cards_root() / set_code
    ensure_dir(out_dir)

    mode = choose_folder_mode(out_dir)
    if mode == "clean":
        clear_directory(out_dir)
        mode = "skip"  # after cleaning, just download normally

    # Stats + log
    start = time.time()
    downloaded = 0
    skipped = 0
    errors = 0
    log: List[str] = []
    log_path = out_dir / f"errors_{set_code}.log.txt"

    pbar = tqdm(cards, desc=f"[{set_code}] downloading", unit="card", dynamic_ncols=True)
    for card in pbar:
        entries = build_entries(card)
        if not entries:
            skipped += 1
            continue

        for e in entries:
            try:
                ext = ".png"
                path = next_available_path(out_dir, e.name, ext, mode)

                # If overwrite: we always write.
                # If skip: we always write too (path will be Name2/Name3... if needed).
                content = download_bytes_with_retry(e.url)

                with open(path, "wb") as f:
                    f.write(content)

                downloaded += 1

            except requests.exceptions.HTTPError as ex:
                errors += 1
                status = ex.response.status_code if getattr(ex, "response", None) is not None else "?"
                log.append(f"[HTTP {status}] {e.name} -> {e.url} :: {ex}")

            except Exception as ex:
                errors += 1
                log.append(f"[EXCEPTION] {e.name} -> {e.url} :: {ex}")

    pbar.close()

    elapsed = time.time() - start
    avg_speed = downloaded / elapsed if elapsed > 0 else 0.0

    if log:
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(log))
        except Exception:
            pass

    # Final box
    lines = [
        f"{GREEN}{BRIGHT}SET {set_code} completed{RESET}",
        f"Search results (records/prints): {CYAN}{len(cards)}{RESET}",
        f"Scryfall reference size: {CYAN}{expected}{RESET}",
        f"Images downloaded (includes faces/flip): {GREEN}{downloaded}{RESET}",
        f"Skipped: {YELLOW}{skipped}{RESET}",
        f"Errors: {RED}{errors}{RESET}",
        f"Elapsed time: {CYAN}{format_duration(elapsed)}{RESET}",
        f"Average speed: {CYAN}{avg_speed:.2f} images/s{RESET}",
        (f"Error log: {log_path}" if log else "No errors recorded."),
        f"Output: {CYAN}{out_dir}{RESET}",
    ]
    box(lines, color=YELLOW)


# ------------------------------------------------------------
# Main loop (like other modules)
# ------------------------------------------------------------
def main():
    box([
        f"{BRIGHT}PRINTED-NAME SET DOWNLOADER{RESET}",
        "",
        f"Mode: {CYAN}Printed / Flavor name first{RESET}",
    ], color=YELLOW)


    sets = get_all_sets()

    while True:
        run_download_for_set(sets)

        ans = input("\nDownload another set? [y/N]: ").strip().lower()
        if ans != "y":
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled by user.")