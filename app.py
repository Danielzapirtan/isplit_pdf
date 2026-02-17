import PyPDF2
from PyPDF2 import PdfReader, PdfWriter
import re
from typing import List, Tuple, Optional
import os
from dataclasses import dataclass
import fitz  # PyMuPDF
from collections import defaultdict

@dataclass
class Chapter:
    """Clasă pentru stocarea informațiilor despre un capitol"""
    title: str
    start_page: int
    end_page: Optional[int] = None
    level: int = 1

class PDFChapterSegmenter:
    def __init__(self, pdf_path: str):
        """
        Inițializează segmentatorul cu calea către PDF

        Args:
            pdf_path: Calea către fișierul PDF
        """
        # Bug fix: validate path before opening to avoid silent failures
        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"Fișierul PDF nu a fost găsit: {pdf_path}")

        self.pdf_path = pdf_path
        self.pdf_document = fitz.open(pdf_path)
        self.reader = PdfReader(pdf_path)
        self.chapters: List[Chapter] = []
        self.total_pages = len(self.pdf_document)

    def extract_chapters_from_outline(self) -> List[Chapter]:
        """
        Extrage capitolele din outline-ul/bookmarks-ul PDF-ului

        Returns:
            Lista de capitole găsite în outline
        """
        chapters: List[Chapter] = []

        # Verificăm dacă PDF-ul are outline
        if hasattr(self.reader, 'outline') and self.reader.outline:
            outline = self.reader.outline

            def process_outline_item(item, level: int = 1):
                """Procesează recursiv elementele din outline"""
                if isinstance(item, list):
                    for subitem in item:
                        process_outline_item(subitem, level + 1)
                else:
                    # Bug fix: PyPDF2 outline items are dict-like; use .get() for safety
                    title = item.get('/Title') if hasattr(item, 'get') else None
                    page_ref = item.get('/Page') if hasattr(item, 'get') else None

                    if title and page_ref is not None:
                        try:
                            if isinstance(page_ref, PyPDF2.generic.IndirectObject):
                                # Bug fix: resolve the indirect object to get the page object,
                                # then look up its 0-based index via the reader's internal list.
                                resolved = page_ref.get_object()
                                # reader.pages is a list; find the matching page object
                                page_num = None
                                for idx, p in enumerate(self.reader.pages):
                                    if p.indirect_reference == page_ref:
                                        page_num = idx + 1  # 1-based
                                        break
                                if page_num is None:
                                    return  # skip unmappable reference
                            else:
                                page_num = int(page_ref) + 1

                            # Clamp to valid range
                            page_num = max(1, min(page_num, self.total_pages))
                            chapters.append(Chapter(title=str(title), start_page=page_num, level=level))
                        except (ValueError, TypeError):
                            pass  # skip malformed entries

            process_outline_item(outline)

            # Sortăm capitolele după pagina de start
            chapters.sort(key=lambda x: x.start_page)

            # Calculăm pagina de final pentru fiecare capitol
            for i in range(len(chapters) - 1):
                chapters[i].end_page = chapters[i + 1].start_page - 1
            if chapters:
                chapters[-1].end_page = self.total_pages

        return chapters

    def extract_chapters_by_formatting(self, font_threshold: float = 0.8) -> List[Chapter]:
        """
        Extrage capitolele pe baza formatării textului (font size, stil)

        Args:
            font_threshold: Pragul pentru identificarea titlurilor (font size mai mare)

        Returns:
            Lista de capitole potențiale găsite prin analiza formatării
        """
        potential_chapters: List[Chapter] = []

        # Analizăm fiecare pagină pentru a găsi text cu formatare de titlu
        for page_num in range(self.total_pages):
            page = self.pdf_document[page_num]
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            font_size = span["size"]
                            text = span["text"].strip()

                            # Căutăm pattern-uri comune pentru titluri
                            title_patterns = [
                                r'^Capitolul\s+\d+',   # "Capitolul 1"
                                r'^Chapter\s+\d+',     # "Chapter 1"
                                r'^\d+\.\s+[A-Z]',     # "1. Title"
                                r'^[IVXLCDM]+\.\s+',   # "I. Title" (numere romane)
                                r'^[A-Z][a-z]+\s+\d+', # "Title 1" fără cuvântul "Chapter"
                            ]

                            # Bug fix: only consider reasonably-sized text as a potential title
                            if text and 3 < len(text) < 200:
                                for pattern in title_patterns:
                                    if re.match(pattern, text, re.IGNORECASE):
                                        potential_chapters.append(Chapter(
                                            title=text,
                                            start_page=page_num + 1,
                                            level=1
                                        ))
                                        break

        # Eliminăm duplicatele și sortăm
        unique_chapters: List[Chapter] = []
        seen_titles: set = set()

        for chapter in potential_chapters:
            if chapter.title not in seen_titles:
                seen_titles.add(chapter.title)
                unique_chapters.append(chapter)

        unique_chapters.sort(key=lambda x: x.start_page)

        # Calculăm paginile de final
        for i in range(len(unique_chapters) - 1):
            unique_chapters[i].end_page = unique_chapters[i + 1].start_page - 1
        if unique_chapters:
            unique_chapters[-1].end_page = self.total_pages

        return unique_chapters

    def extract_chapters_by_table_of_contents(self) -> List[Chapter]:
        """
        Extrage capitolele analizând cuprinsul (primele pagini)

        Returns:
            Lista de capitole extrase din cuprins
        """
        toc_patterns = [
            r'(Cuprins|Contents|Table of Contents|Index)',
            r'\.{2,}\s+\d+',  # pattern pentru puncte și numere de pagină
        ]

        chapters: List[Chapter] = []

        # Bug fix: the inner loop shadowed the outer `page_num` variable with the
        # page number parsed from text.  Renamed outer variable to `scan_page_num`.
        for scan_page_num in range(min(5, self.total_pages)):
            page = self.pdf_document[scan_page_num]
            text = page.get_text()

            # Verificăm dacă pagina pare a fi un cuprins
            if any(re.search(pattern, text, re.IGNORECASE) for pattern in toc_patterns):
                lines = text.split('\n')

                for line in lines:
                    line = line.strip()
                    # Căutăm linii care conțin un titlu și un număr de pagină
                    match = re.search(r'(.+?)[\.\s]+(\d+)$', line)
                    if match:
                        title = match.group(1).strip()
                        try:
                            toc_page_num = int(match.group(2))
                        except ValueError:
                            continue

                        # Verificăm dacă numărul paginii este valid
                        if title and 1 <= toc_page_num <= self.total_pages:
                            chapters.append(Chapter(title=title, start_page=toc_page_num, level=1))

        # Deduplicate by (title, start_page) before deciding validity
        seen: set = set()
        unique_chapters: List[Chapter] = []
        for ch in chapters:
            key = (ch.title, ch.start_page)
            if key not in seen:
                seen.add(key)
                unique_chapters.append(ch)

        # Dacă am găsit suficiente intrări în cuprins, le folosim
        if len(unique_chapters) >= 3:
            unique_chapters.sort(key=lambda x: x.start_page)

            for i in range(len(unique_chapters) - 1):
                unique_chapters[i].end_page = unique_chapters[i + 1].start_page - 1
            if unique_chapters:
                unique_chapters[-1].end_page = self.total_pages

            return unique_chapters

        return []

    def merge_chapters(self, chapters_list: List[List[Chapter]]) -> List[Chapter]:
        """
        Combină și deduplică capitolele din multiple surse

        Args:
            chapters_list: Lista de liste de capitole din diferite metode

        Returns:
            Lista combinată și deduplicată de capitole
        """
        if not chapters_list:
            return []

        all_chapters: List[Chapter] = []
        for chapters in chapters_list:
            all_chapters.extend(chapters)

        # Eliminăm duplicatele pe baza titlului și paginii de start
        seen: set = set()
        unique_chapters: List[Chapter] = []

        for chapter in all_chapters:
            key = (chapter.title, chapter.start_page)
            if key not in seen:
                seen.add(key)
                unique_chapters.append(chapter)

        # Sortăm după pagina de start
        unique_chapters.sort(key=lambda x: x.start_page)

        # Recalculăm paginile de final pentru a asigura continuitatea
        for i in range(len(unique_chapters) - 1):
            unique_chapters[i].end_page = unique_chapters[i + 1].start_page - 1
        if unique_chapters:
            unique_chapters[-1].end_page = self.total_pages

        return unique_chapters

    def detect_chapters(self) -> List[Chapter]:
        """
        Metoda principală pentru detectarea capitolelor folosind toate metodele disponibile

        Returns:
            Lista capitolelor detectate
        """
        print("🔍 Detectare capitole în curs...")

        outline_chapters = self.extract_chapters_from_outline()
        formatting_chapters = self.extract_chapters_by_formatting()
        toc_chapters = self.extract_chapters_by_table_of_contents()

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

        Returns:
            Lista capitolelor detectate
        """
        chapters: List[Chapter] = []
        chapter_keywords = ['capitol', 'chapter', 'secțiune', 'section', 'part']

        for page_num in range(self.total_pages):
            page = self.pdf_document[page_num]
            text = page.get_text()[:500]  # Primele 500 de caractere

            lines = text.split('\n')
            for line in lines[:5]:  # Primele 5 linii
                line_lower = line.lower().strip()

                for keyword in chapter_keywords:
                    if keyword in line_lower and 5 < len(line) < 200:
                        title = line[:50].strip()
                        chapters.append(Chapter(title=title, start_page=page_num + 1, level=1))
                        break

        # Eliminăm duplicatele și sortăm
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

    def split_pdf_by_chapters(self, output_dir: str = "segmented_chapters"):
        """
        Împarte PDF-ul în fișiere separate pentru fiecare capitol

        Args:
            output_dir: Directorul unde vor fi salvate fișierele
        """
        if not self.chapters:
            print("❌ Nu s-au detectat capitole pentru a face split-ul.")
            return

        # Bug fix: prevent path traversal by resolving to an absolute path and
        # ensuring it stays within the current working directory.
        output_dir = os.path.realpath(output_dir)
        cwd = os.path.realpath(os.getcwd())
        if not output_dir.startswith(cwd):
            print("❌ Director de output invalid (path traversal detectat).")
            return

        os.makedirs(output_dir, exist_ok=True)
        print(f"\n📁 Creare fișiere în directorul: {output_dir}")

        for i, chapter in enumerate(self.chapters, 1):
            output_pdf = PdfWriter()

            # Bug fix: guard against None end_page and out-of-range indices
            end_page = chapter.end_page if chapter.end_page is not None else self.total_pages
            start_idx = chapter.start_page - 1
            end_idx = min(end_page, self.total_pages)

            for page_num in range(start_idx, end_idx):
                output_pdf.add_page(self.reader.pages[page_num])

            # Generăm numele fișierului – strip non-word chars for safety
            safe_title = re.sub(r'[^\w\s-]', '', chapter.title)
            safe_title = re.sub(r'[-\s]+', '-', safe_title).strip('-')

            if not safe_title:
                safe_title = f"capitol-{i}"

            output_path = os.path.join(output_dir, f"{i:02d}-{safe_title[:50]}.pdf")

            with open(output_path, 'wb') as output_file:
                output_pdf.write(output_file)

            title_display = chapter.title[:50]
            # Bug fix: avoid IndexError when title is shorter than 50 chars by
            # only appending "..." when the title was actually truncated.
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
            # Bug fix: end_page may be None; provide a safe fallback for display
            end_display = chapter.end_page if chapter.end_page is not None else "?"
            print(f"{i:2d}. Paginile {chapter.start_page:3d} - {end_display!s:>3} | {chapter.title[:70]}")
        print("-" * 80)

    def close(self):
        """Eliberează resursele deschise."""
        if self.pdf_document:
            self.pdf_document.close()


def main():
    """Funcția principală a aplicației"""
    print("=" * 60)
    print("📄 SEGMENTATOR AUTOMAT DE PDF-URI")
    print("   Detecție structurală a capitolelor")
    print("=" * 60)

    while True:
        pdf_path = input("\n📂 Introduceți calea către fișierul PDF: ").strip()
        pdf_path = pdf_path.strip('"').strip("'")

        if os.path.isfile(pdf_path):
            break
        else:
            print("❌ Fișierul nu există. Vă rugăm introduceți o cale validă.")

    segmenter = None
    try:
        segmenter = PDFChapterSegmenter(pdf_path)
        print(f"📊 Total pagini în document: {segmenter.total_pages}")

        chapters = segmenter.detect_chapters()

        if chapters:
            segmenter.display_chapters()

            response = input("\n❓ Doriți să generați fișiere separate pentru fiecare capitol? (da/nu): ").strip().lower()

            if response in ['da', 'd', 'yes', 'y']:
                output_dir = input("📁 Director pentru output (implicit 'segmented_chapters'): ").strip()
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
        # Bug fix: always close the fitz document to avoid resource leaks
        if segmenter is not None:
            segmenter.close()


def manual_split(pdf_path: str):
    """Funcție pentru split manual în cazul în care detecția automată eșuează"""
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

            # Bug fix: handle input that contains more or fewer than one '-'
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
