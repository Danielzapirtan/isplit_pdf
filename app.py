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
                if re.search(r'^(\s|I|\d)+$', first_line.strip()) or re.search(r'^Chapter\s+\d+\.', first_line.strip()):
                    delimiter_positions.append(page_num)
            if text:
                lines = text.split("\n")
                for line in lines:
                    if re.search(r'^\d+\s+-\s+', line):
                        delimiter_positions.append(page_num)
        if total_pages > 0:
            delimiter_positions.append(total_pages)
        delimiter_positions = sorted(set(delimiter_positions))
    dp = delimiter_positions
    p = range(len(delimiter_positions))
    dp2 = [dp[i] for i in p]
    return dp2

def main():
    input_path = '/content/drive/MyDrive/boox/dbt_bpd.pdf'
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
    os.makedirs(output_dir, exist_ok=True)
    delimiter_positions = split_by_headers(input_path, output_dir)
    with open(input_path, 'rb') as file:
        pdf_reader = PyPDF2.PdfReader(file)
        total_pages = len(pdf_reader.pages)
        for i in range(len(delimiter_positions) - 1):
            start_page = delimiter_positions[i]
            end_page = delimiter_positions[i + 1]
            pdf_writer = PyPDF2.PdfWriter()
            for page_num in range(start_page, end_page):
                pdf_writer.add_page(pdf_reader.pages[page_num])
            output_filename = f"chapter_{i+1:03d}_pages_{start_page+1:03d}_to_{end_page:03d}.pdf"
            output_path = os.path.join(output_dir, output_filename)
            with open(output_path, 'wb') as output_file:
                pdf_writer.write(output_file)
            print(f"✅ Created: {output_filename} (pages {start_page+1}-{end_page})")
    print("=" * 70)
    print(f"🎉 Successfully split PDF into {len(delimiter_positions)-1} chapters!")
    print("=" * 70)

if __name__ == "__main__":
    total_pages = 0
    main()
