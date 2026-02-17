import fitz  # PyMuPDF
import os

def split_pdf_by_headers(input_path, output_folder):
    # Ensure output directory exists
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    doc = fitz.open(input_path)
    total_pages = len(doc)
    
    current_chapter_name = None
    chapter_start_page = 0
    
    # Define the "Header Area" (Adjust these coordinates if necessary)
    # Rect format: (x0, y0, x1, y1) - y0 to y1 should cover the top of the page
    header_rect = fitz.Rect(0, 0, 600, 50) 

    for page_num in range(total_pages):
        # We check the header on EVEN pages (0-indexed 0, 2, 4...) 
        # as per your "left page" requirement.
        if page_num % 2 == 0:
            page = doc[page_num]
            header_text = page.get_textbox(header_rect).strip()

            # If a header is found and it's different from the current one
            if header_text and header_text != current_chapter_name:
                
                # If we were already tracking a chapter, save the previous chunk
                if current_chapter_name is not None:
                    save_chunk(doc, chapter_start_page, page_num - 1, current_chapter_name, output_folder)
                
                # Start a new chapter tracking
                current_chapter_name = header_text
                chapter_start_page = page_num

    # Save the final chapter
    if current_chapter_name:
        save_chunk(doc, chapter_start_page, total_pages - 1, current_chapter_name, output_folder)
    
    doc.close()
    print("Splitting complete.")

def save_chunk(doc, start, end, name, folder):
    """Saves a range of pages into a new PDF."""
    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=start, to_page=end)
    
    # Clean filename to prevent OS errors
    clean_name = "".join([c for c in name if c.isalnum() or c in (' ', '_')]).rstrip()
    output_path = os.path.join(folder, f"{clean_name}.pdf")
    
    new_doc.save(output_path)
    new_doc.close()
    print(f"Saved: {output_path} (Pages {start+1} to {end+1})")

if __name__ == "__main__":
    INPUT_FILE = "/content/drive/MyDrive/input.pdf"
    OUTPUT_DIR = "/content/drive/MyDrive/split_chapters/"
    
    if os.path.exists(INPUT_FILE):
        split_pdf_by_headers(INPUT_FILE, OUTPUT_DIR)
    else:
        print(f"Error: File not found at {INPUT_FILE}")
