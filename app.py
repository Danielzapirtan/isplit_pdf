import PyPDF2
import os
import re
from pathlib import Path

def split_by_headers(input_path, output_dir):
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        delimiter_positions = []
        text = None
        for page_num in range(total_pages - 1):
            if page_num % 2 == 0:
                continue
            page = pdf_reader.pages[page_num];
            oldtext = text
            text = page.extract_text()
            if oldtext == None:
                delimiter_positions.append(page_num + 1)    
            elif len(oldtext.split()):
                if re.match(r"[A-Za-z]", oldtext.split()[0]) != re.match(r"[A-Za-z]", text.split()[0]):
                    delimiter_positions.append(page_num + 1)    
    return delimiter_positions

def split_pdf_by_intentionally_blank_pages(input_path, output_dir):
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        delimiter_positions = split_by_headers(input_path, output_dir)
        # Find all pages that are BEFORE a blank page (these will be chapter starts)
        chapter_start_pages = []
        for delim_pos in delimiter_positions:
            if delim_pos > 0:  # Make sure there's a page before the blank page
                chapter_start_pages.append(delim_pos - 1)
            
        # Remove duplicates and sort
        chapter_start_pages = sorted(set(chapter_start_pages))
            
        print(f"\n📌 Chapter start pages (pages BEFORE blank pages): {[p+1 for p in chapter_start_pages]}")
        print("-" * 70)
            
        # Build chapters
        chapters = []
        chapter_count = 1
            
        # If there are pages before the first chapter start, they form Chapter 1
        if chapter_start_pages and chapter_start_pages[0] > 0:
            first_chapter_pages = list(range(0, chapter_start_pages[0]))
            if first_chapter_pages:
                chapters.append({
                    'pages': first_chapter_pages,
                    'chapter_num': chapter_count,
                    'type': 'introductory'
                })
                chapter_count += 1
            
        # Create chapters for each chapter start page
        for i, start_page in enumerate(chapter_start_pages):
            # Determine end of this chapter
            if i < len(chapter_start_pages) - 1:
                # End before the next chapter start page
                end_page = chapter_start_pages[i + 1] - 1
            else:
                # Last chapter goes to the end of the document
                end_page = total_pages - 1
                
            # Create chapter pages
            if start_page <= end_page:
                chapter_pages = list(range(start_page, end_page + 1))
                    
                # Find which blank page this chapter starts before
                corresponding_blank = None
                for delim_pos in delimiter_positions:
                    if delim_pos - 1 == start_page:
                        corresponding_blank = delim_pos + 1
                        break
                    
                chapters.append({
                    'pages': chapter_pages,
                    'chapter_num': chapter_count,
                    'starts_at_page': start_page + 1,
                    'blank_page_after': corresponding_blank,
                    'type': 'regular'
                })
                chapter_count += 1
        
        print(f"\n📊 Found {len(delimiter_positions)} delimiter pages")
        print(f"📊 Created {len(chapters)} chapters")
        print("-" * 70)
        
        # Save each chapter as a separate PDF
        for chapter in chapters:
            output_filename = f"chapter_{chapter['chapter_num']:03d}.pdf"
            output_path = os.path.join(output_dir, output_filename)
            
            pdf_writer = PyPDF2.PdfWriter()
            
            # Add pages to the chapter
            for page_num in chapter['pages']:
                pdf_writer.add_page(pdf_reader.pages[page_num])
            
            # Save the chapter
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            
            # Calculate page range (1-based for display)
            if chapter['pages']:
                start_page = chapter['pages'][0] + 1
                end_page = chapter['pages'][-1] + 1
                page_count = len(chapter['pages'])
                
                if chapter.get('type') == 'introductory':
                    print(f"✓ Created {output_filename}: {page_count} pages "
                          f"(original pages {start_page} to {end_page}) "
                          f"[Introductory chapter]")
                elif 'blank_page_after' in chapter and chapter['blank_page_after']:
                    print(f"✓ Created {output_filename}: {page_count} pages "
                          f"(original pages {start_page} to {end_page}) "
                          f"[STARTS with page {chapter['starts_at_page']} - BEFORE blank page {chapter['blank_page_after']}]")
                else:
                    print(f"✓ Created {output_filename}: {page_count} pages "
                          f"(original pages {start_page} to {end_page})")
        
        return chapters, delimiter_positions

def verify_chapter_boundaries(input_path, chapters, delimiter_positions):
    """Verify chapter boundaries and show first page of each chapter"""
    print("\n" + "=" * 70)
    print("CHAPTER BOUNDARIES VERIFICATION")
    print("=" * 70)
    
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        print("\n📖 Chapter details:")
        for chapter in chapters:
            if chapter['pages']:
                first_page = chapter['pages'][0] + 1
                last_page = chapter['pages'][-1] + 1
                
                # Get content of first page for verification
                first_page_text = pdf_reader.pages[chapter['pages'][0]].extract_text()
                first_page_preview = ' '.join(first_page_text.split()[:20]) if first_page_text else "[No text extracted]"
                
                print(f"\n{'='*50}")
                print(f"CHAPTER {chapter['chapter_num']:03d}")
                print(f"{'='*50}")
                print(f"📄 Pages: {first_page} to {last_page} ({len(chapter['pages'])} pages)")
                print(f"🔹 FIRST page: {first_page}")
                
                # Check if this page is before a blank page
                if first_page - 1 in delimiter_positions:
                    print(f"✨ This chapter STARTS with page {first_page} which is BEFORE blank page {first_page + 1}")
                elif first_page in [d + 1 for d in delimiter_positions]:
                    print(f"⚠️  Note: This chapter starts with a blank page? (page {first_page})")
                
                print(f"\n📝 First page preview:")
                print(f"   \"{first_page_preview[:200]}...\"")
                
                # Show last page preview as well
                if len(chapter['pages']) > 1:
                    last_page_text = pdf_reader.pages[chapter['pages'][-1]].extract_text()
                    last_page_preview = ' '.join(last_page_text.split()[:10]) if last_page_text else "[No text]"
                    print(f"\n📝 Last page preview:")
                    print(f"   \"{last_page_preview[:100]}...\"")

def main():
    # Configuration
    input_path = '/content/drive/MyDrive/input.pdf'
    output_dir = '/content/drive/MyDrive/split_chapters'
    
    # Check if input file exists
    if not os.path.exists(input_path):
        print(f"❌ Error: Input file not found at {input_path}")
        print("Please make sure your PDF is at: /content/drive/MyDrive/input.pdf")
        return
    
    print("=" * 70)
    print("📚 PDF CHAPTER SPLITTER")
    print("=" * 70)
    print(f"📂 Input file: {input_path}")
    print(f"📂 Output directory: {output_dir}")
    print("=" * 70)
    
    try:
        chapters, delimiter_positions = split_pdf_by_intentionally_blank_pages(input_path, output_dir)
        
        print("\n" + "=" * 70)
        print("📊 FINAL SUMMARY")
        print("=" * 70)
        print(f"✅ Total chapters created: {len(chapters)}")
        print(f"✅ Delimiter pages found: {len(delimiter_positions)}")
        
        if delimiter_positions:
            delimiter_pages_display = [pos + 1 for pos in delimiter_positions]
            print(f"📍 Delimiter pages at: {', '.join(map(str, delimiter_pages_display))}")
            
            # Calculate chapter start pages (pages before blank pages)
            chapter_start_pages = []
            for pos in delimiter_positions:
                if pos > 0:  # Page before blank page exists
                    chapter_start_pages.append(pos)  # The page number (0-based) that becomes chapter start
            
            if chapter_start_pages:
                start_pages_display = [p + 1 for p in chapter_start_pages]
                print(f"🎯 Chapter first pages (pages BEFORE blank pages): {', '.join(map(str, start_pages_display))}")
        
        print(f"📁 Output location: {output_dir}")
        print("=" * 70)
        
        print("\n✨ Done! Check the output directory for your chapter PDFs.")
        
    except Exception as e:
        print(f"❌ Error during PDF splitting: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Install required package if not already installed
    try:
        import PyPDF2
    except ImportError:
        print("📦 Installing required package: PyPDF2")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'PyPDF2'])
        import PyPDF2
        print("✅ PyPDF2 installed successfully!\n")
    
    main()
