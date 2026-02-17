import PyPDF2
import pdfplumber
import re
from pathlib import Path

def extract_header_from_right_odd_page(pdf_path):
    """
    Extrage titlul capitolului din centrul antetului paginii impare (dreapta)
    """
    chapters = {}
    current_chapter = None
    start_page = None
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        
        for page_num in range(total_pages):
            page = pdf.pages[page_num]
            
            # Verificăm dacă e pagină impară (numărul paginii începe de la 1)
            # În pdfplumber, indexarea începe de la 0
            is_odd_page = (page_num + 1) % 2 == 1
            
            if is_odd_page:
                # Extragem textul din partea de sus a paginii (antet)
                # Presupunem că antetul ocupă primele 15% din pagină
                page_height = page.height
                header_bbox = (0, 0, page.width, page_height * 0.15)
                
                # Încercăm să extragem textul din zona antetului
                cropped_page = page.within_bbox(header_bbox)
                header_text = cropped_page.extract_text()
                
                if header_text:
                    # Curățăm textul și eliminăm spațiile multiple
                    header_text = ' '.join(header_text.split())
                    
                    # Verificăm dacă antetul conține un titlu de capitol
                    # Filtrăm textul care ar putea fi doar număr de pagină sau alte elemente
                    if len(header_text) > 3 and not header_text.strip().isdigit():
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
                            current_chapter = re.match('[A-Z ]*', header_text).group()
                            start_page = page_num
    
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
        output_path = input_path.parent / f"{input_path.stem}_chapters"
    
    output_path.mkdir(exist_ok=True)
    
    print(f"Procesez fișierul: {input_path}")
    print("Extrag capitolele...")
    
    # Extragem capitolele
    chapters = extract_header_from_right_odd_page(input_path)
    
    if not chapters:
        print("Nu am găsit niciun capitol în document!")
        return
    
    print(f"Am găsit {len(chapters)} capitole:\n")
    
    # Citim PDF-ul original pentru a extrage paginile
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        for idx, (chapter_title, chapter_info) in enumerate(chapters.items(), 1):
            start_page = chapter_info['start_page'] - 1  # Convertim la index 0 pentru PyPDF2
            end_page = chapter_info['end_page']
            
            print(f"Capitolul {idx}: {chapter_title}")
            print(f"  Pagini: {chapter_info['start_page']} - {end_page}")
            print(f"  Număr pagini: {len(chapter_info['pages'])}")
            
            # Creăm PDF-ul pentru acest capitol
            pdf_writer = PyPDF2.PdfWriter()
            
            for page_num in range(start_page, end_page):
                pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # Generăm numele fișierului
            # Eliminăm caracterele care nu sunt permise în nume de fișier
            safe_title = re.sub(r'[^\w\s-]', '', chapter_title)
            safe_title = re.sub(r'[-\s]+', '_', safe_title)
            output_filename = output_path / f"{idx:02d}_{safe_title[:50]}.pdf"
            
            # Salvăm fișierul
            with open(output_filename, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            print(f"  Salvat în: {output_filename}\n")
    
    print(f"Segmentare completă! Fișierele au fost salvate în: {output_path}")

def main():
    # Calea către fișierul PDF
    pdf_path = "/content/drive/MyDrive/input.pdf"
    
    # Rulează segmentarea
    segment_pdf_by_chapters(pdf_path)
    
    # Afișează și o listă sumară a capitolelor
    print("\n" + "="*50)
    print("SUMAR CAPITOLE:")
    print("="*50)
    
    chapters = extract_header_from_right_odd_page(pdf_path)
    for idx, (title, info) in enumerate(chapters.items(), 1):
        print(f"{idx:2d}. {title}")
        print(f"    Paginile {info['start_page']} - {info['end_page']}")

if __name__ == "__main__":
    main()
