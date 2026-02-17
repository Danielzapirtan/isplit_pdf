import fitz  # PyMuPDF

def print_toc_structure(pdf_path):
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    
    if not toc:
        print("No embedded TOC found.")
        return
    
    print("Embedded TOC entries:")
    for level, title, page in toc:
        print(f"Level {level} | Page {page} | {title}")
    
    doc.close()

print_toc_structure("/content/drive/MyDrive/input.pdf")