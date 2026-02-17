import PyPDF2
from PyPDF2 import PdfReader, PdfWriter
import re
from typing import Dict, List, Optional, Tuple
import os
from dataclasses import dataclass
import fitz  # PyMuPDF
from collections import defaultdict


# ---------------------------------------------------------------------------
# Roman-numeral helpers
# ---------------------------------------------------------------------------

_ROMAN_RE = re.compile(
    r'^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$',
    re.IGNORECASE,
)

def _roman_to_int(s: str) -> Optional[int]:
    """Convert a roman-numeral string to an integer, or return None if invalid."""
    s = s.strip().upper()
    if not s or not _ROMAN_RE.match(s):
        return None
    val = {'I': 1, 'V': 5, 'X': 10, 'L': 50,
           'C': 100, 'D': 500, 'M': 1000}
    result = 0
    prev = 0
    for ch in reversed(s):
        v = val[ch]
        result += v if v >= prev else -v
        prev = v
    return result if result > 0 else None


def _int_to_roman(n: int) -> str:
    """Convert a positive integer to a roman numeral string."""
    val  = [1000, 900, 500, 400, 100,  90,  50,  40,  10,   9,   5,   4,   1]
    syms = [ 'M','CM',  'D','CD',  'C','XC',  'L','XL',  'X','IX',  'V','IV',  'I']
    result = ''
    for v, s in zip(val, syms):
        while n >= v:
            result += s
            n -= v
    return result


def _int_to_alpha(n: int) -> str:
    """Convert a positive integer to an alphabetic label (A, B, …, Z, AA, …)."""
    result = ''
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(ord('A') + rem) + result
    return result


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class Chapter:
    """Clasă pentru stocarea informațiilor despre un capitol"""
    title: str
    start_page: int          # 1-based PDF page index
    end_page: Optional[int] = None
    level: int = 1


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class PDFChapterSegmenter:
    def __init__(self, pdf_path: str):
        """
        Inițializează segmentatorul cu calea către PDF

        Args:
            pdf_path: Calea către fișierul PDF
        """
        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"Fișierul PDF nu a fost găsit: {pdf_path}")

        self.pdf_path = pdf_path
        self.pdf_document = fitz.open(pdf_path)
        self.reader = PdfReader(pdf_path)
        self.chapters: List[Chapter] = []
        self.total_pages = len(self.pdf_document)

        # Build label → pdf_index map once; used by TOC extraction.
        self._label_to_pdf_index: Dict[str, int] = self._build_label_map()

    # ------------------------------------------------------------------
    # Page-label / offset infrastructure
    # ------------------------------------------------------------------

    def _build_label_map(self) -> Dict[str, int]:
        """
        Build a dict mapping every printed page label (e.g. 'i', 'ii', '1', '2')
        to its 0-based PDF page index.

        Strategy (in priority order):
        A. fitz Page.get_label() – reads PageLabels from the PDF catalog.
        B. Parse /PageLabels via PyPDF2.
        C. Heuristic text scan of page headers/footers.
        """
        label_map: Dict[str, int] = {}

        # --- Method A: fitz PageLabels (most reliable, fitz >= 1.23) ---
        if hasattr(fitz.Page, 'get_label'):
            for idx in range(self.total_pages):
                try:
                    label = self.pdf_document[idx].get_label()
                    if label:
                        label_map[label.strip().lower()] = idx
                        label_map[label.strip()] = idx
                except Exception:
                    pass
            if label_map:
                return label_map

        # --- Method B: parse /PageLabels via PyPDF2 ---
        try:
            catalog = self.reader.trailer['/Root']
            if '/PageLabels' in catalog:
                pl = catalog['/PageLabels']
                nums = pl.get('/Nums', [])
                ranges_raw: List[Tuple] = []
                for i in range(0, len(nums) - 1, 2):
                    start_idx = int(nums[i])
                    label_dict = nums[i + 1]
                    style  = label_dict.get('/S', None)
                    prefix = str(label_dict.get('/P', ''))
                    first  = int(label_dict.get('/St', 1))
                    ranges_raw.append((start_idx, style, prefix, first))

                for ri, (start_idx, style, prefix, first) in enumerate(ranges_raw):
                    end_idx = ranges_raw[ri + 1][0] if ri + 1 < len(ranges_raw) else self.total_pages
                    for pdf_idx in range(start_idx, end_idx):
                        offset = pdf_idx - start_idx
                        n = first + offset
                        if style is None:
                            label = prefix
                        elif style == '/D':
                            label = prefix + str(n)
                        elif style == '/r':
                            label = prefix + _int_to_roman(n).lower()
                        elif style == '/R':
                            label = prefix + _int_to_roman(n).upper()
                        elif style == '/a':
                            label = prefix + _int_to_alpha(n).lower()
                        elif style == '/A':
                            label = prefix + _int_to_alpha(n).upper()
                        else:
                            label = prefix + str(n)
                        label_map[label.strip().lower()] = pdf_idx
                        label_map[label.strip()] = pdf_idx

                if label_map:
                    return label_map
        except Exception:
            pass

        # --- Method C: heuristic header/footer scan ---
        for idx in range(self.total_pages):
            try:
                page = self.pdf_document[idx]
                h = page.rect.height
                w = page.rect.width
                for clip in (
                    fitz.Rect(0, 0, w, h * 0.12),
                    fitz.Rect(0, h * 0.88, w, h),
                ):
                    region = page.get_text(clip=clip).strip()
                    m = re.search(
                        r'(?<!\w)([ivxlcdmIVXLCDM]{1,10}|\d{1,6})(?!\w)',
                        region,
                    )
                    if m:
                        token = m.group(1).strip()
                        label_map.setdefault(token.lower(), idx)
                        label_map.setdefault(token, idx)
                        break
            except Exception:
                pass

        return label_map

    def _printed_page_to_pdf_index(self, printed: str) -> Optional[int]:
        """
        Convert a printed page label (arabic or roman) to a 0-based PDF index.

        Strategy:
        1. Direct lookup in the pre-built label map.
        2. For roman numerals, compare decoded integer values.
        3. For arabic numbers, estimate offset from the label map and validate
           by checking whether the candidate page actually displays that number
           in its header/footer.
        4. Linear scan as last resort.
        """
        printed = printed.strip()
        printed_lower = printed.lower()

        # 1. Direct lookup
        if printed_lower in self._label_to_pdf_index:
            return self._label_to_pdf_index[printed_lower]
        if printed in self._label_to_pdf_index:
            return self._label_to_pdf_index[printed]

        # 2. Roman numeral match by decoded value
        roman_val = _roman_to_int(printed)
        if roman_val is not None:
            for label, idx in self._label_to_pdf_index.items():
                if _roman_to_int(label) == roman_val:
                    return idx

        # 3. Arabic: offset estimation + local validation
        try:
            arabic = int(printed)
        except ValueError:
            return None

        offsets: Dict[int, int] = defaultdict(int)
        for label, idx in self._label_to_pdf_index.items():
            try:
                lv = int(label)
                offsets[idx - lv] += 1
            except ValueError:
                pass

        if offsets:
            best_offset = max(offsets, key=lambda k: offsets[k])
            candidate = arabic + best_offset - 1  # 0-based
            if 0 <= candidate < self.total_pages:
                if self._page_contains_number(candidate, arabic):
                    return candidate
            # Search ±5 pages around candidate
            for delta in range(1, 6):
                for c in (candidate - delta, candidate + delta):
                    if 0 <= c < self.total_pages and self._page_contains_number(c, arabic):
                        return c

        # 4. Full linear scan
        for idx in range(self.total_pages):
            if self._page_contains_number(idx, arabic):
                return idx

        return None

    def _page_contains_number(self, pdf_idx: int, number: int) -> bool:
        """
        Return True if the header or footer of page pdf_idx contains
        ``number`` as a standalone numeric token.
        """
        try:
            page = self.pdf_document[pdf_idx]
            h = page.rect.height
            w = page.rect.width
            for clip in (
                fitz.Rect(0, 0, w, h * 0.12),
                fitz.Rect(0, h * 0.88, w, h),
            ):
                txt = page.get_text(clip=clip)
                if re.search(rf'(?<!\d){re.escape(str(number))}(?!\d)', txt):
                    return True
        except Exception:
            pass
        return False

    # ------------------------------------------------------------------
    # Chapter extraction methods
    # ------------------------------------------------------------------

    def extract_chapters_from_outline(self) -> List[Chapter]:
        """
        Extrage capitolele din outline-ul/bookmarks-ul PDF-ului
        """
        chapters: List[Chapter] = []

        if hasattr(self.reader, 'outline') and self.reader.outline:
            outline = self.reader.outline

            def process_outline_item(item, level: int = 1):
                if isinstance(item, list):
                    for subitem in item:
                        process_outline_item(subitem, level + 1)
                else:
                    title    = item.get('/Title') if hasattr(item, 'get') else None
                    page_ref = item.get('/Page')  if hasattr(item, 'get') else None

                    if title and page_ref is not None:
                        try:
                            if isinstance(page_ref, PyPDF2.generic.IndirectObject):
                                page_num = None
                                for idx, p in enumerate(self.reader.pages):
                                    if p.indirect_reference == page_ref:
                                        page_num = idx + 1  # 1-based
                                        break
                                if page_num is None:
                                    return
                            else:
                                page_num = int(page_ref) + 1

                            page_num = max(1, min(page_num, self.total_pages))
                            chapters.append(Chapter(title=str(title), start_page=page_num, level=level))
                        except (ValueError, TypeError):
                            pass

            process_outline_item(outline)
            chapters.sort(key=lambda x: x.start_page)

            for i in range(len(chapters) - 1):
                chapters[i].end_page = chapters[i + 1].start_page - 1
            if chapters:
                chapters[-1].end_page = self.total_pages

        return chapters

    def extract_chapters_by_formatting(self, font_threshold: float = 0.8) -> List[Chapter]:
        """
        Extrage capitolele pe baza formatării textului (font size, stil)
        """
        potential_chapters: List[Chapter] = []

        title_patterns = [
            r'^Capitolul\s+\d+',
            r'^Chapter\s+\d+',
            r'^\d+\.\s+[A-Z]',
            r'^[IVXLCDM]+\.\s+',
            r'^[A-Z][a-z]+\s+\d+',
        ]

        for page_num in range(self.total_pages):
            page   = self.pdf_document[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"].strip()
                            if text and 3 < len(text) < 200:
                                for pattern in title_patterns:
                                    if re.match(pattern, text, re.IGNORECASE):
                                        potential_chapters.append(Chapter(
                                            title=text,
                                            start_page=page_num + 1,
                                            level=1,
                                        ))
                                        break

        unique_chapters: List[Chapter] = []
        seen_titles: set = set()
        for chapter in potential_chapters:
            if chapter.title not in seen_titles:
                seen_titles.add(chapter.title)
                unique_chapters.append(chapter)

        unique_chapters.sort(key=lambda x: x.start_page)

        for i in range(len(unique_chapters) - 1):
            unique_chapters[i].end_page = unique_chapters[i + 1].start_page - 1
        if unique_chapters:
            unique_chapters[-1].end_page = self.total_pages

        return unique_chapters

    def extract_chapters_by_table_of_contents(self) -> List[Chapter]:
        """
        Extrage capitolele analizând cuprinsul.

        Handles:
        - TOC pages that carry roman-numeral page numbers (i, ii, iii …)
        - TOC entries that reference roman-numeral pages (front-matter)
        - Book page numbers that differ from PDF page indices (offset / front-matter)
        - Multi-page TOCs
        """
        # Signals that a page is (or contains) a TOC
        toc_heading_re = re.compile(
            r'\b(Cuprins|Contents|Table\s+of\s+Contents|Tabla\s+de\s+Materii)\b',
            re.IGNORECASE,
        )
        # A TOC entry: arbitrary text, then a run of dots/dashes/spaces, then a
        # page token (arabic or roman), optionally followed by trailing whitespace.
        toc_line_re = re.compile(
            r'^(.+?)'                                    # title (non-greedy)
            r'[\s.\-–—_]{2,}'                            # separator run (≥2 chars)
            r'([ivxlcdmIVXLCDM]{1,10}|\d{1,6})'         # page token
            r'\s*$',
        )

        # ------------------------------------------------------------------
        # Step 1 – locate TOC page(s)
        # Search the first 20% of the document (or first 20 pages) for a TOC.
        # ------------------------------------------------------------------
        scan_limit = min(self.total_pages, max(20, self.total_pages // 5))
        toc_pdf_pages: List[int] = []

        for scan_idx in range(scan_limit):
            page = self.pdf_document[scan_idx]
            text = page.get_text()
            if toc_heading_re.search(text):
                toc_pdf_pages.append(scan_idx)

        # Fallback: pages dense with leader dots even without an explicit heading
        if not toc_pdf_pages:
            for scan_idx in range(scan_limit):
                page = self.pdf_document[scan_idx]
                text = page.get_text()
                if len(re.findall(r'\.{3,}', text)) >= 3:
                    toc_pdf_pages.append(scan_idx)

        if not toc_pdf_pages:
            return []

        # ------------------------------------------------------------------
        # Step 2 – extend to adjacent pages (multi-page TOC)
        # ------------------------------------------------------------------
        pages_to_scan: set = set(toc_pdf_pages)
        for p in sorted(toc_pdf_pages):
            for delta in range(1, 5):
                nxt = p + delta
                if nxt >= self.total_pages:
                    break
                nxt_text = self.pdf_document[nxt].get_text()
                has_leaders = len(re.findall(r'\.{2,}', nxt_text)) >= 2
                has_heading  = toc_heading_re.search(nxt_text) is not None
                if has_leaders or has_heading:
                    pages_to_scan.add(nxt)
                else:
                    break   # stop extending once we hit a non-TOC page

        # ------------------------------------------------------------------
        # Step 3 – extract raw (title, page_token) pairs
        # ------------------------------------------------------------------
        raw_entries: List[Tuple[str, str]] = []

        for scan_idx in sorted(pages_to_scan):
            page = self.pdf_document[scan_idx]
            text = page.get_text()
            lines = text.split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                m = toc_line_re.match(line)
                if m:
                    title       = m.group(1).strip(' .\-–—_')
                    page_token  = m.group(2).strip()
                    if title and page_token:
                        raw_entries.append((title, page_token))

        # ------------------------------------------------------------------
        # Step 4 – resolve printed page labels → PDF page indices
        # ------------------------------------------------------------------
        chapters: List[Chapter] = []

        for title, page_token in raw_entries:
            pdf_idx: Optional[int] = None

            # Try arabic interpretation first (faster)
            try:
                int(page_token)
                pdf_idx = self._printed_page_to_pdf_index(page_token)
            except ValueError:
                pass

            # If not resolved, try roman
            if pdf_idx is None and _roman_to_int(page_token) is not None:
                pdf_idx = self._printed_page_to_pdf_index(page_token)

            if pdf_idx is not None:
                pdf_page_1based = pdf_idx + 1
                if 1 <= pdf_page_1based <= self.total_pages:
                    chapters.append(Chapter(title=title, start_page=pdf_page_1based, level=1))

        # ------------------------------------------------------------------
        # Step 5 – deduplicate, validate, assign end pages
        # ------------------------------------------------------------------
        seen: set = set()
        unique_chapters: List[Chapter] = []
        for ch in chapters:
            key = (ch.title, ch.start_page)
            if key not in seen:
                seen.add(key)
                unique_chapters.append(ch)

        if len(unique_chapters) < 2:
            return []

        unique_chapters.sort(key=lambda x: x.start_page)

        for i in range(len(unique_chapters) - 1):
            unique_chapters[i].end_page = unique_chapters[i + 1].start_page - 1
        if unique_chapters:
            unique_chapters[-1].end_page = self.total_pages

        return unique_chapters

    # ------------------------------------------------------------------
    # Merging / detection
    # ------------------------------------------------------------------

    def merge_chapters(self, chapters_list: List[List[Chapter]]) -> List[Chapter]:
        """
        Combină și deduplică capitolele din multiple surse
        """
        if not chapters_list:
            return []

        all_chapters: List[Chapter] = []
        for chapters in chapters_list:
            all_chapters.extend(chapters)

        seen: set = set()
        unique_chapters: List[Chapter] = []
        for chapter in all_chapters:
            key = (chapter.title, chapter.start_page)
            if key not in seen:
                seen.add(key)
                unique_chapters.append(chapter)

        unique_chapters.sort(key=lambda x: x.start_page)

        for i in range(len(unique_chapters) - 1):
            unique_chapters[i].end_page = unique_chapters[i + 1].start_page - 1
        if unique_chapters:
            unique_chapters[-1].end_page = self.total_pages

        return unique_chapters

    def detect_chapters(self) -> List[Chapter]:
        """
        Metoda principală pentru detectarea capitolelor folosind toate metodele disponibile
        """
        print("🔍 Detectare capitole în curs...")

        outline_chapters    = self.extract_chapters_from_outline()
        formatting_chapters = self.extract_chapters_by_formatting()
        toc_chapters        = self.extract_chapters_by_table_of_contents()

        print(f"   📑 Capitole găsite în outline: {len(outline_chapters)}")
        print(f"   📝 Capitole găsite prin formatare: {len(formatting_chapters)}")
        print(f"   📖 Capitole găsite în cuprins: {len(toc_chapters)}")

        self.chapters = self.merge_chapters([outline_chapters, formatting_chapters, toc_chapters])

        if not self.chapters:
            print("   ⚠️  Nu s-au găsit capitole prin metodele avansate. Încerc metoda simplă...")
            self.chapters = self.simple_chapter_detection()

        print(f"   ✅ Total capitole detectate: {len(self.chapters)}")
        return self.chapters

    def simple_chapter_detection(self) -> List[Chapter]:
        """
        Metodă simplă de detectare a capitolelor bazată pe cuvinte cheie comune
        """
        chapters: List[Chapter] = []
        chapter_keywords = ['capitol', 'chapter', 'secțiune', 'section', 'part']

        for page_num in range(self.total_pages):
            page = self.pdf_document[page_num]
            text = page.get_text()[:500]
            lines = text.split('\n')
            for line in lines[:5]:
                line_lower = line.lower().strip()
                for keyword in chapter_keywords:
                    if keyword in line_lower and 5 < len(line) < 200:
                        title = line[:50].strip()
                        chapters.append(Chapter(title=title, start_page=page_num + 1, level=1))
                        break

        unique_chapters: List[Chapter] = []
        seen_pages: set = set()
        for chapter in chapters:
            if chapter.start_page not in seen_pages:
                seen_pages.add(chapter.start_page)
                unique_chapters.append(chapter)

        unique_chapters.sort(key=lambda x: x.start_page)

        for i in range(len(unique_chapters) - 1):
            unique_chapters[i].end_page = unique_chapters[i + 1].start_page - 1
        if unique_chapters:
            unique_chapters[-1].end_page = self.total_pages

        return unique_chapters

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def split_pdf_by_chapters(self, output_dir: str = "segmented_chapters"):
        """
        Împarte PDF-ul în fișiere separate pentru fiecare capitol
        """
        if not self.chapters:
            print("❌ Nu s-au detectat capitole pentru a face split-ul.")
            return

        output_dir = os.path.realpath(output_dir)
        cwd = os.path.realpath(os.getcwd())
        if not (output_dir == cwd or output_dir.startswith(cwd + os.sep)):
            print("❌ Director de output invalid (path traversal detectat).")
            return

        os.makedirs(output_dir, exist_ok=True)
        print(f"\n📁 Creare fișiere în directorul: {output_dir}")

        for i, chapter in enumerate(self.chapters, 1):
            output_pdf = PdfWriter()

            end_page  = chapter.end_page if chapter.end_page is not None else self.total_pages
            start_idx = chapter.start_page - 1
            end_idx   = min(end_page, self.total_pages)

            for page_num in range(start_idx, end_idx):
                output_pdf.add_page(self.reader.pages[page_num])

            safe_title = re.sub(r'[^\w\s-]', '', chapter.title)
            safe_title = re.sub(r'[-\s]+', '-', safe_title).strip('-')
            if not safe_title:
                safe_title = f"capitol-{i}"

            output_path = os.path.join(output_dir, f"{i:02d}-{safe_title[:50]}.pdf")

            with open(output_path, 'wb') as output_file:
                output_pdf.write(output_file)

            title_display = chapter.title[:50]
            if len(chapter.title) > 50:
                title_display += '...'
            print(f"   ✅ Capitol {i}: '{title_display}' (paginile {chapter.start_page}-{end_page})")

        print(f"\n✨ Proces complet! {len(self.chapters)} capitole salvate în directorul '{output_dir}'")

    def display_chapters(self):
        """Afișează capitolele detectate"""
        if not self.chapters:
            print("❌ Nu s-au detectat capitole.")
            return

        print("\n📚 Capitole detectate:")
        print("-" * 80)
        for i, chapter in enumerate(self.chapters, 1):
            end_display = chapter.end_page if chapter.end_page is not None else "?"
            print(f"{i:2d}. Paginile {chapter.start_page:3d} - {end_display!s:>3} | {chapter.title[:70]}")
        print("-" * 80)

    def close(self):
        """Eliberează resursele deschise."""
        if self.pdf_document:
            self.pdf_document.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("📄 SEGMENTATOR AUTOMAT DE PDF-URI")
    print("   Detecție structurală a capitolelor")
    print("=" * 60)

    while True:
        pdf_path = input("\n📂 Introduceți calea către fișierul PDF: ").strip()
        pdf_path = pdf_path.strip('"').strip("'")
        if os.path.isfile(pdf_path):
            break
        print("❌ Fișierul nu există. Vă rugăm introduceți o cale validă.")

    segmenter = None
    try:
        segmenter = PDFChapterSegmenter(pdf_path)
        print(f"📊 Total pagini în document: {segmenter.total_pages}")

        chapters = segmenter.detect_chapters()

        if chapters:
            segmenter.display_chapters()
            response = input(
                "\n❓ Doriți să generați fișiere separate pentru fiecare capitol? (da/nu): "
            ).strip().lower()
            if response in ['da', 'd', 'yes', 'y']:
                output_dir = input(
                    "📁 Director pentru output (implicit 'segmented_chapters'): "
                ).strip()
                if not output_dir:
                    output_dir = "segmented_chapters"
                segmenter.split_pdf_by_chapters(output_dir)
            else:
                print("👋 Operațiune anulată.")
        else:
            print("❌ Nu s-au putut detecta capitole în acest PDF.")
            response = input("\n❓ Doriți să faceți split manual? (da/nu): ").strip().lower()
            if response in ['da', 'd', 'yes', 'y']:
                manual_split(pdf_path)

    except FileNotFoundError as e:
        print(f"❌ Eroare: {e}")
    except Exception as e:
        print(f"❌ Eroare: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if segmenter is not None:
            segmenter.close()


def manual_split(pdf_path: str):
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        print(f"\n📊 Total pagini: {total_pages}")
        print("Introduceți intervalele de pagini pentru split (ex: 1-10, 11-20, 21-30)")
        print("Apăsați Enter fără text pentru a termina.")

        ranges: List[Tuple[int, int]] = []
        while True:
            range_input = input("   Interval: ").strip()
            if not range_input:
                break
            parts = range_input.split('-')
            if len(parts) != 2:
                print("❌ Format invalid. Folosiți formatul 'start-end' (ex: 1-10)")
                continue
            try:
                start, end = int(parts[0]), int(parts[1])
                if 1 <= start <= end <= total_pages:
                    ranges.append((start, end))
                else:
                    print(f"❌ Interval invalid. Paginile trebuie să fie între 1 și {total_pages}")
            except ValueError:
                print("❌ Format invalid. Folosiți formatul 'start-end' (ex: 1-10)")

        if ranges:
            output_dir = "manual_split"
            os.makedirs(output_dir, exist_ok=True)
            for i, (start, end) in enumerate(ranges, 1):
                output_pdf = PdfWriter()
                for page_num in range(start - 1, end):
                    output_pdf.add_page(reader.pages[page_num])
                output_path = os.path.join(output_dir, f"part-{i:02d}-pages-{start}-{end}.pdf")
                with open(output_path, 'wb') as output_file:
                    output_pdf.write(output_file)
                print(f"   ✅ Partea {i}: paginile {start}-{end}")
            print(f"\n✨ Split manual complet! {len(ranges)} fișiere salvate în '{output_dir}'")
        else:
            print("👋 Operațiune anulată.")

    except Exception as e:
        print(f"❌ Eroare la split manual: {e}")


if __name__ == "__main__":
    try:
        import PyPDF2
        import fitz
    except ImportError as e:
        print(f"❌ Lipsesc dependențe ({e}). Instalați cu:")
        print("   pip install PyPDF2 pymupdf")
        raise SystemExit(1)

    main()
