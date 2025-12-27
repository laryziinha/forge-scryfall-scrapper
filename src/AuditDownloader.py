# ============================================================
#  Scryfall Image Downloader (Forge Friendly)
#  Author: Laryzinha
#  Version: 1.1.4
#  Description:
#      High-quality Scryfall image downloader with colored UI,
#      batch SET download, Singles integration and Token/Audit support.
# ============================================================

import re
import sys
import time
import unicodedata
import random
from pathlib import Path
from typing import Dict, List, Optional

import requests
from tqdm import tqdm
from PIL import Image
from io import BytesIO

# ---------- Cores / UI ----------
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

_ansi_re = re.compile(r"\x1b\[[0-9;]*m")
def _visible_len(s: str) -> int: return len(_ansi_re.sub("", s))

def box(lines: List[str], color=CYAN) -> None:
    width = max(_visible_len(t) for t in lines) if lines else 0
    print(color + "╔" + "═" * (width + 2) + "╗" + RESET)
    for t in lines:
        pad = width - _visible_len(t)
        print(color + "║ " + RESET + t + " " * pad + color + " ║" + RESET)
    print(color + "╚" + "═" * (width + 2) + "╝" + RESET)

def format_duration(s: float) -> str:
    if s < 60: return f"{int(s)}s"
    m, ss = int(s // 60), int(s % 60)
    return f"{m}m {ss:02d}s"

# ---------- Paths / nomes ----------
def script_root() -> Path:
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd()

def cards_root() -> Path:
    return script_root() / "Cards"

def ensure_dir(p: Path): p.mkdir(parents=True, exist_ok=True)

INVALID_CHARS_PATTERN = r'[<>:"/\\|?*\x00-\x1F]'
def slugify_filename(name: str) -> str:
    name = (name or "").replace(":", "-").strip()
    return re.sub(INVALID_CHARS_PATTERN, "_", name)

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def normalize_title(s: str) -> str:
    s = strip_accents(s or "")
    s = s.lower()
    s = re.sub(r"[\"'’`´]", "", s)
    s = re.sub(r"[^a-z0-9 \-\&]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def infer_ext_from_url(url: str) -> str:
    return ".png" if ".png" in (url or "").lower() else ".jpg"

# ---------- HTTP / Scryfall ----------
SCRYFALL_API = "https://api.scryfall.com"

# --- Networking / rate control ---
RATE_SLEEP = 0.20
TIMEOUT = 30
RETRY = 6
BACKOFF_BASE = 1.2
BACKOFF_JITTER = 0.35

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ForgeImageFetcher/1.9 (bconti-scrapper)"})

# --- Wrapper ---
def scry_get_json(url: str, *, params: dict | None = None) -> dict:
    last_exc = None
    for attempt in range(1, RETRY + 1):
        try:
            r = SESSION.get(url, params=params, timeout=TIMEOUT)

            # 404/400 não adianta tentar de novo
            if r.status_code in (400, 404):
                r.raise_for_status()

            # retry somente em rate limit / instabilidade
            if r.status_code == 429 or 500 <= r.status_code <= 599:
                raise requests.exceptions.HTTPError(f"HTTP {r.status_code}", response=r)

            r.raise_for_status()
            time.sleep(RATE_SLEEP)
            return r.json()

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as e:

            # NÃO dar retry em 400/404 (erro lógico/sem resultado)
            if isinstance(e, requests.exceptions.HTTPError):
                resp = getattr(e, "response", None)
                if resp is not None and resp.status_code in (400, 404):
                    raise

            last_exc = e
            sleep_s = (BACKOFF_BASE ** attempt) + random.random() * BACKOFF_JITTER

            if attempt == RETRY:
                raise

            print(f"[net] retry {attempt}/{RETRY} in {sleep_s:.1f}s — {e}")
            time.sleep(sleep_s)

    raise last_exc


def download_bytes_with_retry(url: str) -> bytes:
    last_exc = None
    for attempt in range(1, RETRY + 1):
        try:
            with SESSION.get(url, stream=True, timeout=TIMEOUT) as r:
                if r.status_code == 429 or 500 <= r.status_code <= 599:
                    raise requests.exceptions.HTTPError(f"HTTP {r.status_code}", response=r)
                r.raise_for_status()
                content = r.content

            time.sleep(RATE_SLEEP)
            return content

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError,
                OSError) as e:
            last_exc = e
            sleep_s = (BACKOFF_BASE ** attempt) + random.random() * BACKOFF_JITTER
            if attempt == RETRY:
                raise
            print(f"[net-img] retry {attempt}/{RETRY} in {sleep_s:.1f}s — {e}")
            time.sleep(sleep_s)

    raise last_exc

# --- Search ---

def _search_cards(query: str) -> List[dict]:
    out, page = [], 1
    while True:
        url = (f"{SCRYFALL_API}/cards/search"
               f"?q={requests.utils.quote(query)}"
               f"&order=set&dir=asc"
               f"&unique=prints&include_extras=true&include_variations=true"
               f"&page={page}")

        try:
            js = scry_get_json(url)
        except requests.exceptions.HTTPError as e:
            resp = getattr(e, "response", None)
            if resp is not None and resp.status_code == 404:
                break
            raise

        out.extend(js.get("data", []))
        if not js.get("has_more"):
            break
        page += 1

    return out

def scry_search_cards_for_set(set_code: str) -> List[dict]:
    return _search_cards(f"(not:token) e:{set_code}")

def scry_search_global_by_name(name: str) -> List[dict]:
    base = name.strip()
    compact = base.replace(" ", "")
    for q in (
        f'(not:token) (name:"{base}" OR printed:"{base}")',
        f'(not:token) (name:{base} OR printed:{base})',
        f'(not:token) (name:"{compact}" OR printed:"{compact}")',
    ):
        cards = _search_cards(q)
        if cards: return cards
    return []

# ---------- Imagem ----------
def should_rotate_h90(card: dict, img: Image.Image) -> bool:
    layout = (card.get("layout") or "").lower()
    horizontal_layouts = {"split", "aftermath", "flip"}
    w, h = img.size
    return (w > h) and (layout in horizontal_layouts)

def save_image(content: bytes, out_path: Path, card=None, rotate_mode: Optional[str] = None):
    try:
        img = Image.open(BytesIO(content))
        if rotate_mode == "rot180":
            img = img.rotate(180, expand=True).convert("RGB")
            img.save(out_path.with_suffix(".jpg"), quality=95, subsampling=0, optimize=True)
            return
        if should_rotate_h90(card, img):
            img = img.rotate(90, expand=True).convert("RGB")
            img.save(out_path.with_suffix(".jpg"), quality=95, subsampling=0, optimize=True)
            return
    except Exception:
        pass
    with open(out_path, "wb") as f:
        f.write(content)

# ---------- Candidatos ----------
def _from_uris(uris: dict) -> Optional[str]:
    if not uris: return None
    return uris.get("large") or uris.get("png") or uris.get("normal") or uris.get("small")

def _normset(*vals) -> set:
    return { normalize_title(v) for v in vals if v }

def _face_tuple(f: dict) -> tuple:
    return (f.get("flavor_name"), f.get("printed_name"), f.get("name"))

def _card_tuple(c: dict) -> tuple:
    return (c.get("flavor_name"), c.get("printed_name"), c.get("name"))

def _concat_faces(faces: List[dict], key: str) -> str:
    parts = []
    for f in faces:
        v = f.get(key) or ""
        parts.append(v.replace(" ", ""))
    return "".join(parts)

def build_candidate_entries_for_card(card: dict) -> List[dict]:
    layout = (card.get("layout") or "").lower()
    entries: List[dict] = []

    if card.get("image_uris"):
        u = _from_uris(card["image_uris"])
        if not u: return entries
        ext = infer_ext_from_url(u) or ".jpg"

        if layout in {"split", "aftermath"}:
            faces = card.get("card_faces") or []
            if faces:
                cf = _concat_faces(faces, "flavor_name")
                cp = _concat_faces(faces, "printed_name")
                cc = _concat_faces(faces, "name")
                cands = _normset(cf, cp, cc, cf.lower(), cp.lower(), cc.lower())
                entries.append({"url": u, "rotate": None, "candidates": cands, "ext": ext, "card": card})
                return entries

        if layout == "adventure":
            faces = card.get("card_faces") or []
            if faces:
                cf = _concat_faces(faces, "flavor_name")
                cp = _concat_faces(faces, "printed_name")
                cc = _concat_faces(faces, "name")
                f1_flv, f1_pr, f1_nm = _face_tuple(faces[0])
                f2_flv, f2_pr, f2_nm = _face_tuple(faces[1]) if len(faces) > 1 else (None,None,None)
                cands = _normset(cf, cp, cc, f1_flv, f1_pr, f1_nm, f2_flv, f2_pr, f2_nm)
                entries.append({"url": u, "rotate": None, "candidates": cands, "ext": ext, "card": card})
                return entries

        if layout == "flip":
            faces = card.get("card_faces") or []
            f1_flv, f1_pr, f1_nm = _face_tuple(faces[0]) if faces else (None, None, None)
            c1 = _normset(f1_flv, f1_pr, f1_nm, *_card_tuple(card))
            entries.append({"url": u, "rotate": None, "candidates": c1, "ext": ext, "card": card})
            f2_flv, f2_pr, f2_nm = _face_tuple(faces[1]) if len(faces) > 1 else (None, None, None)
            c2 = _normset(f2_flv, f2_pr, f2_nm, *_card_tuple(card))
            entries.append({"url": u, "rotate": "rot180", "candidates": c2, "ext": ext, "card": card})
            return entries

        flv, prn, nm = _card_tuple(card)
        cands = _normset(flv, prn, nm)
        entries.append({"url": u, "rotate": None, "candidates": cands, "ext": ext, "card": card})
        return entries

    faces = card.get("card_faces") or []
    for f in faces:
        u = _from_uris(f.get("image_uris", {}))
        if not u:
            continue
        ext = infer_ext_from_url(u) or ".jpg"
        flv, prn, nm = _face_tuple(f)
        cands = _normset(flv, prn, nm)
        entries.append({"url": u, "rotate": None, "candidates": cands, "ext": ext, "card": card})

    return entries

# ---------- Parser do Audit.txt ----------
AUDIT_HEADER_RE = re.compile(r"^\s*.+\(([A-Za-z0-9]+)\)\s*$")
AUDIT_LINE_RE   = re.compile(r"^\s*([A-Za-z0-9_]+)/(.*)\.full\s*$")

def parse_audit_file(audit_path: Path) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    current_set = None

    if not audit_path.exists():
        return groups

    for raw in audit_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("---"):
            continue

        m_head = AUDIT_HEADER_RE.match(line)
        if m_head:
            current_set = (m_head.group(1) or "").upper()
            groups.setdefault(current_set, [])
            continue

        m_item = AUDIT_LINE_RE.match(line)
        if m_item and current_set:
            name_full = m_item.group(2)
            groups[current_set].append(name_full)
    return groups

# ---------- Helpers de UX ----------
def preview_names(names: List[str], max_items: int = 12) -> List[str]:
    if not names:
        return ["(no items)"]
    show = names[:max_items]
    extra = len(names) - len(show)
    lines = [f"• {n}" for n in show]
    if extra > 0:
        lines.append(f"... (+{extra} more)")
    return lines

def ask_choice(prompt: str, valid=("y","n","s","q")) -> str:
    while True:
        ans = input(prompt).strip().lower()
        if ans in valid:
            return ans
        print(RED + "Invalid option." + RESET)

# ---------- Auditoria / Fluxo ----------
def ensure_audit_file_with_instructions(audit_path: Path) -> bool:
    """Cria Audit.txt com instruções EN se não existir. Retorna True se deve sair ao menu."""
    if audit_path.exists():
        return False
    audit_path.write_text(
        "### Forge Audit Instructions ###\n"
        "1) Open Forge\n"
        "2) Game Settings → Content Downloaders\n"
        "3) Click on 'Audit Card and Image Data'\n"
        "4) When finished, click 'Copy to Clipboard'\n"
        "5) Come back here and PASTE (Ctrl+V) into this file, then SAVE\n"
        "\n"
        "Expected line format (one per token/card):\n"
        "slug|SET|collector|face\n"
        "ex.: c_1_1_a_insect_flying|40K|22|1\n"
        "Bloomburrow Commander (BLC)\n"
        "BLC/Brightcap Badger2.full",
        encoding="utf-8"
    )
    box([
        "Audit.txt was not found and has been created here:",
        f"{audit_path}",
        "",
        "Paste the Forge clipboard there and SAVE, then run again."
    ], color=YELLOW)
    input("Press ENTER to return...")
    return True

def audit_download_flow():
    base_dir = cards_root()
    ensure_dir(base_dir)

    audit_path = script_root() / "Audit.txt"
    if ensure_audit_file_with_instructions(audit_path):
        return

    # Confirma leitura mais recente
    box([
        f"{BRIGHT}Audit file found:{RESET}",
        f"{audit_path}",
        "",
        "If you just updated it in Forge, SAVE the file now.",
        "Press ENTER to proceed with reading the file..."
    ], color=CYAN)
    input()

    groups = parse_audit_file(audit_path)
    if not groups:
        box(["No items parsed from Audit.txt."], color=RED)
        return

    total_sets = sum(1 for k, v in groups.items() if v)
    total_items = sum(len(v) for v in groups.values())

    # Resumo + seleção do modo de execução
    box([
        f"Sets found in Audit: {CYAN}{total_sets}{RESET}",
        f"Items found in Audit: {CYAN}{total_items}{RESET}",
        ""
    ], color=CYAN)

    box([
        f"{BRIGHT}Audit Download Mode{RESET}",
        "",
        f"{CYAN}1){RESET} Download ALL sets automatically (no confirmations)",
        f"{CYAN}2){RESET} Confirm EACH set before downloading (recommended)",
        f"{CYAN}3){RESET} Cancel / Back to menu",
    ], color=CYAN)

    mode = None
    while True:
        mode_in = input(BRIGHT + "Choose an option [1-3]: " + RESET).strip()
        if mode_in == "1":
            mode = "auto"
            break
        elif mode_in == "2":
            mode = "ask"
            break
        elif mode_in == "3":
            box(["Operation cancelled. Returning to menu."], color=YELLOW)
            return
        else:
            print(RED + "Invalid option. Please type 1, 2, or 3." + RESET)

    # Log global incremental
    log_path = script_root() / "AuditDownload_log.txt"
    with open(log_path, "w", encoding="utf-8") as glog:
        glog.write("# Audit download session log\n\n")

    # Loop por SET
    for set_code, wants in groups.items():
        if not wants:
            continue

        # Prévia do SET
        prev_lines = [
            f"{BRIGHT}Preview — SET {set_code}{RESET}",
            f"Planned from Audit: {CYAN}{len(wants)}{RESET}",
            "",
            "Will attempt to match and download the following names:"
        ] + preview_names(wants)
        box(prev_lines, color=YELLOW)

        # Modo: auto baixa sem perguntar; caso contrário, pergunta
        if mode == "auto":
            ans = "y"
        else:
            ans = ask_choice(
                f"{BRIGHT}Start downloading this set? {RESET}[Y]es / [S]kip / [Q]uit: ",
                valid=("y","s","q")
            )

        if ans == "q":
            box(["Stopping by user choice."], color=YELLOW)
            return
        if ans == "s":
            box([f"Skipping set {set_code}."], color=YELLOW)
            with open(log_path, "a", encoding="utf-8") as glog:
                glog.write(f"[{set_code}] skipped by user.\n")
            continue

        # Resolve prints do SET
        print(f"\n>>> Resolving set [{set_code}] on Scryfall (prints + extras/variations)... <<<")
        cards = scry_search_cards_for_set(set_code)

        # Index por nome normalizado
        index: Dict[str, List[dict]] = {}
        for c in cards:
            for ent in build_candidate_entries_for_card(c):
                for nm in ent["candidates"]:
                    index.setdefault(nm, []).append(ent)

        set_dir = base_dir / set_code.upper()
        ensure_dir(set_dir)

        planned: List[tuple[Path, dict]] = []
        missing_names: List[str] = []

        for raw in wants:
            m = re.match(r"^(.*?)(\d+)?$", raw.strip())
            if m:
                base_name = m.group(1).strip()
                idx_str   = m.group(2)
            else:
                base_name = raw.strip()
                idx_str   = None

            normalized = normalize_title(base_name)
            entries = index.get(normalized, [])

            if not entries:
                normalized_compact = normalize_title(base_name.replace(" ", ""))
                entries = index.get(normalized_compact, [])

            if not entries:
                gcards = scry_search_global_by_name(base_name)
                if gcards:
                    tmp_entries = []
                    for gc in gcards:
                        tmp_entries.extend(build_candidate_entries_for_card(gc))
                    compat = [e for e in tmp_entries if (normalized in e["candidates"] or normalize_title(base_name.replace(" ", "")) in e["candidates"])]
                    entries = compat

            if not entries:
                missing_names.append(base_name)
                with open(log_path, "a", encoding="utf-8") as glog:
                    glog.write(f"[{set_code}] unmatched from Audit: {base_name}\n")
                continue

            if idx_str:
                try:
                    pos = int(idx_str)
                    chosen = entries[pos - 1] if 1 <= pos <= len(entries) else entries[0]
                    suffix = idx_str
                except Exception:
                    chosen = entries[0]
                    suffix = idx_str
            else:
                chosen = entries[0]
                suffix = ""

            final_stem = f"{base_name}{suffix}.fullborder"
            ext = infer_ext_from_url(chosen["url"])
            out_path = set_dir / f"{slugify_filename(final_stem)}{ext}"
            planned.append((out_path, chosen))

        if not planned and not missing_names:
            box([f"{set_code}: nothing to download."], color=YELLOW)
            continue

        # Baixa (com barra)
        start = time.time()
        ok = 0
        errors = 0

        for out_path, ent in tqdm(planned, desc=f"{set_code} — downloading (Audit)", unit="img"):
            if out_path.exists():
                ok += 1
                continue
            try:
                content = download_bytes_with_retry(ent["url"])

                save_image(
                    content,
                    out_path,
                    card=ent.get("card"),
                    rotate_mode=ent.get("rotate")
                )
                ok += 1

            except requests.exceptions.HTTPError as e:
                errors += 1
                status = e.response.status_code if e.response is not None else "?"
                with open(log_path, "a", encoding="utf-8") as glog:
                    glog.write(f"[{set_code}] HTTP {status} while {out_path.name}\n")

            except Exception as e:
                errors += 1
                with open(log_path, "a", encoding="utf-8") as glog:
                    glog.write(f"[{set_code}] ERROR {e} while {out_path.name}\n")

        elapsed = time.time() - start
        speed = ok / elapsed if elapsed > 0 else 0.0

        # Relatório do SET
        lines = [
            f"{BRIGHT}AUDIT SET{RESET} {set_code} {BRIGHT}completed{RESET}.",
            f"Planned from Audit: {CYAN}{len(wants)}{RESET}",
            f"Downloaded/Found: {GREEN}{ok}{RESET}",
            f"Unmatched in Audit: {YELLOW}{len(missing_names)}{RESET}",
            f"Errors while downloading: {RED}{errors}{RESET}",
            f"Elapsed time: {CYAN}{format_duration(elapsed)}{RESET}",
            f"Average speed: {CYAN}{speed:.2f} images/s{RESET}",
            f"Folder: {set_dir}",
        ]
        box(lines, color=GREEN)

        # Logs por SET
        if missing_names:
            miss_path = set_dir / f"audit_unmatched_{set_code}.log"
            miss_path.write_text("\n".join(missing_names), encoding="utf-8")
            print(YELLOW + f"Unmatched names saved to: {miss_path}" + RESET)

        with open(log_path, "a", encoding="utf-8") as glog:
            glog.write(f"[{set_code}] planned={len(wants)} downloaded={ok} unmatched={len(missing_names)} errors={errors}\n")

    print("")
    box([f"Global log written to: {log_path}", "All done!"], color=CYAN)

# ---------- Standalone ----------
if __name__ == "__main__":
    try:
        audit_download_flow()
    except KeyboardInterrupt:
        print("\nInterrupted.")