# SingleCard.py — Download de cartas individuais (prints)
# Regras implementadas:
#   • Nome limpo: <SET>_<Nome>.fullborder.<ext>
#   • Enumeração por chave (SET+Nome) somente quando há 2+ imagens nessa chave: ,2,3,...
#   • SEMPRE gera lista temporária do que você escolheu (ALL ou ONE),
#     compara com a pasta Singles e baixa apenas o que falta (idempotente).
#   • Tratativas de layout: split/aftermath (1), flip (2 imgs: face2 rot180),
#     DFC (1/face), rotação 90° para horizontais.

import re
import time
import requests
from pathlib import Path
from typing import Dict, List, Tuple, Optional, NamedTuple
from tqdm import tqdm
from PIL import Image
from io import BytesIO

# ---------- UI ----------
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
def _len_vis(s: str) -> int: return len(_ansi_re.sub("", s))

def box(lines: List[str], color=CYAN):
    w = max(_len_vis(t) for t in lines) if lines else 0
    print(color + "╔" + "═" * (w + 2) + "╗" + RESET)
    for t in lines:
        pad = w - _len_vis(t)
        print(color + "║ " + RESET + t + " " * pad + color + " ║" + RESET)
    print(color + "╚" + "═" * (w + 2) + "╝" + RESET)

def banner():
    title = "bconti Single Card Scrapper"
    print(f"{PINK}{'═'*len(title)}\n{title}\n{'═'*len(title)}{RESET}")

def fmt_dur(s: float) -> str:
    if s < 60: return f"{int(s)}s"
    return f"{int(s//60)}m {int(s%60):02d}s"

# ---------- Paths / nomes ----------
def singles_root() -> Path:
    try:
        base = Path(__file__).resolve().parent
    except NameError:
        base = Path.cwd()
    return base / "Singles"

def ensure_dir(p: Path): p.mkdir(parents=True, exist_ok=True)

INVALID_CHARS_PATTERN = r'[<>:"/\\|?*\x00-\x1F]'
def slugify_filename(name: str) -> str:
    name = (name or "").replace(":", "-").strip()
    return re.sub(INVALID_CHARS_PATTERN, "_", name)

def infer_ext(url: str) -> str:
    return ".png" if ".png" in (url or "").lower() else ".jpg"

# ---------- HTTP / Scryfall ----------
SCRYFALL_API = "https://api.scryfall.com"
RATE_SLEEP = 0.12
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "ForgeImageFetcher/1.7 (bconti-scrapper)"})


# ---------- Entradas de imagem ----------
class ImgEntry(NamedTuple):
    url: str
    rotate: Optional[str]  # None | "rot180"

def _from_uris(uris: dict) -> Optional[str]:
    if not uris: return None
    return uris.get("large") or uris.get("png") or uris.get("normal") or uris.get("small")

def pick_image_entries(card: dict) -> List[ImgEntry]:
    """
    - split/aftermath → 1
    - flip → 2 (normal + rot180)
    - DFC → 1 por face
    - default → 1
    (Nome de arquivo SEMPRE usa card['name'], não o da face.)
    """
    entries: List[ImgEntry] = []
    layout = (card.get("layout") or "").lower()

    if card.get("image_uris"):
        u = _from_uris(card["image_uris"])
        if not u: return entries
        if layout in {"split", "aftermath"}:
            entries.append(ImgEntry(u, None))
            return entries
        if layout == "flip":
            entries.append(ImgEntry(u, None))
            entries.append(ImgEntry(u, "rot180"))
            return entries
        entries.append(ImgEntry(u, None))
        return entries

    # DFC / multiface
    for face in (card.get("card_faces") or []):
        u = _from_uris(face.get("image_uris", {}))
        if u: entries.append(ImgEntry(u, None))
    return entries

def should_rotate_h90(card: dict, img: Image.Image) -> bool:
    layout = (card.get("layout") or "").lower()
    if layout not in {"split", "aftermath", "flip"}: return False
    w, h = img.size
    return w > h

def save_image(content: bytes, out_path: Path, card=None, rotate_mode: Optional[str] = None):
    try:
        img = Image.open(BytesIO(content))
        if rotate_mode == "rot180":
            img = img.rotate(180, expand=True).convert("RGB")
            img.save(out_path.with_suffix(".jpg"), quality=95, subsampling=0)
            return
        if should_rotate_h90(card, img):
            img = img.rotate(90, expand=True).convert("RGB")
            img.save(out_path.with_suffix(".jpg"), quality=95, subsampling=0)
            return
    except Exception:
        pass
    with open(out_path, "wb") as f: f.write(content)

# ---------- Scryfall search ----------
def scry_search_by_name_all_prints(name: str) -> List[dict]:
    queries = [
        f'!"{name}" unique:prints include:extras include:variations',
        f'{name} unique:prints include:extras include:variations'
    ]
    for q in queries:
        page = 1
        cards: List[dict] = []
        while True:
            url = f"{SCRYFALL_API}/cards/search?q={requests.utils.quote(q)}&order=set&dir=asc&page={page}"
            r = SESSION.get(url)
            time.sleep(RATE_SLEEP)
            if r.status_code == 404: break
            r.raise_for_status()
            js = r.json()
            cards.extend(js.get("data", []))
            if not js.get("has_more"): break
            page += 1
        if cards: return cards
    return []

# ---------- Scanner da pasta ----------
# Formato de stem (sem extensão): SET_Nome[2|3|...].fullborder
STEM_RE = re.compile(
    r'^(?P<set>[A-Z0-9]{2,5})_(?P<name>.+?)(?P<idx>\d+)?\.fullborder$',
    flags=re.UNICODE
)

def scan_existing(folder: Path) -> Dict[Tuple[str, str], set]:
    """
    Retorna mapa: (SET, slugified_name) -> {índices existentes}
    """
    found: Dict[Tuple[str, str], set] = {}
    for p in folder.glob("*.*"):
        lp = p.name.lower()
        if not (lp.endswith(".fullborder.jpg") or lp.endswith(".fullborder.png")):
            continue
        stem = p.with_suffix("").name  # remove .jpg/.png
        m = STEM_RE.match(stem)
        if not m:  # não aderente ao padrão
            continue
        set_code = m.group("set").upper()
        name_part = m.group("name")  # já está no formato de arquivo
        idx = int(m.group("idx")) if m.group("idx") else 1
        key = (set_code, name_part)
        found.setdefault(key, set()).add(idx)
    return found

# ---------- Planejamento determinístico ----------
class PlannedFile(NamedTuple):
    url: str
    path: Path
    rotate: Optional[str]
    card: dict

def base_noext_for(set_code: str, name: str, index: int) -> str:
    set_code = (set_code or "").upper()
    safe_name = slugify_filename(name)
    suffix = "" if index == 1 else str(index)
    return f"{set_code}_{safe_name}{suffix}.fullborder"

def build_plan_from_selection(selected_cards: List[dict], out_dir: Path) -> Tuple[List[PlannedFile], int]:
    """
    A partir da SELEÇÃO (ALL ou ONE):
      • Agrupa por (SET, Nome) — nome slug no arquivo
      • Conta quantas imagens DEVEM existir nessa chave (somando todos os prints/entradas)
      • Gera a lista alvo de índices [1..F]
      • Compara com o que JÁ EXISTE no disco para essa chave
      • Planeja download apenas dos índices faltantes (caminhos definitivos)
    Retorna (plan, skipped_existing_total)
    """
    ensure_dir(out_dir)
    existing = scan_existing(out_dir)

    # 1) montar lista ordenada de entradas por chave
    per_key_entries: Dict[Tuple[str, str], List[Tuple[dict, ImgEntry]]] = {}
    for card in selected_cards:
        set_code = (card.get("set") or "").upper()
        name = slugify_filename(canonical_single_name(card))  # <- chave usa slug igual ao arquivo
        key = (set_code, name)
        for e in pick_image_entries(card):
            per_key_entries.setdefault(key, []).append((card, e))

    # 2) para cada chave, indices desejados = 1..len(lst)
    plan: List[PlannedFile] = []
    skipped_total = 0
    for key, lst in per_key_entries.items():
        set_code, name_slug = key
        desired_total = len(lst)
        desired_indices = list(range(1, desired_total + 1))
        existing_indices = existing.get(key, set())

        # Associa entradas aos índices desejados em ordem estável
        for desired_idx, (card, entry) in zip(desired_indices, lst):
            base_noext = base_noext_for(set_code, name_slug, desired_idx)
            ext = infer_ext(entry.url)
            out_path = out_dir / f"{base_noext}{ext}"
            if desired_idx in existing_indices or out_path.exists():
                skipped_total += 1
                continue
            plan.append(PlannedFile(entry.url, out_path, entry.rotate, card))

    return plan, skipped_total

# ---------- Execução ----------
def execute_plan(plan: List[PlannedFile]) -> Tuple[int, int]:
    downloaded = 0
    errors = 0
    for pf in tqdm(plan, desc="Downloading", unit="img"):
        try:
            with SESSION.get(pf.url, stream=True) as r:
                time.sleep(RATE_SLEEP)
                if r.status_code != 200:
                    errors += 1
                    continue
                save_image(r.content, pf.path, card=pf.card, rotate_mode=pf.rotate)
                downloaded += 1
        except Exception:
            errors += 1
    return downloaded, errors

# ---------- UI helpers ----------
def next_action_prompt(allow_same_list: bool) -> str:
    """
    Retorna:
      - 'same_list'  -> baixar outra print desta mesma lista (só se allow_same_list=True)
      - 'new_card'   -> pesquisar outra carta
      - 'back'       -> voltar ao menu principal
    """
    if allow_same_list:
        options = [
            f"{CYAN}1){RESET} Download another print from this list",
            f"{CYAN}2){RESET} Search another card",
            f"{CYAN}3){RESET} Back to Main Menu"
        ]
    else:
        options = [
            f"{CYAN}1){RESET} Search another card",
            f"{CYAN}2){RESET} Back to Main Menu"
        ]

    box([f"{BRIGHT}What would you like to do next?{RESET}", ""] + options, CYAN)

    while True:
        ans = input(BRIGHT + "Your choice: " + RESET).strip()
        if allow_same_list:
            if ans == "1": return "same_list"
            if ans == "2": return "new_card"
            if ans == "3": return "back"
        else:
            if ans == "1": return "new_card"
            if ans == "2": return "back"
        print(RED + "Invalid option. Please choose a valid item." + RESET)

def singlecard_intro_box(out_dir: Path):
    box([
        f"{BRIGHT}SINGLE CARD DOWNLOADER{RESET}",
        "",
        "Type a card name and I'll list every print found on Scryfall.",
        "Then you can pick ONE print, or choose ALL.",
        "",
        f"{YELLOW}Tips:{RESET}",
        f" • You can type the full name or a close match.",
        f" • {CYAN}[B]{RESET} to go back to the main menu.",
        f" • ENTER with empty input also returns to the main menu.",
        "",
        f"{YELLOW}Examples:{RESET} Lightning Bolt, Birds of Paradise, Assassin's Trophy",
        "",
        f"{CYAN}Saving pattern:{RESET} <SET>_<Name>[2|3...].fullborder.<ext>",
        f"{CYAN}Folder:{RESET} {out_dir}"
    ], CYAN)

def canonical_single_name(card: dict) -> str:
    """
    Nome canônico para cartas de UMA imagem:
      - adventure: usar a face principal (faces[0].name)
        * detecta por layout OU pela estrutura das faces (Instant/Sorcery 'Adventure')
      - demais: card['name']
    """
    name_full = (card.get("name") or "").strip()
    layout = (card.get("layout") or "").lower()
    faces = card.get("card_faces") or []

    # 1) Se o layout já disser 'adventure', usamos face[0]
    if layout == "adventure" and faces and (faces[0].get("name") or "").strip():
        return faces[0]["name"].strip()

    # 2) Fallback robusto: detectar adventure pela estrutura das faces
    #    (muitas rebalanced/alchemy mantêm name com ' // ' mas não setam layout)
    if faces and len(faces) >= 2:
        second_tline = (faces[1].get("type_line") or "").lower()
        # a face 2 costuma ser 'Instant — Adventure' ou 'Sorcery — Adventure'
        if "adventure" in second_tline or "instant" in second_tline or "sorcery" in second_tline:
            main_face = (faces[0].get("name") or "").strip()
            if main_face:
                return main_face

    # 3) Caso não detecte, usa o nome completo
    return name_full or "Unknown"

def pretty(card: dict) -> str:
    name = card.get("name") or "Unknown"
    setname = card.get("set_name") or ""
    code = (card.get("set") or "").upper()
    col = card.get("collector_number") or "—"
    finish = ", ".join(card.get("finishes", []) or [])
    flags = []
    if card.get("promo"): flags.append("Promo")
    if card.get("full_art"): flags.append("FullArt")
    if card.get("frame_effects"): flags.append("Fx")
    tail = (" — " + ", ".join(flags)) if flags else ""
    return f"{name} — {setname} [{code}] #{col} ({finish}){tail}"

def print_found(cards: List[dict], disp: str):
    # Agrupa por SET, soma quantos prints e captura ano/nome do set
    groups: Dict[str, Dict[str, object]] = {}
    for c in cards:
        code = (c.get("set") or "").upper()
        name = c.get("set_name") or ""
        year = (c.get("released_at") or "")[:4] or "—"
        g = groups.setdefault(code, {"name": name, "year": year, "count": 0})
        g["count"] = int(g["count"]) + 1

    # Ordena: mais recente primeiro (ano desc), depois nome
    rows = sorted(
        groups.items(),
        key=lambda kv: ((kv[1]["year"] or "0000"), (kv[1]["name"] or "")),
        reverse=True
    )

    # Larguras agradáveis (mantém tudo enxuto)
    code_w = max(3, max((len(k) for k, _ in rows), default=3))
    year_w = 4
    name_w = 36  # corta com reticências se passar

    def trim(s: str, n: int) -> str:
        s = s or ""
        return (s[: n - 1] + "…") if len(s) > n else s

    # Cabeçalho + linhas
    header = [f"Found {len(cards)} print(s) across {len(groups)} set(s) for: {disp}", ""]
    body = []
    for code, meta in rows:
        name = trim(str(meta["name"]), name_w)
        year = str(meta["year"])
        count = int(meta["count"])
        body.append(
            f"{CYAN}•{RESET} {code:<{code_w}}  {year:>{year_w}}  "
            f"{name:<{name_w}}  {YELLOW}{count}{RESET} print(s)"
        )

    box(header + body, YELLOW)

    # Lista das prints (mantém como estava)
    lst = [f"{i:>3}) {pretty(c)}" for i, c in enumerate(cards, 1)]
    box(["Available prints:"] + lst, CYAN)


def nothing_to_do(disp: str, folder: Path):
    box([
        f"{BRIGHT}{GREEN}[✓] Nothing to download for:{RESET} {disp}",
        f"{YELLOW}All target files already exist in:{RESET} {folder}",
        "Tip: choose another print number or type a new card name."
    ], YELLOW)

# ---------- Menu ----------
def singlecard_menu(_base: Path):
    out_dir = singles_root()
    ensure_dir(out_dir)

    while True:
        # tela de abertura mais amigável
        singlecard_intro_box(out_dir)

        prompt = (
            BRIGHT
            + f"{CYAN}➤{RESET} Type card name {YELLOW}[ENTER = Back]{RESET}: "
        )
        name = input(prompt).strip()

        # voltar ao menu principal
        if not name or name.lower() in {"b", "back"}:
            return

        print(YELLOW + "Searching on Scryfall..." + RESET)
        cards = scry_search_by_name_all_prints(name)
        if not cards:
            box([f"No results for: {name}"], RED)
            # volta para a tela de intro, sem sair do Singles
            continue

        disp = slugify_filename(cards[0].get("name") or name)

        # (o restante do fluxo — lista de prints/ALL/ONE — permanece igual)
        while True:
            print_found(cards, disp)
            box([
                f"{BRIGHT}Select a print:{RESET}",
                "",
                f" {CYAN}•{RESET} Enter a number {YELLOW}(1..{len(cards)}){RESET}",
                f" {CYAN}•{RESET} {YELLOW}A{RESET} = download ALL prints",
                f" {CYAN}•{RESET} {YELLOW}B{RESET} = return to card search"
            ], CYAN)

            choice = input(
                f"{BRIGHT}{CYAN}➤{RESET} Your choice: "
            ).strip().upper()
            if choice == "B":
                break

            if choice == "A":
                start = time.time()
                plan, skipped = build_plan_from_selection(cards, out_dir)
                if not plan:
                    nothing_to_do(disp, out_dir)
                    break
                dl, er = execute_plan(plan)
                el = time.time() - start
                sp = dl / el if el > 0 else 0.0
                box([
                    f"{BRIGHT}ALL prints completed for:{RESET} {disp}",
                    f"Downloaded: {GREEN}{dl}{RESET}",
                    f"Skipped (already existed): {YELLOW}{skipped}{RESET}",
                    f"Errors: {RED}{er}{RESET}",
                    f"Elapsed: {fmt_dur(el)}",
                    f"Speed: {sp:.2f} img/s",
                    f"Folder: {out_dir}"
                ], GREEN)
                action = next_action_prompt(allow_same_list=False)
                if action == "new_card":
                    # sai do while interno (lista desta carta) e volta para pedir outro nome
                    break
                elif action == "back":
                    # volta imediatamente ao menu principal do Downloader
                    return

            # ONE
            try:
                idx = int(choice)
                if idx < 1 or idx > len(cards): raise ValueError()
            except Exception:
                print(RED + "Invalid choice." + RESET)
                continue

            chosen = [cards[idx - 1]]
            start = time.time()
            plan, skipped = build_plan_from_selection(chosen, out_dir)
            if not plan:
                nothing_to_do(pretty(chosen[0]), out_dir)
                continue
            dl, er = execute_plan(plan)
            el = time.time() - start
            sp = dl / el if el > 0 else 0.0
            box([
                f"{BRIGHT}Download finished for:{RESET} {pretty(chosen[0])}",
                f"Downloaded: {GREEN}{dl}{RESET}",
                f"Skipped (already existed): {YELLOW}{skipped}{RESET}",
                f"Errors: {RED}{er}{RESET}",
                f"Elapsed: {fmt_dur(el)}",
                f"Speed: {sp:.2f} img/s",
                f"Folder: {out_dir}"
            ], GREEN)

            action = next_action_prompt(allow_same_list=True)
            if action == "same_list":
                # continua no while interno → mostra novamente a mesma lista de prints
                continue
            elif action == "new_card":
                # sai do while interno → volta para a intro e pede outro nome
                break
            elif action == "back":
                # retorna ao menu principal do Downloader
                return

# ---------- Standalone ----------
def main():
    banner()
    singlecard_menu(Path.cwd())

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
