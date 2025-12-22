# ============================================================
#  Scryfall Image Downloader (Forge Friendly)
#  Author: Laryzinha
#  Version: 1.1.2
#  Description:
#      High-quality Scryfall image downloader with colored UI,
#      batch SET download, Singles integration and Token/Audit support.
# ============================================================

import os
import re
import time
import difflib
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple, NamedTuple

import requests
from PIL import Image
from io import BytesIO
from tqdm import tqdm

SCRYFALL_API = "https://api.scryfall.com"
RATE_SLEEP = 0.12  # keep below 10 req/s limit
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "SetOnlyDownloader/1.0 (forge-friendly)"})

# -------------------- Helpers --------------------

def script_root_cards() -> Path:
    try:
        base = Path(__file__).resolve().parent
    except NameError:
        base = Path.cwd()
    return base / "Cards"

def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def slugify_filename(name: str) -> str:
    name = (name or "Unknown").strip().replace(":", "-")
    return re.sub(r'[<>:\"/\\|?*\x00-\x1F]', "_", name)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def get_all_sets() -> List[dict]:
    r = SESSION.get(f"{SCRYFALL_API}/sets")
    time.sleep(RATE_SLEEP)
    r.raise_for_status()
    return r.json().get("data", [])

def fuzzy_match_set(user_text: str, sets_meta: List[dict]) -> Optional[dict]:
    raw = user_text.strip()
    lower = raw.lower()
    noacc = strip_accents(lower)

    # quick exact matches
    for s in sets_meta:
        if lower == (s.get("code") or "").lower(): return s
        if lower == (s.get("mtgo_code") or "").lower(): return s
        if lower == (s.get("arena_code") or "").lower(): return s

    # by name
    names = [strip_accents((s.get("name") or "").lower()) for s in sets_meta]
    if noacc in names:
        return sets_meta[names.index(noacc)]
    best = difflib.get_close_matches(noacc, names, n=1, cutoff=0.7)
    if best:
        return sets_meta[names.index(best[0])]

    # by code similarity
    codes = [(s.get("code") or "").lower() for s in sets_meta]
    bestc = difflib.get_close_matches(lower, codes, n=1, cutoff=0.6)
    if bestc:
        return sets_meta[codes.index(bestc[0])]
    return None

def scry_search_cards_for_set(set_code: str) -> List[dict]:
    cards = []
    q = f"e:{set_code}"
    page = 1
    while True:
        url = (
            f"{SCRYFALL_API}/cards/search"
            f"?q={requests.utils.quote(q)}"
            f"&order=set&dir=asc&unique=prints"
            f"&include_extras=true&include_variations=true&page={page}"
        )
        r = SESSION.get(url)
        time.sleep(RATE_SLEEP)
        if r.status_code == 404:
            break
        r.raise_for_status()
        js = r.json()
        cards.extend(js.get("data", []))
        if not js.get("has_more"):
            break
        page += 1
    return cards

def pick_image_uri(uris: Optional[Dict]) -> Optional[str]:
    if not uris: return None
    return uris.get("png") or uris.get("large") or uris.get("normal") or uris.get("small")

def preferred_title(card: Dict) -> str:
    return (card.get("flavor_name") or card.get("printed_name") or card.get("name") or "Unknown").strip()

def preferred_face_title(face: Dict) -> str:
    return (face.get("flavor_name") or face.get("printed_name") or face.get("name") or "Unknown").strip()

def concat_faces_preferred(faces: List[Dict]) -> str:
    parts = [re.sub(r"[^A-Za-z0-9]+", "", preferred_face_title(f)) for f in (faces or [])]
    return "".join(parts) if parts else "Unknown"

class ImgEntry(NamedTuple):
    url: str
    name: str
    rotate: Optional[str] = None  # None | "rot180"

def build_entries(card: Dict) -> List[ImgEntry]:
    layout = (card.get("layout") or "").lower()
    out: List[ImgEntry] = []

    if card.get("image_uris"):
        url = pick_image_uri(card["image_uris"])
        if not url:
            return out

        if layout in {"split", "aftermath"}:
            faces = card.get("card_faces") or []
            combined = concat_faces_preferred(faces)
            out.append(ImgEntry(url, combined, None))
            return out

        if layout == "adventure":
            faces = card.get("card_faces") or []
            main_title = preferred_face_title(faces[0]) if faces else preferred_title(card)
            out.append(ImgEntry(url, main_title, None))
            return out

        if layout == "flip":
            faces = card.get("card_faces") or []
            front = preferred_face_title(faces[0]) if faces else preferred_title(card)
            back = preferred_face_title(faces[1]) if len(faces) > 1 else front
            out.append(ImgEntry(url, front, None))
            out.append(ImgEntry(url, back, "rot180"))
            return out

        out.append(ImgEntry(url, preferred_title(card), None))
        return out

    # faces with their own image_uris (DFC etc.)
    faces = card.get("card_faces") or []
    for face in faces:
        url = pick_image_uri(face.get("image_uris"))
        if url:
            out.append(ImgEntry(url, preferred_face_title(face), None))
    return out

def should_rotate_h90(card: dict, img: Image.Image) -> bool:
    layout = (card.get("layout") or "").lower()
    horizontal_layouts = {"split", "aftermath", "flip"}
    w, h = img.size
    return (w > h) and (layout in horizontal_layouts)

def infer_ext_from_url(url: str) -> str:
    return ".png" if ".png" in url.lower() else ".jpg"

def save_image(content: bytes, out_path: Path, card=None, rotate_mode: Optional[str]=None):
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

# -------------------- One-shot flow --------------------

def run_once():
    print("\n=== Set Downloader (printed-name first) ===\n")
    sets_meta = get_all_sets()
    while True:
        q = input("Type the SET code or name (e.g., SLD, 'Arena Anthology'): ").strip()
        m = fuzzy_match_set(q, sets_meta)
        if not m:
            print("Set not found, try again.")
            continue
        code = (m.get("code") or '').upper()
        name = m.get("name") or 'Unknown'
        ok = input(f"Download {name} [{code}]? [Y/n]: ").strip().lower()
        if ok in {"", "y", "yes"}:
            chosen = m
            break

    out_root = script_root_cards()
    ensure_dir(out_root)
    set_dir = out_root / code
    ensure_dir(set_dir)

    # if exists, ask policy
    if any(set_dir.iterdir()):
        print(f"\nFolder exists: {set_dir}")
        print("  1) Keep and skip existing (default)")
        print("  2) Overwrite existing files")
        print("  3) Clean folder and redownload")
        opt = input("Choose [1-3]: ").strip()
        if opt == "3":
            # clean all files
            for p in set_dir.iterdir():
                try:
                    if p.is_file():
                        p.unlink()
                except Exception:
                    pass
        exist_mode = "overwrite" if opt == "2" else "skip"
    else:
        exist_mode = "skip"

    print("\nQuerying Scryfall...")
    cards = scry_search_cards_for_set(code)

    downloaded = 0
    skipped = 0
    errors = 0
    name_counts = {}

    pbar = tqdm(cards, desc=f"[{code}] downloading", unit="card", dynamic_ncols=True)
    for card in pbar:
        label = (card.get("name") or "").replace("\n", " ").strip()
        if label:
            pbar.set_postfix_str(label[:42])

        entries = build_entries(card)
        if not entries:
            skipped += 1
            continue

        for entry in entries:
            base_name = slugify_filename(entry.name)
            ext = infer_ext_from_url(entry.url)
            # de-duplicate: enumerate same base names (ChaosEmerald, ChaosEmerald2, ...)
            cnt = name_counts.get(base_name, 0) + 1
            name_counts[base_name] = cnt
            suffix = "" if cnt == 1 else str(cnt)
            final_name = f"{base_name}{suffix}.fullborder{ext}"
            out_path = set_dir / final_name

            if out_path.exists() and exist_mode == "skip":
                skipped += 1
                continue

            try:
                r = SESSION.get(entry.url, stream=True)
                time.sleep(RATE_SLEEP)
                if r.status_code != 200:
                    errors += 1
                    continue
                save_image(r.content, out_path, card=card, rotate_mode=entry.rotate)
                downloaded += 1
            except Exception:
                errors += 1

    pbar.close()
    print(f"\nDone: {downloaded} files; skipped {skipped}; errors {errors}.")
    print(f"Output: {set_dir}")

if __name__ == "__main__":
    try:
        run_once()
    except KeyboardInterrupt:
        print("\nCancelled by user.")
