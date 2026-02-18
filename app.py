import PyPDF2
import os
import re
from pathlib import Path

def is_intentionally_blank_page(page):
    """Check if a page contains the text 'This page intentionally left blank' (case-insensitive)"""
    try:
        text = page.extract_text()
        if text:
            # Clean up text: remove extra whitespace and convert to lowercase for comparison
            cleaned_text = ' '.join(text.split()).lower()
            # Check for the exact phrase (case-insensitive)
            if 'this page intentionally left blank' in cleaned_text:
                return True
            
            # Also check for variations (sometimes OCR might have issues)
            variations = [
                r'this\s+page\s+intentionally\s+left\s+blank',
                r'page\s+intentionally\s+left\s+blank',
                r'intentionally\s+left\s+blank'
            ]
            
            for pattern in variations:
                if re.search(pattern, cleaned_text, re.IGNORECASE):
                    return True
        
        return False
    except Exception as e:
        print(f"Warning: Could not extract text from page: {e}")
        return False

def split_pdf_by_intentionally_blank_pages(input_path, output_dir):
    """
    Split PDF into chapters based on pages that say "This page intentionally left blank".
    The page BEFORE each blank page becomes the FIRST page of a new chapter.
    Blank pages themselves are NOT included in any chapter.
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Open the PDF
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        
        print(f"Total pages in PDF: {total_pages}")
        print("-" * 70)
        
        # First, identify all delimiter pages
        delimiter_positions = []
        for page_num in range(total_pages):
            page = pdf_reader.pages[page_num]
            if is_intentionally_blank_page(page):
                delimiter_positions.append(page_num)
                print(f"✓ Found delimiter page at position {page_num + 1}: 'This page intentionally left blank'")
        
        if not delimiter_positions:
            print("No delimiter pages found. The entire PDF will be treated as one chapter.")
            chapters = [{'pages': list(range(total_pages)), 'chapter_num': 1}]
        else:
            # Build chapters based on delimiter positions
            # Each chapter STARTS with the page BEFORE a delimiter
            chapters = []
            chapter_count = 1
            
            # Process each delimiter
            for i, delimiter_pos in enumerate(delimiter_positions):
                # The page before this delimiter becomes the first page of a chapter
                chapter_start = delimiter_pos - 1
                
                # Determine where this chapter ends (page before the next delimiter, or end of document)
                if i < len(delimiter_positions) - 1:
                    # End at the page before the next delimiter
                    chapter_end = delimiter_positions[i + 1] - 2  // -2 because we want to exclude the next delimiter and its preceding page?
                    # Wait, let me think carefully...
                    
                # Let me rethink the logic properly
                
            # Better approach: Let's collect all the "chapter start" pages (pages before delimiters)
            chapter_start_pages = []
            for delimiter_pos in delimiter_positions:
                if delimiter_pos > 0:  # Make sure there's a page before the delimiter
                    chapter_start_pages.append(delimiter_pos - 1)
            
            # Sort and remove duplicates (in case of consecutive delimiters)
            chapter_start_pages = sorted(set(chapter_start_pages))
            
            print(f"\nChapter start pages (pages before blank pages): {[p+1 for p in chapter_start_pages]}")
            
            # Build chapters using these start pages as boundaries
            chapters = []
            chapter_count = 1
            
            # Add all pages before the first chapter start as Chapter 1
            if chapter_start_pages:
                first_start = chapter_start_pages[0]
                if first_start > 0:
                    # Pages from beginning to the page before the first chapter start
                    pre_chapter_pages = list(range(0, first_start))
                    if pre_chapter_pages:
                        chapters.append({
                            'pages': pre_chapter_pages,
                            'chapter_num': chapter_count,
                            'description': f'Pages before first chapter start (ends at page {first_start})'
                        })
                        chapter_count += 1
                
                # Now create chapters for each chapter start page
                for i, start_page in enumerate(chapter_start_pages):
                    # Determine end of this chapter
                    if i < len(chapter_start_pages) - 1:
                        # End before the next chapter start page
                        end_page = chapter_start_pages[i + 1] - 1
                    else:
                        # Last chapter goes to the end of the document
                        end_page = total_pages - 1
                    
                    # Create chapter pages from start_page to end_page
                    if start_page <= end_page:
                        chapter_pages = list(range(start_page, end_page + 1))
                        chapters.append({
                            'pages': chapter_pages,
                            'chapter_num': chapter_count,
                            'starts_at_page': start_page + 1,
                            'description': f'Chapter starts at page {start_page + 1} (page before blank page {delimiter_positions[i] + 1})'
                        })
                        chapter_count += 1
            else:
                # No chapter starts found, whole document is one chapter
                chapters = [{'pages': list(range(total_pages)), 'chapter_num': 1}]
        
        print("-" * 70)
        print(f"Found {len(delimiter_positions)} delimiter pages")
        print(f"Created {len(chapters)} chapters")
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
                
                if 'starts_at_page' in chapter:
                    print(f"✓ Created {output_filename}: {page_count} pages "
                          f"(original pages {start_page} to {end_page}) "
                          f"[STARTS with page {chapter['starts_at_page']} - the page BEFORE blank page]")
                else:
                    print(f"✓ Created {output_filename}: {page_count} pages "
                          f"(original pages {start_page} to {end_page})")
        
        return chapters, delimiter_positions

def verify_chapter_boundaries(input_path, chapters, delimiter_positions):
    """Optional function to verify chapter boundaries"""
    print("\n" + "=" * 70)
    print("CHAPTER BOUNDARIES VERIFICATION")
    print("=" * 70)
    
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        print("\nChapter breakdown:")
        for chapter in chapters:
            if chapter['pages']:
                first_page = chapter['pages'][0] + 1
                last_page = chapter['pages'][-1] + 1
                
                # Get first few words of first page for verification
                first_page_text = pdf_reader.pages[chapter['pages'][0]].extract_text()
                first_preview = ' '.join(first_page_text.split()[:15]) if first_page_text else "[No text]"
                
                print(f"\nChapter {chapter['chapter_num']:03d}:")
                print(f"  Pages: {first_page} to {last_page} ({len(chapter['pages'])} pages)")
                print(f"  FIRST page: {first_page}")
                print(f"  First page preview: {first_preview[:150]}...")
                
                # Check if this chapter starts with a page before a delimiter
                if first_page - 1 in [d + 1 for d in delimiter_positions]:
                    print(f"  ✓ This chapter STARTS with page {first_page} which is BEFORE blank page {first_page + 1}")

def main():
    # Configuration
    input_path = '/content/drive/MyDrive/input.pdf'
    output_dir = '/content/drive/MyDrive/split_chapters'
    
    # Check if input file exists
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at {input_path}")
        print("Please make sure your PDF is at: /content/drive/MyDrive/input.pdf")
        return
    
    print("=" * 70)
    print("PDF CHAPTER SPLITTER")
    print("=" * 70)
    print(f"Input file: {input_path}")
    print(f"Output directory: {output_dir}")
    print("Chapter definition: The page BEFORE each blank page is the FIRST page of a new chapter")
    print("=" * 70)
    
    try:
        chapters, delimiter_positions = split_pdf_by_intentionally_blank_pages(input_path, output_dir)
        
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"✓ Total chapters created: {len(chapters)}")
        print(f"✓ Delimiter pages found: {len(delimiter_positions)}")
        if delimiter_positions:
            delimiter_pages_display = [pos + 1 for pos in delimiter_positions]
            print(f"✓ Delimiter pages at: {', '.join(map(str, delimiter_pages_display))}")
            chapter_start_pages = [d for d in delimiter_pages_display if d > 1]
            if chapter_start_pages:
                print(f"✓ Chapter first pages (pages BEFORE blank pages): {', '.join([str(p-1) for p in chapter_start_pages])}")
        print(f"✓ Output location: {output_dir}")
        print("=" * 70)
        
        # Optional: Verify chapter boundaries
        if chapters:
            verify_chapter_boundaries(input_path, chapters, delimiter_positions)
        
    except Exception as e:
        print(f"Error during PDF splitting: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Install required package if not already installed
    try:
        import PyPDF2
    except ImportError:
        print("Installing required package: PyPDF2")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'PyPDF2'])
        import PyPDF2
    
    main()