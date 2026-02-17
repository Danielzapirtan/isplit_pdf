import PyPDF2
import re
import os
from pathlib import Path

# Input file path
input_pdf = "/content/drive/MyDrive/input.pdf"
output_dir = "/content/drive/MyDrive/chapters"

# Create output directory if it doesn't exist
Path(output_dir).mkdir(parents=True, exist_ok=True)

def find_chapters(pdf_path):
    """Find chapter pages by looking for 'Chapter' patterns"""
    chapter_pages = []
    
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        
        # Common chapter patterns
        chapter_patterns = [
            r'chapter\s+\d+',  # "chapter 1", "chapter 2", etc.
            r'CHAPTER\s+\d+',  # "CHAPTER 1", "CHAPTER 2", etc.
            r'Chapter\s+\d+',  # "Chapter 1", "Chapter 2", etc.
            r'^\d+\.',         # "1. ", "2. " at start of line
        ]
        
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            
            if text:
                # Check first 500 characters for chapter patterns
                first_chars = text[:500].lower()
                for pattern in chapter_patterns:
                    if re.search(pattern, first_chars, re.IGNORECASE):
                        chapter_pages.append(page_num)
                        break
    
    return chapter_pages

def split_pdf_by_chapters(pdf_path, output_folder):
    # Find chapter pages
    chapter_pages = find_chapters(pdf_path)
    
    if not chapter_pages:
        print("No chapters found automatically!")
        return
    
    print(f"Found chapters on pages: {[p+1 for p in chapter_pages]}")
    
    # Add last page as end point
    with open(pdf_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        chapter_pages.append(total_pages)
    
    # Split into chapters
    for i in range(len(chapter_pages) - 1):
        start = chapter_pages[i]
        end = chapter_pages[i + 1] - 1
        
        pdf_writer = PyPDF2.PdfWriter()
        
        # Add pages to the new PDF
        for page_num in range(start, end + 1):
            pdf_writer.add_page(pdf_reader.pages[page_num])
        
        # Save the chapter
        output_path = os.path.join(output_folder, f"chapter_{i+1}.pdf")
        with open(output_path, 'wb') as output_file:
            pdf_writer.write(output_file)
        
        print(f"Created: chapter_{i+1}.pdf (pages {start+1}-{end+1})")

if __name__ == "__main__":
    if os.path.exists(input_pdf):
        split_pdf_by_chapters(input_pdf, output_dir)
        print("PDF splitting complete!")
    else:
        print(f"Error: {input_pdf} not found")