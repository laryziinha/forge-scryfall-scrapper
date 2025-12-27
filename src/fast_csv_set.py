# ============================================================
#  Scryfall Image Downloader (Forge Friendly)
#  Author: Laryzinha
#  Version: 1.1.4
#  Description:
#      High-quality Scryfall image downloader with colored UI,
#      batch SET download, Singles integration and Token/Audit support.
# ============================================================

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests

# Optional: PIL for rotation logic (flip rot180, split/aftermath h90). If not available, we skip rotation.
try:
    from PIL import Image
    from io import BytesIO
except Exception:
    Image = None  # type: ignore


SCRYFALL_API = "https://api.scryfall.com"

# Conservative defaults (you can tune later)
API_TIMEOUT = 30
DL_TIMEOUT = 45
API_RETRY = 6
DL_RETRY = 6
BACKOFF_BASE = 1.2
BACKOFF_JITTER = 0.35

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ForgeFastCSV/0.1 (fast-manifest-downloader)"})


INVALID_CHARS_PATTERN = r'[<>:"/\\|?*\x00-\x1F]'


def slugify_filename(name: str) -> str:
    name = (name or "").replace(":", "-").strip()
    name = re.sub(INVALID_CHARS_PATTERN, "_", name)
    name = name.rstrip(" .")
    return name if name else "Unknown"


def safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def is_windows_reserved(code: str) -> bool:
    if os.name != "nt":
        return False
    c = (code or "").strip().upper()
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
    return c in reserved


def safe_set_folder_name(set_code: str) -> str:
    code = slugify_filename((set_code or "UNK").strip().upper())
    code = code.rstrip(" .")
    if is_windows_reserved(code):
        return f"_{code}"
    return code


def sleep_backoff(attempt: int) -> None:
    time.sleep((BACKOFF_BASE ** attempt) + (random.random() * BACKOFF_JITTER))


def api_get_json(url: str, *, params: Optional[dict] = None) -> dict:
    last_exc: Optional[Exception] = None
    for attempt in range(1, API_RETRY + 1):
        try:
            r = SESSION.get(url, params=params, timeout=API_TIMEOUT)
            if r.status_code == 429 or 500 <= r.status_code <= 599:
                raise requests.exceptions.HTTPError(f"HTTP {r.status_code}", response=r)
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
            last_exc = e
            if attempt == API_RETRY:
                raise
            sleep_backoff(attempt)
    raise last_exc or RuntimeError("api_get_json failed")


def dl_get_bytes(url: str) -> bytes:
    last_exc: Optional[Exception] = None
    for attempt in range(1, DL_RETRY + 1):
        try:
            r = SESSION.get(url, stream=True, timeout=DL_TIMEOUT)
            if r.status_code == 429 or 500 <= r.status_code <= 599:
                raise requests.exceptions.HTTPError(f"HTTP {r.status_code}", response=r)
            r.raise_for_status()
            return r.content
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError, OSError) as e:
            last_exc = e
            if attempt == DL_RETRY:
                raise
            sleep_backoff(attempt)
    raise last_exc or RuntimeError("dl_get_bytes failed")


@dataclass(frozen=True)
class ManifestRow:
    set_code: str
    collector_number: str
    scryfall_id: str
    layout: str
    face: int  # 1..N
    image_url: str
    target_filename: str  # only the file name (not full path)
    rotate: str  # "", "rot180", "h90"
    status: str  # "pending" | "done" | "failed"
    error: str


def from_uris(uris: Optional[dict]) -> Optional[str]:
    if not uris:
        return None
    # prefer large (fast default) then png
    return uris.get("large") or uris.get("png") or uris.get("normal") or uris.get("small")


def infer_ext(url: str) -> str:
    u = (url or "").lower()
    if ".png" in u:
        return ".png"
    return ".jpg"


def canonical_name_for_single_image(card: dict) -> str:
    """
    Keep close to your existing behavior:
    - split/aftermath -> concat face names without spaces
    - adventure -> use face[0]
    - otherwise -> card['name']
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


def pick_image_entries(card: dict) -> List[Tuple[str, str, int, str]]:
    """
    Returns list of tuples:
      (url, display_name_for_filename, face_index, rotate_mode)

    Rules:
      - split/aftermath: 1 url, rotate h90 later if image is horizontal (optional PIL)
      - flip: 2 outputs from same url: face1 normal + face2 rot180
      - default single-face: 1 output
      - DFC/multiface: 1 per face
    """
    layout = (card.get("layout") or "").lower()
    out: List[Tuple[str, str, int, str]] = []

    if card.get("image_uris"):
        u = from_uris(card.get("image_uris"))
        if not u:
            return out

        if layout in {"split", "aftermath"}:
            nm = canonical_name_for_single_image(card)
            out.append((u, nm, 1, "h90"))  # rotate only if needed (optional)
            return out

        if layout == "adventure":
            nm = canonical_name_for_single_image(card)
            out.append((u, nm, 1, ""))
            return out

        if layout == "flip":
            faces = card.get("card_faces") or []
            f1 = (faces[0].get("name") if len(faces) > 0 else None) or (card.get("name") or "Unknown")
            f2 = (faces[1].get("name") if len(faces) > 1 else None) or (card.get("name") or "Unknown")
            out.append((u, str(f1).strip(), 1, ""))
            out.append((u, str(f2).strip(), 2, "rot180"))
            return out

        out.append((u, (card.get("name") or "Unknown").strip(), 1, ""))
        return out

    # DFC / faces
    faces = card.get("card_faces") or []
    for i, f in enumerate(faces, start=1):
        u = from_uris(f.get("image_uris"))
        if not u:
            continue
        nm = (f.get("name") or card.get("name") or "Unknown").strip()
        out.append((u, nm, i, ""))
    return out


def build_target_filename(set_code: str, name: str, idx: int, ext: str) -> str:
    """
    Desired pattern (no SET prefix, because folder already represents the set):
      <Name>[2|3...].fullborder.<ext>
    idx starts at 1. idx==1 => no suffix. idx>=2 => suffix number.
    """
    safe_name = slugify_filename(name)
    suffix = "" if idx == 1 else str(idx)
    return f"{safe_name}{suffix}.fullborder{ext}"


def scryfall_cards_for_set(set_code: str) -> List[dict]:
    """
    One paginated call chain:
    /cards/search?q=e:<set>&unique=prints&include_extras=true&include_variations=true
    """
    cards: List[dict] = []
    page = 1
    while True:
        js = api_get_json(
            f"{SCRYFALL_API}/cards/search",
            params={
                "q": f"e:{set_code}",
                "unique": "prints",
                "include_extras": "true",
                "include_variations": "true",
                "order": "set",
                "dir": "asc",
                "page": str(page),
            },
        )
        data = js.get("data") or []
        cards.extend(data)
        if not js.get("has_more"):
            break
        page += 1
    return cards


def write_manifest_csv(path: Path, rows: List[ManifestRow]) -> None:
    safe_mkdir(path.parent)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "set_code", "collector_number", "scryfall_id", "layout", "face",
            "image_url", "target_filename", "rotate", "status", "error"
        ])
        for r in rows:
            w.writerow([
                r.set_code, r.collector_number, r.scryfall_id, r.layout, r.face,
                r.image_url, r.target_filename, r.rotate, r.status, r.error
            ])


def read_manifest_csv(path: Path) -> List[ManifestRow]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        out: List[ManifestRow] = []
        for row in rd:
            out.append(ManifestRow(
                set_code=row.get("set_code", ""),
                collector_number=row.get("collector_number", ""),
                scryfall_id=row.get("scryfall_id", ""),
                layout=row.get("layout", ""),
                face=int(row.get("face", "1") or 1),
                image_url=row.get("image_url", ""),
                target_filename=row.get("target_filename", ""),
                rotate=row.get("rotate", "") or "",
                status=row.get("status", "pending") or "pending",
                error=row.get("error", "") or "",
            ))
        return out


def load_state_done(state_path: Path) -> Dict[str, str]:
    """
    Returns mapping target_filename -> status ("done" or "failed").
    Append-only JSONL file, lines like:
      {"target":"...", "status":"done"}
    """
    done: Dict[str, str] = {}
    if not state_path.exists():
        return done
    with open(state_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                js = json.loads(line)
                t = js.get("target")
                s = js.get("status")
                if t and s:
                    done[str(t)] = str(s)
            except Exception:
                continue
    return done


def append_state(state_path: Path, *, target: str, status: str, error: str = "") -> None:
    safe_mkdir(state_path.parent)
    rec = {"target": target, "status": status}
    if error:
        rec["error"] = error[:300]
    with open(state_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def atomic_write_bytes(final_path: Path, content: bytes) -> None:
    """
    Write to *.part then rename to final.
    """
    tmp = final_path.with_suffix(final_path.suffix + ".part")
    safe_mkdir(final_path.parent)

    with open(tmp, "wb") as f:
        f.write(content)

    # On Windows, replace is atomic-ish; on POSIX rename is atomic.
    os.replace(str(tmp), str(final_path))


def apply_rotation_if_needed(content: bytes, rotate_mode: str) -> bytes:
    """
    If PIL is available:
      - rot180 => rotate 180 and convert to JPG bytes
      - h90 => rotate 90 only if image is horizontal
    Otherwise: return raw bytes.
    """
    if Image is None or not rotate_mode:
        return content

    try:
        img = Image.open(BytesIO(content))
        if rotate_mode == "rot180":
            img = img.rotate(180, expand=True).convert("RGB")
        elif rotate_mode == "h90":
            w, h = img.size
            if w > h:
                img = img.rotate(90, expand=True).convert("RGB")
            else:
                return content
        else:
            return content

        # Always emit JPEG for rotated variants (consistent with your previous behavior)
        out = BytesIO()
        img.save(out, format="JPEG", quality=95, subsampling=0, optimize=True)
        return out.getvalue()
    except Exception:
        return content


def build_manifest_for_set(set_code: str, manifest_path: Path) -> List[ManifestRow]:
    set_code_norm = (set_code or "").strip().lower()
    if not set_code_norm:
        raise ValueError("Empty set code.")

    cards = scryfall_cards_for_set(set_code_norm)

    # Deterministic duplicate suffixing per base key inside this set
    # base key = "<SET>_<slugified name>"
    counters: Dict[str, int] = {}

    rows: List[ManifestRow] = []
    for card in cards:
        sc_id = str(card.get("id") or "")
        layout = str(card.get("layout") or "").lower()
        collector = str(card.get("collector_number") or "")
        set_upper = str(card.get("set") or set_code_norm).upper()

        entries = pick_image_entries(card)
        if not entries:
            continue

        for (url, nm, face_index, rotate) in entries:
            ext = infer_ext(url)
            if rotate in {"rot180", "h90"}:
                ext = ".jpg"

            base_key = slugify_filename(nm)
            counters[base_key] = counters.get(base_key, 0) + 1
            idx = counters[base_key]

            target = build_target_filename(set_upper, nm, idx, ext)

            rows.append(ManifestRow(
                set_code=set_upper,
                collector_number=collector,
                scryfall_id=sc_id,
                layout=layout,
                face=face_index,
                image_url=url,
                target_filename=target,
                rotate=rotate or "",
                status="pending",
                error="",
            ))

    write_manifest_csv(manifest_path, rows)
    return rows


def download_one(row: ManifestRow, out_dir: Path) -> Tuple[str, str, str]:
    """
    Returns (target_filename, status, error)
    """
    final_path = out_dir / row.target_filename

    # already ok?
    if final_path.exists() and final_path.stat().st_size > 0:
        return (row.target_filename, "done", "")

    try:
        content = dl_get_bytes(row.image_url)

        # apply rotation logic if requested (PIL optional)
        content2 = apply_rotation_if_needed(content, row.rotate)

        atomic_write_bytes(final_path, content2)
        return (row.target_filename, "done", "")
    except Exception as e:
        return (row.target_filename, "failed", str(e))


def run_download(manifest_path: Path, out_dir: Path, threads: int) -> None:
    rows = read_manifest_csv(manifest_path)
    state_path = manifest_path.with_suffix(".state.jsonl")

    state = load_state_done(state_path)

    # Filter pending considering:
    # - CSV status
    # - state.jsonl
    # - file exists
    pending: List[ManifestRow] = []
    done_count = 0

    for r in rows:
        fp = out_dir / r.target_filename
        file_ok = fp.exists() and fp.stat().st_size > 0

        st = state.get(r.target_filename)

        # Trust "done" only if the file exists
        if st == "done":
            if file_ok:
                done_count += 1
                continue
            # state says done but file is missing -> must redownload
            pending.append(r)
            continue

        # If file exists, it's done (even if state missing)
        if file_ok:
            done_count += 1
            continue

        pending.append(r)

    print(f"[fastcsv] Manifest: {manifest_path.name}")
    print(f"[fastcsv] Output:   {out_dir}")
    print(f"[fastcsv] Total rows: {len(rows)} | already done: {done_count} | pending: {len(pending)}")
    if not pending:
        print("[fastcsv] Nothing to download.")
        return

    safe_mkdir(out_dir)

    # Concurrency
    ok = 0
    fail = 0
    start = time.time()

    with ThreadPoolExecutor(max_workers=max(1, threads)) as ex:
        futures = {ex.submit(download_one, r, out_dir): r for r in pending}
        for fut in as_completed(futures):
            target, status, err = fut.result()
            if status == "done":
                ok += 1
                append_state(state_path, target=target, status="done")
            else:
                fail += 1
                append_state(state_path, target=target, status="failed", error=err)
                # keep it short in console
                print(f"[fail] {target} :: {err}")

    elapsed = time.time() - start
    speed = ok / elapsed if elapsed > 0 else 0.0
    print(f"[fastcsv] Download finished. ok={ok} fail={fail} elapsed={elapsed:.1f}s speed={speed:.2f} img/s")

    # Update CSV status (rewrite once at end)
    # We merge state into rows:
    state2 = load_state_done(state_path)
    updated: List[ManifestRow] = []
    for r in rows:
        fp = out_dir / r.target_filename
        file_ok = fp.exists() and fp.stat().st_size > 0

        st = r.status
        er = r.error

        st_state = state2.get(r.target_filename)

        if st_state == "done":
            if file_ok:
                st = "done"
                er = ""
            else:
                # state says done but file is missing -> should be pending
                st = "pending"
                er = ""
        elif st_state == "failed":
            st = "failed"
            # keep existing error (if any)
        else:
            # no state info: trust filesystem
            if file_ok:
                st = "done"
                er = ""
            else:
                st = "pending"

        updated.append(ManifestRow(
            set_code=r.set_code,
            collector_number=r.collector_number,
            scryfall_id=r.scryfall_id,
            layout=r.layout,
            face=r.face,
            image_url=r.image_url,
            target_filename=r.target_filename,
            rotate=r.rotate,
            status=st,
            error=er,
        ))

    write_manifest_csv(manifest_path, updated)
    print(f"[fastcsv] CSV updated with status/error.")


def default_paths(root: Path, set_code: str) -> Tuple[Path, Path]:
    """
    root/
      manifests/<SET>.csv
      cards/<SET>/ (or _CON etc)
    """
    set_up = set_code.strip().upper()
    manifests = root / "manifests"
    cards = root / "Cards" / safe_set_folder_name(set_up)
    manifest_path = manifests / f"{set_up}.csv"
    return manifest_path, cards


def main() -> int:
    ap = argparse.ArgumentParser(description="Fast CSV per-set manifest + downloader (resume)")
    ap.add_argument("--set", dest="set_code", required=True, help="Set code (e.g., one, m21, con)")
    ap.add_argument("--mode", choices=["build", "download", "all"], default="all", help="What to do")
    ap.add_argument("--root", default=".", help="Root folder for manifests/ and Cards/")
    ap.add_argument("--threads", type=int, default=16, help="Download threads")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    manifest_path, out_dir = default_paths(root, args.set_code)

    if args.mode in {"build", "all"}:
        print(f"[fastcsv] Building manifest for SET={args.set_code} ...")
        rows = build_manifest_for_set(args.set_code, manifest_path)
        print(f"[fastcsv] Manifest written: {manifest_path} (rows={len(rows)})")

    if args.mode in {"download", "all"}:
        run_download(manifest_path, out_dir, args.threads)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
