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
    These delimiter pages are not included in the output chapters.
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Open the PDF
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        
        print(f"Total pages in PDF: {total_pages}")
        print("-" * 60)
        
        chapters = []
        current_chapter = []
        delimiter_pages = []
        chapter_count = 1
        
        for page_num in range(total_pages):
            page = pdf_reader.pages[page_num]
            
            if is_intentionally_blank_page(page):
                # Found a delimiter page
                delimiter_pages.append(page_num + 1)  # +1 for human-readable page numbers
                
                # Save current chapter if it has pages
                if current_chapter:
                    chapters.append({
                        'pages': current_chapter.copy(),
                        'chapter_num': chapter_count
                    })
                    chapter_count += 1
                    current_chapter = []
                
                print(f"✓ Found delimiter page at position {page_num + 1}: 'This page intentionally left blank'")
            else:
                # Add page to current chapter
                current_chapter.append(page_num)
        
        # Don't forget the last chapter if it exists
        if current_chapter:
            chapters.append({
                'pages': current_chapter.copy(),
                'chapter_num': chapter_count
            })
        
        print("-" * 60)
        print(f"Found {len(delimiter_pages)} delimiter pages (pages intentionally left blank)")
        print(f"Found {len(chapters)} chapters based on these delimiters")
        print("-" * 60)
        
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
            start_page = chapter['pages'][0] + 1
            end_page = chapter['pages'][-1] + 1
            page_count = len(chapter['pages'])
            
            print(f"✓ Created {output_filename}: {page_count} pages "
                  f"(original pages {start_page} to {end_page})")
        
        return chapters, delimiter_pages

def verify_delimiter_pages(input_path, delimiter_pages):
    """Optional function to verify the content of delimiter pages"""
    print("\n" + "=" * 60)
    print("DELIMITER PAGES VERIFICATION")
    print("=" * 60)
    
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        for page_num in delimiter_pages:
            # Convert back to 0-based for PyPDF2
            page = pdf_reader.pages[page_num - 1]
            text = page.extract_text()
            
            print(f"\nPage {page_num} content:")
            print("-" * 40)
            if text:
                # Show first 200 characters of the page
                print(text[:200].strip())
                if len(text) > 200:
                    print("...")
            else:
                print("[No text extracted]")
            print("-" * 40)

def main():
    # Configuration
    input_path = '/content/drive/MyDrive/input.pdf'
    output_dir = '/content/drive/MyDrive/split_chapters'
    
    # Check if input file exists
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at {input_path}")
        print("Please make sure your PDF is at: /content/drive/MyDrive/input.pdf")
        return
    
    print("=" * 60)
    print("PDF CHAPTER SPLITTER")
    print("=" * 60)
    print(f"Input file: {input_path}")
    print(f"Output directory: {output_dir}")
    print("Looking for pages with: 'This page intentionally left blank'")
    print("=" * 60)
    
    try:
        chapters, delimiter_pages = split_pdf_by_intentionally_blank_pages(input_path, output_dir)
        
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"✓ Total chapters created: {len(chapters)}")
        print(f"✓ Delimiter pages found: {len(delimiter_pages)}")
        if delimiter_pages:
            print(f"✓ Delimiter pages at: {', '.join(map(str, delimiter_pages))}")
        print(f"✓ Output location: {output_dir}")
        print("=" * 60)
        
        # Optional: Verify delimiter pages content
        if delimiter_pages and len(delimiter_pages) <= 10:  # Only verify if not too many
            verify_delimiter_pages(input_path, delimiter_pages)
        
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