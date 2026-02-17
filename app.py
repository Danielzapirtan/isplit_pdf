import PyPDF2
import pdfplumber
import re
from pathlib import Path

def extract_header_from_left_even_page(pdf_path):
    """
    Extrage titlul capitolului din centrul antetului paginii pare (stânga)
    """
    chapters = {}
    current_chapter = None
    start_page = None
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        
        for page_num in range(total_pages):
            page = pdf.pages[page_num]
            
            # Verificăm dacă e pagină pară (numărul paginii începe de la 1)
            # În pdfplumber, indexarea începe de la 0
            is_even_page = (page_num + 1) % 2 == 0
            
            if is_even_page:
                # Extragem textul din partea de sus a paginii (antet)
                # Antetul ocupă primele 10-15% din pagină
                page_height = page.height
                page_width = page.width
                
                # Definim bbox-ul pentru antet - ne uităm în partea de sus a paginii
                # Ne concentrăm pe zona centrală (25% - 75% din lățime) pentru a capta centrul antetului
                header_bbox = (
                    page_width * 0.25,  # x0: 25% din lățime (stânga)
                    0,                   # y0: începutul paginii
                    page_width * 0.75,  # x1: 75% din lățime (dreapta)
                    page_height * 0.12   # y1: 12% din înălțime (suficient pentru antet)
                )
                
                # Încercăm să extragem textul din zona antetului
                cropped_page = page.within_bbox(header_bbox)
                header_text = cropped_page.extract_text()
                
                if header_text:
                    # Curățăm textul și eliminăm spațiile multiple
                    header_text = ' '.join(header_text.split())
                    
                    # Verificăm dacă antetul conține un titlu de capitol
                    # Filtrăm textul care ar putea fi doar număr de pagină sau alte elemente
                    if len(header_text) > 3 and not header_text.strip().isdigit():
                        # Excludem textul care pare a fi numere de pagină sau copyright
                        if not re.match(r'^\d+$|page|pagina|copyright|©', header_text.lower()):
                            
                            # Dacă am găsit un nou capitol
                            if header_text != current_chapter:
                                # Salvăm capitolul anterior
                                if current_chapter and start_page is not None:
                                    chapters[current_chapter] = {
                                        'start_page': start_page + 1,  # +1 pentru că utilizatorii vor vedea paginile de la 1
                                        'end_page': page_num,
                                        'pages': list(range(start_page + 1, page_num + 1))
                                    }
                                
                                # Începem un capitol nou
                                current_chapter = header_text
                                start_page = page_num
                                print(f"  → Capitol nou găsit la pagina {page_num + 1}: '{header_text}'")
    
    # Adăugăm ultimul capitol
    if current_chapter and start_page is not None:
        chapters[current_chapter] = {
            'start_page': start_page + 1,
            'end_page': total_pages,
            'pages': list(range(start_page + 1, total_pages + 1))
        }
    
    return chapters

def segment_pdf_by_chapters(input_path, output_dir=None):
    """
    Segmentează PDF-ul în fișiere separate pentru fiecare capitol
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        print(f"Eroare: Fișierul {input_path} nu există!")
        return
    
    # Creăm directorul de output dacă nu există
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = input_path.parent / f"{input_path.stem}_capitole"
    
    output_path.mkdir(exist_ok=True)
    
    print(f"\n{'='*60}")
    print(f"Procesez fișierul: {input_path}")
    print(f"{'='*60}\n")
    
    print("🔍 Extrag capitolele din antetul paginilor pare (stânga)...")
    print("-" * 50)
    
    # Extragem capitolele
    chapters = extract_header_from_left_even_page(input_path)
    
    if not chapters:
        print("\n❌ Nu am găsit niciun capitol în document!")
        print("   Posibile cauze:")
        print("   - Antetele nu sunt în paginile pare")
        print("   - Antetele nu sunt în zona centrală a paginii")
        print("   - Formatul PDF-ului nu permite extragerea textului")
        return
    
    print(f"\n✅ Am găsit {len(chapters)} capitole:\n")
    
    # Citim PDF-ul original pentru a extrage paginile
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        for idx, (chapter_title, chapter_info) in enumerate(chapters.items(), 1):
            start_page = chapter_info['start_page'] - 1  # Convertim la index 0 pentru PyPDF2
            end_page = chapter_info['end_page']
            
            print(f"📘 Capitolul {idx}: {chapter_title}")
            print(f"   📄 Pagini: {chapter_info['start_page']} - {end_page} ({len(chapter_info['pages'])} pagini)")
            
            # Creăm PDF-ul pentru acest capitol
            pdf_writer = PyPDF2.PdfWriter()
            
            for page_num in range(start_page, end_page):
                pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # Generăm numele fișierului
            # Eliminăm caracterele care nu sunt permise în nume de fișier
            safe_title = re.sub(r'[^\w\s-]', '', chapter_title)
            safe_title = re.sub(r'[-\s]+', '_', safe_title)
            safe_title = safe_title[:50]  # Limităm lungimea titlului
            output_filename = output_path / f"Capitolul_{idx:02d}_{safe_title}.pdf"
            
            # Salvăm fișierul
            with open(output_filename, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            print(f"   💾 Salvat în: {output_filename.name}\n")
    
    print(f"{'='*60}")
    print(f"✅ Segmentare completă!")
    print(f"📁 Fișierele au fost salvate în: {output_path}")
    print(f"{'='*60}")

def main():
    # Calea către fișierul PDF
    pdf_path = "/content/drive/MyDrive/input.pdf"
    
    # Rulează segmentarea
    segment_pdf_by_chapters(pdf_path)
    
    # Afișează și o listă sumară a capitolelor
    print("\n" + "="*60)
    print("📋 SUMAR CAPITOLE:")
    print("="*60)
    
    chapters = extract_header_from_left_even_page(pdf_path)
    for idx, (title, info) in enumerate(chapters.items(), 1):
        print(f"{idx:2d}. {title}")
        print(f"    Paginile {info['start_page']} - {info['end_page']}")

if __name__ == "__main__":
    main()