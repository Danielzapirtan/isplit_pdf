import fitz
import re
import os
import argparse
import sys

INPUT_DEFAULT = "/content/drive/MyDrive/input.pdf"
OUTPUT_DEFAULT = "/content/drive/MyDrive/chapters"

PAGE_PATTERN = re.compile(r'(.+?)[\s:/]+(\d+)$')

# Top-level patterns
PART_PATTERN = re.compile(r'^PART\s+[IVXLC]+', re.IGNORECASE)
TOP_CHAPTER_PATTERN = re.compile(r'^\d+\.\s+', re.IGNORECASE)

INDEX_LIKE_PATTERN = re.compile(r',\s*\d+|\(cont\)|Index|Notes', re.IGNORECASE)
MAX_FILENAME_LENGTH = 120


def find_contents_start(doc):
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if text.lower().strip().startswith("content"):
            return i
    return None


def clean_title(title):
    title = re.sub(r'\s+\d+$', '', title.strip())  # remove trailing numbers
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    title = re.sub(r'\s+', ' ', title)
    return title[:MAX_FILENAME_LENGTH]


def extract_toc_entries(doc, start_index):
    """Return top-level chapter entries (PARTs or top chapters)"""
    entries = []
    last_page_number = -1
    detected_part = False
    toc_lines = []

    # Collect all TOC lines first
    for i in range(start_index, len(doc)):
        text = doc[i].get_text("text")
        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            if line and not line.lower().startswith("content"):
                toc_lines.append(line)

    # Detect whether PARTs exist
    for line in toc_lines:
        if PAGE_PATTERN.match(line) and PART_PATTERN.match(line):
            detected_part = True
            break

    # Decide pattern to use
    pattern_to_use = PART_PATTERN if detected_part else TOP_CHAPTER_PATTERN

    # Extract entries
    for line in toc_lines:
        match = PAGE_PATTERN.match(line)
        if not match:
            continue
        title = match.group(1).strip()
        page_number = int(match.group(2))

        if INDEX_LIKE_PATTERN.search(title):
            continue
        if not pattern_to_use.match(title):
            continue
        if page_number <= last_page_number:
            continue

        entries.append((title, page_number))
        last_page_number = page_number

    return entries


def compute_offset(doc, first_printed_page):
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if re.search(rf'\b{first_printed_page}\b', text):
            return i - (first_printed_page - 1)
    return 0


def split_pdf_by_toc(input_path, output_dir):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    doc = fitz.open(input_path)

    contents_start = find_contents_start(doc)
    if contents_start is None:
        raise ValueError("Contents section not found.")

    toc_entries = extract_toc_entries(doc, contents_start)
    if not toc_entries:
        raise ValueError("No top-level chapters detected in TOC.")

    os.makedirs(output_dir, exist_ok=True)

    offset = compute_offset(doc, toc_entries[0][1])
    chapter_starts = [(title, page_num - 1 + offset) for title, page_num in toc_entries]

    for i, (title, start_idx) in enumerate(chapter_starts):
        end_idx = (
            chapter_starts[i + 1][1] - 1 if i + 1 < len(chapter_starts) else len(doc) - 1
        )

        if start_idx < 0 or end_idx < start_idx:
            continue

        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start_idx, to_page=end_idx)

        filename = f"{i+1:02d}_{clean_title(title)}.pdf"
        output_path = os.path.join(output_dir, filename)

        new_doc.save(output_path)
        new_doc.close()
        print(f"Saved: {output_path}")

    doc.close()
    print("Splitting complete.")


def main():
    parser = argparse.ArgumentParser(description="Split PDF by top-level chapters")
    parser.add_argument("--input", default=INPUT_DEFAULT, help="Input PDF path")
    parser.add_argument("--output", default=OUTPUT_DEFAULT, help="Output folder")
    args = parser.parse_args()

    try:
        split_pdf_by_toc(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()