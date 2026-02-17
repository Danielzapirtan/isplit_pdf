import fitz
import re
import os
import argparse
import sys

INPUT_DEFAULT = "/content/drive/MyDrive/input.pdf"
OUTPUT_DEFAULT = "/content/drive/MyDrive/chapters"

# Pattern to match TOC lines ending with a page number
PAGE_PATTERN = re.compile(r'(.+?)[\s:/]+(\d+)$')

# Only main chapters: PART, Roman numerals, or digits with dot
MAIN_CHAPTER_PATTERN = re.compile(r'^(PART\s+[IVXLC]+|[IVXLC]+\.\s+|\d+\.\s+)', re.IGNORECASE)

# Lines that indicate index-like entries or notes
INDEX_LIKE_PATTERN = re.compile(r',\s*\d+|\(cont\)|Index|Notes', re.IGNORECASE)

MAX_FILENAME_LENGTH = 120


def find_contents_start(doc):
    """Return the first page index containing 'Contents'"""
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if text.lower().strip().startswith("content"):
            return i
    return None


def clean_title(title):
    """Sanitize title for filenames"""
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    return title[:MAX_FILENAME_LENGTH]


def is_main_chapter(title):
    """Return True only for main chapters, not subheadings"""
    if INDEX_LIKE_PATTERN.search(title):
        return False
    return bool(MAIN_CHAPTER_PATTERN.match(title))


def extract_toc_entries(doc, start_index):
    """Extract main chapter entries (title, page) from TOC"""
    entries = []
    last_page_number = -1

    for i in range(start_index, len(doc)):
        text = doc[i].get_text("text")
        lines = text.splitlines()

        for line in lines:
            line = line.strip()
            if not line or line.lower().startswith("content"):
                continue

            match = PAGE_PATTERN.match(line)
            if match:
                title = match.group(1).strip()
                page_number = int(match.group(2))

                if not is_main_chapter(title):
                    continue

                # Ensure strictly increasing page numbers
                if page_number <= last_page_number:
                    continue

                entries.append((title, page_number))
                last_page_number = page_number

        # Stop if page numbers jump unrealistically high (likely Index)
        if entries and last_page_number > len(doc) + 50:
            break

    return entries


def compute_offset(doc, first_printed_page):
    """Compute PDF page offset for printed page numbers"""
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if re.search(rf'\b{first_printed_page}\b', text):
            return i - (first_printed_page - 1)
    return 0


def split_pdf_by_toc(input_path, output_dir):
    """Split PDF into main chapters only"""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    doc = fitz.open(input_path)

    contents_start = find_contents_start(doc)
    if contents_start is None:
        raise ValueError("Contents section not found.")

    toc_entries = extract_toc_entries(doc, contents_start)
    if not toc_entries:
        raise ValueError("No main chapters detected in TOC.")

    os.makedirs(output_dir, exist_ok=True)

    offset = compute_offset(doc, toc_entries[0][1])
    chapter_starts = [
        (title, page_num - 1 + offset) for title, page_num in toc_entries
    ]

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
    parser = argparse.ArgumentParser(
        description="Split PDF into main chapters using printed TOC"
    )
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