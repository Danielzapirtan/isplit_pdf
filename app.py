import PyPDF2
import pdfplumber
import re
from pathlib import Path

def extract_chapters_from_even_pages(pdf_path):
    """
    Extrage titlurile capitolelor din antetul paginilor pare (stânga)
    și determină paginile de start (pagina impară anterioară)
    """
    chapter_starts = []  # Listă de tuple (pagina_impara_anterioara, titlu_capitol)
    
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        
        for page_num in range(total_pages):
            page = pdf.pages[page_num]
            
            # Verificăm dacă e pagină pară (numărul paginii începe de la 1)
            is_even_page = (page_num + 1) % 2 == 0
            
            if is_even_page:
                # Extragem textul din centrul antetului
                page_height = page.height
                page_width = page.width
                
                # Bbox pentru centrul antetului (25% - 75% din lățime, primele 12% din înălțime)
                header_bbox = (
                    page_width * 0.15,   # x0: 25% din lățime
                    0,                    # y0: începutul paginii
                    page_width * 0.85,   # x1: 75% din lățime
                    page_height * 0.1    # y1: 12% din înălțime
                )
                
                cropped_page = page.within_bbox(header_bbox)
                header_text = cropped_page.extract_text()
                
                if header_text:
                    header_text = ' '.join(header_text.split())
                    
                    # Verificăm dacă e un titlu de capitol valid
                    if (len(header_text) > 3 and 
                        not header_text.strip().isdigit() and
                        not re.match(r'^\d+$|page|pagina|copyright|©', header_text.lower())):
                        
                        # Pagina impară anterioară (pagina curentă - 1)
                        previous_odd_page = page_num  # page_num e index 0, deci pagina impară anterioară e chiar page_num
                        # Explicatie: dacă pagina pară e la index 1 (pagina 2), pagina impară anterioară e la index 0 (pagina 1)
                        
                        chapter_starts.append((previous_odd_page, header_text))
                        print(f"  → Capitol '{header_text}' începe de la pagina {previous_odd_page + 1} (impară)")
    
    return chapter_starts

def segment_pdf_by_chapters(input_path, output_dir=None):
    """
    Segmentează PDF-ul în fișiere separate pentru fiecare capitol,
    începând fiecare capitol de la pagina impară anterioară
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        print(f"Eroare: Fișierul {input_path} nu există!")
        return
    
    # Creăm directorul de output
    if output_dir:
        output_path = Path(output_dir)
    else:
        output_path = input_path.parent / f"{input_path.stem}_capitole"
    
    output_path.mkdir(exist_ok=True)
    
    print(f"\n{'='*70}")
    print(f"📄 Procesez fișierul: {input_path}")
    print(f"{'='*70}\n")
    
    print("🔍 Extrag capitolele din antetul paginilor pare...")
    print("-" * 60)
    
    # Extragem începuturile de capitole
    chapter_starts = extract_chapters_from_even_pages(input_path)
    
    if not chapter_starts:
        print("\n❌ Nu am găsit niciun capitol în document!")
        return
    
    # Adăugăm sfârșitul documentului ca ultimul capitol
    with pdfplumber.open(input_path) as pdf:
        total_pages = len(pdf.pages)
    
    # Construim capitolele cu paginile corespunzătoare
    chapters = []
    old_title = ''
    for i, (start_page, title) in enumerate(chapter_starts):
        if title != old_title:
            if i < len(chapter_starts) - 1:
                end_page = chapter_starts[i + 1][0]  # Pagina de start a următorului capitol
            else:
                end_page = total_pages  # Ultimul capitol merge până la sfârșit
        
            chapters.append({
                'title': title,
                'start_page': start_page + 1,  # Convertim la indexare de la 1 pentru utilizator
                'end_page': end_page,
                'pages': list(range(start_page + 1, end_page + 1))
            })
    
    print(f"\n✅ Am găsit {len(chapters)} capitole, fiecare începând de la o pagină impară:\n")
    
    # Citim PDF-ul original pentru a extrage paginile
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        for idx, chapter in enumerate(chapters, 1):
            start_page = chapter['start_page'] - 1  # Convertim la index 0 pentru PyPDF2
            end_page = chapter['end_page']
            
            print(f"📘 Capitolul {idx}: {chapter['title']}")
            print(f"   📄 Pagini: {chapter['start_page']} - {end_page} ({len(chapter['pages'])} pagini)")
            print(f"   🔸 Începe la pagina {chapter['start_page']} (impară)")
            
            # Verificăm dacă pagina de start e într-adevăr impară
            if chapter['start_page'] % 2 == 1:
                print(f"   ✅ Confirmare: Pagina {chapter['start_page']} este impară")
            else:
                print(f"   ⚠️  Atenție: Pagina {chapter['start_page']} ar trebui să fie impară")
            
            # Creăm PDF-ul pentru acest capitol
            pdf_writer = PyPDF2.PdfWriter()
            
            for page_num in range(start_page, end_page):
                pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # Generăm numele fișierului
            safe_title = re.sub(r'[^\w\s-]', '', chapter['title'])
            safe_title = re.sub(r'[-\s]+', '_', safe_title)
            safe_title = safe_title[:50]
            output_filename = output_path / f"Capitolul_{idx:02d}_p{chapter['start_page']}-{end_page}_{safe_title}.pdf"
            
            # Salvăm fișierul
            with open(output_filename, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            print(f"   💾 Salvat în: {output_filename.name}\n")
    
    print(f"{'='*70}")
    print(f"✅ Segmentare completă!")
    print(f"📁 Fișierele au fost salvate în: {output_path}")
    print(f"{'='*70}")
    
    # Afișăm un sumar al capitolelor
    print("\n📋 SUMAR CAPITOLE:")
    print("-" * 60)
    for idx, chapter in enumerate(chapters, 1):
        print(f"{idx:2d}. {chapter['title']}")
        print(f"    Paginile {chapter['start_page']} - {chapter['end_page']} (începe la pagina {chapter['start_page']}, impară)")

def main():
    # Calea către fișierul PDF
    pdf_path = "/content/drive/MyDrive/input.pdf"
    
    # Rulează segmentarea
    segment_pdf_by_chapters(pdf_path)

if __name__ == "__main__":
    main()
