import re
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter

def extract_chapters_from_contents(contents_text):
    """
    Extract chapter titles and their starting page numbers from the table of contents.
    Looks for patterns like "Chapter 1: Title .......... 5" or "1. Title 10"
    """
    chapters = []
    
    # Common patterns for table of contents entries
    # Pattern 1: "Chapter 1: Title .......... 5"
    # Pattern 2: "1. Title ................. 10"
    # Pattern 3: "CHAPTER ONE: Title ......... 15"
    
    lines = contents_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Try to find page numbers at the end of the line
        # Look for numbers that could be page numbers (considering roman numerals might be handled separately)
        page_match = re.search(r'\.+\s*(\d+)$', line)
        
        if page_match:
            page_num = int(page_match.group(1))
            
            # Extract chapter title (remove the page number and dots)
            title = re.sub(r'\.+\s*\d+$', '', line).strip()
            
            # Clean up the title
            title = re.sub(r'^[•\-]', '', title).strip()
            
            chapters.append({
                'title': title,
                'page_num': page_num
            })
    
    return chapters

def find_contents_page(reader):
    """
    Find the page containing the table of contents.
    Looks for keywords like "Contents", "Table of Contents", etc.
    """
    contents_keywords = ['contents', 'table of contents', 'index', 'content']
    
    for i, page in enumerate(reader.pages):
        text = page.extract_text().lower()
        if any(keyword in text for keyword in contents_keywords):
            # Check if this page actually has numbered entries (not just the title)
            if re.search(r'chapter|page|\.+\s*\d+', text, re.IGNORECASE):
                return i
    
    return None

def detect_page_numbering_system(reader):
    """
    Detect if the book uses roman numerals for front matter.
    Returns the offset between displayed page numbers and actual PDF page numbers.
    """
    # Check first few pages for roman numerals
    roman_pattern = r'^(i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv)$'
    
    for i in range(min(20, len(reader.pages))):
        page = reader.pages[i]
        text = page.extract_text().strip()
        
        # Look for page numbers (often at top or bottom)
        # This is a simplified approach - in reality you might need more sophisticated detection
        lines = text.split('\n')
        for line in lines[-3:]:  # Check last few lines for page numbers
            line = line.strip().lower()
            if re.match(roman_pattern, line):
                # Found roman numeral page number
                # The offset is: actual PDF page number - displayed roman page number
                # Since roman i should be page 1 in PDF, but might be at a different index
                return i + 1  # +1 because PDF pages are 0-indexed
    
    return 0  # No offset detected

def split_pdf_by_chapters(input_pdf_path, output_dir):
    """
    Split a PDF into chapters based on its table of contents.
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Read the PDF
    reader = PdfReader(input_pdf_path)
    total_pages = len(reader.pages)
    
    print(f"PDF loaded: {total_pages} pages total")
    
    # Detect page numbering offset
    offset = detect_page_numbering_system(reader)
    print(f"Detected page numbering offset: {offset} pages")
    
    # Find the table of contents page
    contents_page_num = find_contents_page(reader)
    if contents_page_num is None:
        print("Could not find table of contents automatically.")
        return
    
    print(f"Found table of contents on page {contents_page_num + 1}")
    
    # Extract the contents page text
    contents_page = reader.pages[contents_page_num]
    contents_text = contents_page.extract_text()
    
    # Extract chapters from the table of contents
    chapters = extract_chapters_from_contents(contents_text)
    
    if not chapters:
        print("Could not extract chapters from table of contents.")
        return
    
    print(f"Found {len(chapters)} chapters:")
    for i, chapter in enumerate(chapters):
        print(f"  {chapter['title']} - starts on page {chapter['page_num']}")
    
    # Adjust chapter page numbers based on the offset
    for chapter in chapters:
        # PDF pages are 0-indexed, while displayed page numbers are 1-indexed
        # Apply the offset to convert displayed page numbers to PDF indices
        pdf_page_index = chapter['page_num'] - 1 + offset
        chapter['pdf_start_page'] = max(0, pdf_page_index)  # Ensure non-negative
    
    # Sort chapters by page number
    chapters.sort(key=lambda x: x['pdf_start_page'])
    
    # Add the last page as the end of the final chapter
    chapters.append({
        'title': 'End of Book',
        'pdf_start_page': total_pages
    })
    
    # Create PDFs for each chapter
    created_chapters = []
    
    for i in range(len(chapters) - 1):
        chapter = chapters[i]
        next_chapter = chapters[i + 1]
        
        start_page = chapter['pdf_start_page']
        end_page = next_chapter['pdf_start_page'] - 1
        
        if start_page >= total_pages or start_page > end_page:
            print(f"Skipping invalid chapter: {chapter['title']} (pages {start_page}-{end_page})")
            continue
        
        # Create a new PDF writer
        writer = PdfWriter()
        
        # Add pages for this chapter
        for page_num in range(start_page, end_page + 1):
            if page_num < total_pages:
                writer.add_page(reader.pages[page_num])
        
        if len(writer.pages) == 0:
            print(f"Skipping empty chapter: {chapter['title']}")
            continue
        
        # Generate a filename from the chapter title
        safe_title = re.sub(r'[^\w\s-]', '', chapter['title'])
        safe_title = re.sub(r'[-\s]+', '_', safe_title)
        filename = f"Chapter_{i+1:02d}_{safe_title[:50]}.pdf"
        output_path = Path(output_dir) / filename
        
        # Write the chapter PDF
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        created_chapters.append({
            'title': chapter['title'],
            'pages': len(writer.pages),
            'filename': filename,
            'pdf_pages': f"{start_page + 1}-{end_page + 1}"
        })
    
    return created_chapters

def main():
    # Configuration
    input_pdf = "/content/drive/MyDrive/input.pdf"
    output_dir = "/content/drive/MyDrive/chapters"
    
    print("=" * 50)
    print("PDF Chapter Splitter")
    print("=" * 50)
    
    if not Path(input_pdf).exists():
        print(f"Error: Input PDF not found at {input_pdf}")
        print("Please ensure the file exists at: /content/drive/MyDrive/input.pdf")
        return
    
    try:
        chapters = split_pdf_by_chapters(input_pdf, output_dir)
        
        if chapters:
            print("\n" + "=" * 50)
            print("SUCCESS! Created chapter PDFs:")
            print("=" * 50)
            
            total_pages = 0
            for chapter in chapters:
                total_pages += chapter['pages']
                print(f"📄 {chapter['filename']}")
                print(f"   Title: {chapter['title']}")
                print(f"   Pages: {chapter['pages']} (PDF pages {chapter['pdf_pages']})")
                print()
            
            print(f"Total: {len(chapters)} chapters, {total_pages} pages")
            print(f"\nOutput directory: {output_dir}")
        else:
            print("No chapters were created. Please check the PDF format.")
            
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()