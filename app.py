import PyPDF2
import os
from pathlib import Path

def is_page_blank(page):
    """Check if a PDF page is blank (no text or images)"""
    try:
        text = page.extract_text()
        # Consider page blank if extracted text is None, empty, or only whitespace
        return not (text and text.strip())
    except:
        # If we can't extract text, assume it might be blank
        return True

def split_pdf_by_blank_pages(input_path, output_dir):
    """
    Split PDF into chapters based on blank pages as delimiters.
    Blank pages are not included in the output chapters.
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Open the PDF
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        
        print(f"Total pages in PDF: {total_pages}")
        
        chapters = []
        current_chapter = []
        chapter_count = 1
        
        for page_num in range(total_pages):
            page = pdf_reader.pages[page_num]
            
            if is_page_blank(page):
                # Found a delimiter - save current chapter if it has pages
                if current_chapter:
                    chapters.append({
                        'pages': current_chapter.copy(),
                        'chapter_num': chapter_count
                    })
                    chapter_count += 1
                    current_chapter = []
                print(f"Found blank page at position {page_num + 1}")
            else:
                # Add page to current chapter
                current_chapter.append(page_num)
        
        # Don't forget the last chapter if it exists
        if current_chapter:
            chapters.append({
                'pages': current_chapter.copy(),
                'chapter_num': chapter_count
            })
        
        print(f"\nFound {len(chapters)} chapters")
        
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
            
            print(f"Created {output_filename} with {len(chapter['pages'])} pages "
                  f"(pages {chapter['pages'][0] + 1} to {chapter['pages'][-1] + 1})")

def main():
    # Configuration
    input_path = '/content/drive/MyDrive/input.pdf'
    output_dir = '/content/drive/MyDrive/split_chapters'
    
    # Check if input file exists
    if not os.path.exists(input_path):
        print(f"Error: Input file not found at {input_path}")
        return
    
    print("Starting PDF split process...")
    print(f"Input file: {input_path}")
    print(f"Output directory: {output_dir}")
    print("-" * 50)
    
    try:
        split_pdf_by_blank_pages(input_path, output_dir)
        print("-" * 50)
        print("PDF splitting completed successfully!")
    except Exception as e:
        print(f"Error during PDF splitting: {str(e)}")

if __name__ == "__main__":
    # Install required package if not already installed
    try:
        import PyPDF2
    except ImportError:
        print("Installing required package: PyPDF2")
        import subprocess
        subprocess.check_call(['pip', 'install', 'PyPDF2'])
        import PyPDF2
    
    main()