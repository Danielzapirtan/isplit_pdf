"""
PDF Auto-Segmentation Tool
Detectează automat capitolele dintr-un PDF și le extrage în fișiere separate.
Strategii de detecție (în ordine de prioritate):
  1. Outline/bookmarks (nivel 1)
  2. Analiza tipografică: font size, bold, numerotare capitol
"""

import os
import re
import sys
from pathlib import Path

try:
    import pdfplumber
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("Instalează dependențele necesare:")
    print("  pip install pypdf pdfplumber")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sanitize_filename(name: str, max_len: int = 80) -> str:
    """Curăță un șir pentru a putea fi folosit ca nume de fișier."""
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = re.sub(r'\s+', " ", name).strip()
    return name[:max_len] if name else "capitol_fara_titlu"


def extract_outline_chapters(reader: PdfReader):
    """
    Încearcă să extragă capitolele de nivel 1 din outline/bookmarks.
    Returnează lista [(titlu, page_index_0based)] sau [] dacă nu există outline.
    """
    try:
        outline = reader.outline
    except Exception:
        return []

    if not outline:
        return []

    chapters = []

    def _page_index(dest):
        """Returnează indexul paginii (0-based) pentru un destination."""
        try:
            return reader.get_destination_page_number(dest)
        except Exception:
            return None

    def _walk(items, depth=0):
        for item in items:
            if isinstance(item, list):
                # Sub-nivel — ignorăm pentru detecție la nivel 1
                if depth == 0:
                    _walk(item, depth + 1)
            else:
                try:
                    title = item.title if hasattr(item, "title") else str(item)
                    pg = _page_index(item)
                    if pg is not None and depth == 0:
                        chapters.append((title.strip(), pg))
                except Exception:
                    pass

    _walk(outline)
    return chapters


# ---------------------------------------------------------------------------
# Detecție tipografică
# ---------------------------------------------------------------------------

# Patternuri pentru titluri de capitol
CHAPTER_PATTERNS = [
    re.compile(r'^(chapter|capitolul?|cap\.?|part|partea|section|secțiunea?)\s+\w+', re.IGNORECASE),
    re.compile(r'^(chapter|capitolul?|cap\.?|part|partea)\s+\d+', re.IGNORECASE),
    re.compile(r'^\d+[\.\)]\s+[A-ZĂÂÎȘȚ]'),          # "1. Titlu"
    re.compile(r'^[IVXLCDM]+[\.\)]\s+[A-ZĂÂÎȘȚ]'),   # "I. Titlu" (roman)
]


def looks_like_chapter_heading(text: str, font_size: float,
                                median_size: float, is_bold: bool) -> bool:
    """Euristică: decide dacă un bloc de text este un titlu de capitol."""
    text = text.strip()
    if not text or len(text) > 200:
        return False

    # Criteriu 1: font mai mare decât mediana cu minim 20%
    size_ratio = font_size / median_size if median_size > 0 else 1.0
    big_font = size_ratio >= 1.20

    # Criteriu 2: bold
    # Criteriu 3: conținut care se potrivește cu patternuri tipice
    pattern_match = any(p.match(text) for p in CHAPTER_PATTERNS)

    return (big_font or is_bold) and (pattern_match or big_font)


def extract_page_typography(pdf_path: str):
    """
    Extrage, pentru fiecare pagină, lista de blocuri de text cu atribute tipografice.
    Returnează: {page_index: [(text, font_size, is_bold), ...]}
    """
    pages_info = {}
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            chars = page.chars  # listă de caractere cu metadate
            if not chars:
                pages_info[i] = []
                continue

            # Grupăm caracterele în cuvinte/rânduri pe baza poziției y
            lines = {}
            for ch in chars:
                y_key = round(ch["top"], 1)
                if y_key not in lines:
                    lines[y_key] = []
                lines[y_key].append(ch)

            blocks = []
            for y_key in sorted(lines.keys()):
                line_chars = lines[y_key]
                text = "".join(c["text"] for c in line_chars).strip()
                if not text:
                    continue
                sizes = [c.get("size", 0) for c in line_chars if c.get("size")]
                avg_size = sum(sizes) / len(sizes) if sizes else 0
                fonts = [c.get("fontname", "") for c in line_chars]
                is_bold = any("Bold" in f or "bold" in f or "BD" in f for f in fonts)
                blocks.append((text, avg_size, is_bold))

            pages_info[i] = blocks
    return pages_info


def compute_median_font_size(pages_info: dict) -> float:
    """Calculează mărimea mediană a fontului din tot documentul."""
    all_sizes = []
    for blocks in pages_info.values():
        for _, size, _ in blocks:
            if size > 0:
                all_sizes.append(size)
    if not all_sizes:
        return 12.0
    all_sizes.sort()
    mid = len(all_sizes) // 2
    return all_sizes[mid]


def detect_chapters_typographic(pages_info: dict, total_pages: int):
    """
    Detectează titlurile de capitol prin analiza tipografică.
    Returnează [(titlu, page_index_0based)].
    """
    median_size = compute_median_font_size(pages_info)
    chapters = []
    seen_pages = set()

    for page_idx in range(total_pages):
        blocks = pages_info.get(page_idx, [])
        for text, size, is_bold in blocks:
            if page_idx in seen_pages:
                break
            if looks_like_chapter_heading(text, size, median_size, is_bold):
                chapters.append((text, page_idx))
                seen_pages.add(page_idx)
                break  # un singur heading per pagină

    return chapters


# ---------------------------------------------------------------------------
# Construire intervale pagini
# ---------------------------------------------------------------------------

def build_page_ranges(chapters, total_pages: int):
    """
    Din lista [(titlu, start_page)], construiește intervalele [start, end).
    Returnează [(titlu, start_0based, end_0based_exclusive)].
    """
    if not chapters:
        return []

    ranges = []
    for i, (title, start) in enumerate(chapters):
        end = chapters[i + 1][1] if i + 1 < len(chapters) else total_pages
        ranges.append((title, start, end))
    return ranges


# ---------------------------------------------------------------------------
# Salvare capitole
# ---------------------------------------------------------------------------

def save_chapters(pdf_path: str, ranges, output_dir: str):
    """Salvează fiecare capitol ca fișier PDF separat."""
    reader = PdfReader(pdf_path)
    total = len(reader.pages)
    saved = []

    for idx, (title, start, end) in enumerate(ranges, 1):
        writer = PdfWriter()
        for page_idx in range(start, min(end, total)):
            writer.add_page(reader.pages[page_idx])

        safe_title = sanitize_filename(title)
        filename = f"{idx:02d}_{safe_title}.pdf"
        out_path = os.path.join(output_dir, filename)

        with open(out_path, "wb") as f:
            writer.write(f)

        saved.append((title, start + 1, min(end, total), out_path))
        print(f"  [{idx:02d}] Pagini {start+1}–{min(end, total):>3}  →  {filename}")

    return saved


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    pdf_path = input("Calea către fișierul PDF: ").strip().strip('"').strip("'")

    if not os.path.isfile(pdf_path):
        print(f"Eroare: fișierul '{pdf_path}' nu există.")
        sys.exit(1)

    print(f"\nAnalizez: {pdf_path}")

    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    print(f"Total pagini: {total_pages}")

    # --- Strategie 1: Outline/Bookmarks ---
    print("\n[1/2] Caut outline/bookmarks...")
    chapters = extract_outline_chapters(reader)

    if chapters:
        print(f"  ✓ Găsite {len(chapters)} capitole din outline.")
        detection_method = "outline"
    else:
        print("  ✗ Outline indisponibil sau gol. Trec la analiza tipografică...")

        # --- Strategie 2: Analiză tipografică ---
        print("[2/2] Analizez tipografia documentului (poate dura câteva secunde)...")
        pages_info = extract_page_typography(pdf_path)
        chapters = detect_chapters_typographic(pages_info, total_pages)
        detection_method = "tipografic"

        if chapters:
            print(f"  ✓ Găsite {len(chapters)} capitole prin analiză tipografică.")
        else:
            print("  ✗ Nu am putut detecta automat capitolele.")
            print("  Documentul va fi exportat ca un singur fișier.")
            chapters = [("Document complet", 0)]
            detection_method = "fallback"

    # --- Afișare capitole detectate ---
    print(f"\nCapitole detectate (metodă: {detection_method}):")
    for i, (title, pg) in enumerate(chapters, 1):
        print(f"  {i:>2}. Pagina {pg+1:>4}  —  {title}")

    # --- Construire intervale ---
    ranges = build_page_ranges(chapters, total_pages)

    # --- Director de ieșire ---
    pdf_stem = Path(pdf_path).stem
    output_dir = os.path.join(os.path.dirname(os.path.abspath(pdf_path)),
                              f"{pdf_stem}_capitole")
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nSalvez capitolele în: {output_dir}")
    print("-" * 60)

    # --- Salvare ---
    saved = save_chapters(pdf_path, ranges, output_dir)

    print("-" * 60)
    print(f"\n✓ Gata! {len(saved)} fișiere salvate în '{output_dir}'.")


if __name__ == "__main__":
    main()
