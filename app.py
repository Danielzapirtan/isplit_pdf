import PyPDF2
import os
import re
from pathlib import Path

def split_by_headers(input_path, output_dir):
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        delimiter_positions = []  # This will store positions where chapters end
        prev_first_line = None
        
        # Always include page 0 as a chapter start
        delimiter_positions.append(0)
        
        for page_num in range(total_pages - 1):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            
            if text:
                # Get the first line of the page
                first_line = text.split('\n')[0] if '\n' in text else text
                # Check if the first line ends with digits (chapter header)
                if re.search(r'\d+\s*$', first_line.strip()):
                    # This page starts with a chapter header, so the previous page ends the chapter
                    delimiter_positions.append(page_num)
        
        # Add the last page as a delimiter
        if total_pages > 0:
            delimiter_positions.append(total_pages)
        
        # Sort and remove duplicates
        delimiter_positions = sorted(set(delimiter_positions))
        
    return delimiter_positions

def trac(delimiter_positions):
    res = []
    for del_pos in delimiter_positions:
        if del_pos:
            if del_pos - 1 not in delimiter_positions:
                res.append(del_pos - 2)
    return res


def split_pdf_by_intentionally_blank_pages(input_path, output_dir):
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        delimiter_positions = split_by_headers(input_path, output_dir)
        delimiter_positions = trac(delimiter_positions)
        
        print(f"\n📌 Chapter delimiter positions (pages where chapters end): {[p+1 for p in delimiter_positions if p < total_pages]}")
        print("-" * 70)
        
        # Build chapters
        chapters = []
        chapter_count = 1
        
        # Create chapters based on delimiter positions
        for i in range(len(delimiter_positions) - 1):
            start_page = delimiter_positions[i]
            end_page = delimiter_positions[i + 1] - 1
            
            if start_page <= end_page and start_page < total_pages:
                chapter_pages = list(range(start_page, min(end_page, total_pages - 1) + 1))
                
                # Get the first page text for verification
                first_page_text = pdf_reader.pages[start_page].extract_text()
                first_line = first_page_text.split('\n')[0] if first_page_text and '\n' in first_page_text else first_page_text
                
                chapters.append({
                    'pages': chapter_pages,
                    'chapter_num': chapter_count,
                    'first_page_num': start_page + 1,
                    'last_page_num': min(end_page, total_pages - 1) + 1,
                    'first_line': first_line[:100] if first_line else "[No text]"
                })
                chapter_count += 1
        
        print(f"\n📊 Found {len(delimiter_positions) - 1} chapter boundaries")
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
            start_page = chapter['first_page_num']
            end_page = chapter['last_page_num']
            page_count = len(chapter['pages'])
            
            print(f"✓ Created {output_filename}: {page_count} pages "
                  f"(original pages {start_page} to {end_page})")
            print(f"  First line: \"{chapter['first_line'][:50]}...\"")
        
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
                first_page = chapter['first_page_num']
                last_page = chapter['last_page_num']
                
                # Get content of first page for verification
                first_page_text = pdf_reader.pages[chapter['pages'][0]].extract_text()
                first_page_preview = ' '.join(first_page_text.split()[:20]) if first_page_text else "[No text extracted]"
                
                print(f"\n{'='*50}")
                print(f"CHAPTER {chapter['chapter_num']:03d}")
                print(f"{'='*50}")
                print(f"📄 Pages: {first_page} to {last_page} ({len(chapter['pages'])} pages)")
                print(f"🔹 FIRST page: {first_page}")
                
                # Check if this page starts with a chapter header
                first_line = chapter['first_line']
                if re.search(r'\d+\s*$', first_line.strip()):
                    print(f"✨ This chapter starts with a header ending with digits: \"{first_line[:50]}...\"")
                
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
        print(f"✅ Chapter boundaries found: {len(delimiter_positions) - 1}")
        
        if len(delimiter_positions) > 1:
            boundary_pages_display = [pos + 1 for pos in delimiter_positions[1:-1] if pos < total_pages]
            print(f"📍 Chapter boundaries at pages (pages after these are new chapters): {', '.join(map(str, boundary_pages_display))}")
        
        print(f"📁 Output location: {output_dir}")
        print("=" * 70)
        
        # Optional: Verify chapter boundaries
        verify_chapter_boundaries(input_path, chapters, delimiter_positions)
        
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
    
    # Add total_pages to the global scope for the summary
    total_pages = 0
    main()
