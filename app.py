import fitz  # PyMuPDF
import os
import re

def clean_header(text):
    """
    Removes page numbers and extra whitespace to ensure 
    consistent chapter identification.
    """
    # Remove the word 'Page' and any following digits (case insensitive)
    text = re.sub(r'\bpage\s*\d+', '', text, flags=re.IGNORECASE)
    # Remove standalone numbers (usually the page number itself)
    text = re.sub(r'\b\d+\b', '', text)
    # Remove extra spaces and newlines
    return " ".join(text.split()).strip()

def split_pdf_by_headers(input_path, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    doc = fitz.open(input_path)
    total_pages = len(doc)
    
    current_chapter_id = None
    chapter_start_page = 0
    
    # Define the "Header Area" (x0, y0, x1, y1)
    header_rect = fitz.Rect(0, 0, 600, 60) 

    for page_num in range(total_pages):
        # Target EVEN pages (left-hand side in most PDF readers)
        if page_num % 2 == 0:
            page = doc[page_num]
            raw_text = page.get_textbox(header_rect)
            
            # Clean the text to ignore page numbers during comparison
            cleaned_text = clean_header(raw_text)

            # Skip comparison if the header is empty (e.g., a blank page)
            if not cleaned_text:
                continue

            # Detect a change in chapter
            if current_chapter_id is not None and cleaned_text != current_chapter_id:
                save_chunk(doc, chapter_start_page, page_num - 1, current_chapter_id, output_folder)
                chapter_start_page = page_num
            
            current_chapter_id = cleaned_text

    # Save the final chapter
    if current_chapter_id:
        save_chunk(doc, chapter_start_page, total_pages - 1, current_chapter_id, output_folder)
    
    doc.close()
    print("\nProcess finished successfully.")

def save_chunk(doc, start, end, name, folder):
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=start, to_page=end)
    
    # Create a safe filename (max 30 chars to keep it neat)
    safe_name = "".join([c for c in name if c.isalnum() or c == ' ']).strip()[:30]
    if not safe_name:
        safe_name = f"chapter_starting_page_{start+1}"
        
    output_path = os.path.join(folder, f"{safe_name}.pdf")
    new_doc.save(output_path)
    new_doc.close()
    print(f"Created: {output_path} (Pages {start+1}-{end+1})")

if __name__ == "__main__":
    INPUT_FILE = "/content/drive/MyDrive/input.pdf"
    OUTPUT_DIR = "/content/drive/MyDrive/split_chapters/"
    
    if os.path.exists(INPUT_FILE):
        split_pdf_by_headers(INPUT_FILE, OUTPUT_DIR)
    else:
        print(f"Error: {INPUT_FILE} not found.")
