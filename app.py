import PyPDF2
import os
import re
from pathlib import Path

def split_by_headers(input_path, output_dir):
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        delimiter_positions = []
        prev_first_line = None
        delimiter_positions.append(0)
        for page_num in range(total_pages - 1):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            if text:
                first_line = text.split('\n')[0] if '\n' in text else text
                if not (re.search(r'\d+\s*$', first_line.strip()) or re.search(r'^\s*\d+', first_line.strip())):
                    delimiter_positions.append(page_num)
        if total_pages > 0:
            delimiter_positions.append(total_pages)
        delimiter_positions = sorted(set(delimiter_positions))
    return delimiter_positions

def main():
    input_path = '/content/drive/MyDrive/input.pdf'
    output_dir = '/content/drive/MyDrive/split_chapters'
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

if __name__ == "__main__":
    total_pages = 0
    main()
