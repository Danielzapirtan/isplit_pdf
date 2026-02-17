import fitz
import re
import os
import argparse
import sys

INPUT_DEFAULT = "/content/drive/MyDrive/input.pdf"
OUTPUT_DEFAULT = "/content/drive/MyDrive/chapters"

PAGE_PATTERN = re.compile(r'(.+?)[\s:/]+(\d+)$')


def find_contents_start(doc):
    for i in range(len(doc)):
        text = doc[i].get_text("text")
        if text.lower().strip().startswith("content"):
            return i
    return None


def detect_real_chapter_page(page):
    blocks = page.get_text("dict")["blocks"]
    for block in blocks:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            y_position = line["bbox"][1]
            max_font = max(span["size"] for span in line["spans"])
            if y_position < 200 and max_font > 16:
                return True
    return False


def extract_full_toc(doc, start_index):
    entries = []
    buffer = ""

    for i in range(start_index, len(doc)):
        text = doc[i].get_text("text")
        lines = text.splitlines()

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line.lower().startswith("content"):
                continue

            candidate = f"{buffer} {line}".strip() if buffer else line
            match = PAGE_PATTERN.match(candidate)

            if match:
                title = match.group(1).strip()
                page_number = int(match.group(2))
                entries.append((title, page_number))
                buffer = ""
            else:
                buffer = candidate

        if entries and detect_real_chapter_page(doc[i]):
            break

    return entries


def compute_offset(doc, first_printed_page):
    for i in range(len(doc)):
        text = doc[i].get_text("text")
        if re.search(rf'\b{first_printed_page}\b', text):
            return i - (first_printed_page - 1)
    return 0


def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)


def split_pdf_by_toc(input_path, output_dir):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    doc = fitz.open(input_path)

    contents_start = find_contents_start(doc)
    if contents_start is None:
        raise ValueError("Contents section not found.")

    toc_entries = extract_full_toc(doc, contents_start)
    if not toc_entries:
        raise ValueError("No TOC entries detected.")

    os.makedirs(output_dir, exist_ok=True)

    first_printed = toc_entries[0][1]
    offset = compute_offset(doc, first_printed)

    chapter_starts = [
        (title, printed_page - 1 + offset)
        for title, printed_page in toc_entries
    ]

    for i, (title, start_index) in enumerate(chapter_starts):
        end_index = (
            chapter_starts[i + 1][1] - 1
            if i + 1 < len(chapter_starts)
            else len(doc) - 1
        )

        if start_index < 0 or end_index < start_index:
            continue

        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start_index, to_page=end_index)

        filename = f"{i+1:02d}_{sanitize_filename(title)}.pdf"
        output_path = os.path.join(output_dir, filename)

        new_doc.save(output_path)
        new_doc.close()

        print(f"Saved: {output_path}")

    doc.close()
    print("Splitting complete.")


def main():
    parser = argparse.ArgumentParser(description="Split PDF by printed multi-page TOC.")
    parser.add_argument("--input", default=INPUT_DEFAULT, help="Input PDF path")
    parser.add_argument("--output", default=OUTPUT_DEFAULT, help="Output directory")
    args = parser.parse_args()

    try:
        split_pdf_by_toc(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()