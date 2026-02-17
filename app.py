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
        self.pdf_path = pdf_path
        self.pdf_document = fitz.open(pdf_path)
        self.reader = PdfReader(pdf_path)
        self.chapters = []
        self.total_pages = len(self.pdf_document)
        
    def extract_chapters_from_outline(self) -> List[Chapter]:
        """
        Extrage capitolele din outline-ul/bookmarks-ul PDF-ului
        
        Returns:
            Lista de capitole găsite în outline
        """
        chapters = []
        
        # Verificăm dacă PDF-ul are outline
        if hasattr(self.reader, 'outline') and self.reader.outline:
            outline = self.reader.outline
            
            def process_outline_item(item, level=1):
                """Procesează recursiv elementele din outline"""
                if isinstance(item, list):
                    for subitem in item:
                        process_outline_item(subitem, level + 1)
                else:
                    if hasattr(item, '/Title') and hasattr(item, '/Page'):
                        title = item['/Title']
                        # Extragem numărul paginii
                        page_ref = item['/Page']
                        if isinstance(page_ref, PyPDF2.generic.IndirectObject):
                            page_num = self.reader.get_page_number(page_ref) + 1  # +1 pentru că paginile încep de la 0
                        else:
                            page_num = int(page_ref) + 1
                        
                        chapters.append(Chapter(title=title, start_page=page_num, level=level))
            
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
        potential_chapters = []
        
        # Analizăm fiecare pagină pentru a găsi text cu formatare de titlu
        for page_num in range(self.total_pages):
            page = self.pdf_document[page_num]
            blocks = page.get_text("dict")["blocks"]
            
            max_font_size = 0
            potential_title = None
            
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            font_size = span["size"]
                            text = span["text"].strip()
                            
                            # Verificăm dacă textul ar putea fi un titlu
                            if text and len(text) > 3 and len(text) < 200:
                                # Titlurile au de obicei font mai mare
                                if font_size > max_font_size:
                                    max_font_size = font_size
                                    potential_title = text
                            
                            # Căutăm pattern-uri comune pentru titluri
                            title_patterns = [
                                r'^\d+\s',    # "1. Title"
                            ]
                            
                            for pattern in title_patterns:
                                if re.match(pattern, text, re.IGNORECASE):
                                    potential_chapters.append(Chapter(
                                        title=text,
                                        start_page=page_num + 1,
                                        level=1
                                    ))
                                    break
        
        # Eliminăm duplicatele și sortăm
        unique_chapters = []
        seen_titles = set()
        
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
        # Analizăm primele 5 pagini pentru a găsi un cuprins
        toc_patterns = [
            r'(Cuprins|Contents|Table of Contents|Index)',
            r'\.{2,}\s+\d+',  # pattern pentru puncte și numere de pagină
        ]
        
        chapters = []
        page_mappings = {}
        
        for page_num in range(min(18, self.total_pages)):
            page = self.pdf_document[page_num]
            text = page.get_text()
            
            # Verificăm dacă pagina pare a fi un cuprins
            if any(re.search(pattern, text, re.IGNORECASE) for pattern in toc_patterns):
                # Încercăm să extragem liniile care par a fi intrări în cuprins
                lines = text.split('\n')
                
                for line in lines:
                    line = line.strip()
                    # Căutăm linii care conțin un titlu și un număr de pagină
                    match = re.search(r'(.+?)[\.\s]+(\d+)$', line)
                    if match:
                        title = match.group(1).strip()
                        page_num2 = int(match.group(2))
                        
                        # Verificăm dacă numărul paginii este valid
                        if 1 <= page_num2 <= self.total_pages:
                            page_mappings[title] = page_num2
                            chapters.append(Chapter(title=title, start_page=page_num, level=1))
        
        # Dacă am găsit suficiente intrări în cuprins, le folosim
        if len(chapters) >= 3:  # Cel puțin 3 capitole pentru a fi valid
            chapters.sort(key=lambda x: x.start_page)
            
            # Calculăm paginile de final
            for i in range(len(chapters) - 1):
                chapters[i].end_page = chapters[i + 1].start_page - 1
            if chapters:
                chapters[-1].end_page = self.total_pages
                
            return chapters
        
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
        
        # Combinăm toate capitolele
        all_chapters = []
        for chapters in chapters_list:
            all_chapters.extend(chapters)
        
        # Eliminăm duplicatele pe baza titlului și paginii de start
        seen = set()
        unique_chapters = []
        
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
        
        # Încercăm diferite metode de detectare
        outline_chapters = self.extract_chapters_from_outline()
        formatting_chapters = self.extract_chapters_by_formatting()
        toc_chapters = self.extract_chapters_by_table_of_contents()
        
        # Afișăm rezultatele fiecărei metode
        print(f"   📑 Capitole găsite în outline: {len(outline_chapters)}")
        print(f"   📝 Capitole găsite prin formatare: {len(formatting_chapters)}")
        print(f"   📖 Capitole găsite în cuprins: {len(toc_chapters)}")
        
        # Combinăm rezultatele
        #self.chapters = #self.merge_chapters([outline_chapters, #formatting_chapters, toc_chapters])
        self.chapters = formatting_chapters
        
        # Dacă nu am găsit niciun capitol, încercăm o metodă mai simplă
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
        chapters = []
        chapter_keywords = ['capitol', 'chapter', 'secțiune', 'section', 'part']
        
        for page_num in range(self.total_pages):
            page = self.pdf_document[page_num]
            text = page.get_text()[:500]  # Primele 500 de caractere
            
            lines = text.split('\n')
            for line in lines[:5]:  # Primele 5 linii
                line_lower = line.lower().strip()
                
                # Verificăm dacă linia conține cuvinte cheie de capitol
                for keyword in chapter_keywords:
                    if keyword in line_lower and len(line) < 200 and len(line) > 5:
                        # Extragem primele 50 de caractere ca titlu
                        title = line[:50].strip()
                        chapters.append(Chapter(title=title, start_page=page_num + 1, level=1))
                        break
        
        # Eliminăm duplicatele și sortăm
        unique_chapters = []
        seen_pages = set()
        
        for chapter in chapters:
            if chapter.start_page not in seen_pages:
                seen_pages.add(chapter.start_page)
                unique_chapters.append(chapter)
        
        unique_chapters.sort(key=lambda x: x.start_page)
        
        # Calculăm paginile de final
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
        
        # Creăm directorul de output dacă nu există
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\n📁 Creare fișiere în directorul: {output_dir}")
        
        for i, chapter in enumerate(self.chapters, 1):
            output_pdf = PdfWriter()
            
            # Adăugăm paginile capitolului (notă: PyPDF2 folosește indexare de la 0)
            for page_num in range(chapter.start_page - 1, chapter.end_page):
                output_pdf.add_page(self.reader.pages[page_num])
            
            # Generăm numele fișierului
            safe_title = re.sub(r'[^\w\s-]', '', chapter.title)
            safe_title = re.sub(r'[-\s]+', '-', safe_title).strip('-')
            
            if not safe_title:
                safe_title = f"capitol-{i}"
            
            output_path = os.path.join(output_dir, f"{i:02d}-{safe_title[:50]}.pdf")
            
            # Salvăm fișierul
            with open(output_path, 'wb') as output_file:
                output_pdf.write(output_file)
            
            print(f"   ✅ Capitol {i}: '{chapter.title[:50]}...' (paginile {chapter.start_page}-{chapter.end_page})")
        
        print(f"\n✨ Proces complet! {len(self.chapters)} capitole salvate în directorul '{output_dir}'")
    
    def display_chapters(self):
        """Afișează capitolele detectate"""
        if not self.chapters:
            print("❌ Nu s-au detectat capitole.")
            return
        
        print("\n📚 Capitole detectate:")
        print("-" * 80)
        for i, chapter in enumerate(self.chapters, 1):
            print(f"{i:2d}. Paginile {chapter.start_page:3d} - {chapter.end_page:3d} | {chapter.title[:70]}")
        print("-" * 80)

def main():
    """Funcția principală a aplicației"""
    print("=" * 60)
    print("📄 SEGMENTATOR AUTOMAT DE PDF-URI")
    print("   Detecție structurală a capitolelor")
    print("=" * 60)
    
    # Citim calea către fișierul PDF
    while True:
        #pdf_path = input("\n📂 Introduceți calea către fișierul PDF: ").strip()
        pdf_path = "/content/drive/MyDrive/input.pdf"
        
        # Eliminăm ghilimelele dacă există
        pdf_path = pdf_path.strip('"').strip("'")
        
        if os.path.exists(pdf_path):
            break
        else:
            print("❌ Fișierul nu există. Vă rugăm introduceți o cale validă.")
    
    try:
        # Inițializăm segmentatorul
        segmenter = PDFChapterSegmenter(pdf_path)
        print(f"📊 Total pagini în document: {segmenter.total_pages}")
        
        # Detectăm capitolele
        chapters = segmenter.detect_chapters()
        
        if chapters:
            # Afișăm capitolele detectate
            segmenter.display_chapters()
            
            # Întrebăm utilizatorul dacă dorește să continue cu split-ul
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
            
            # Opțiune pentru split manual
            response = input("\n❓ Doriți să faceți split manual? (da/nu): ").strip().lower()
            if response in ['da', 'd', 'yes', 'y']:
                manual_split(pdf_path)
    
    except Exception as e:
        print(f"❌ Eroare: {e}")
        import traceback
        traceback.print_exc()

def manual_split(pdf_path):
    """Funcție pentru split manual în cazul în care detecția automată eșuează"""
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        print(f"\n📊 Total pagini: {total_pages}")
        print("Introduceți intervalele de pagini pentru split (ex: 1-10, 11-20, 21-30)")
        print("Apăsați Enter fără text pentru a termina.")
        
        ranges = []
        while True:
            range_input = input("   Interval: ").strip()
            if not range_input:
                break
            
            try:
                start, end = map(int, range_input.split('-'))
                if 1 <= start <= end <= total_pages:
                    ranges.append((start, end))
                else:
                    print(f"❌ Interval invalid. Paginile trebuie să fie între 1 și {total_pages}")
            except:
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
    # Verificăm dacă avem dependențele necesare
    try:
        import PyPDF2
        import fitz
    except ImportError as e:
        print("❌ Lipsesc dependențe. Instalați cu:")
        print("   pip install PyPDF2 pymupdf")
        exit(1)
    
    main()