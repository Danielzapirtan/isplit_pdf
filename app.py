import fitz
import re
import os
import argparse
import sys

INPUT_DEFAULT = "/content/drive/MyDrive/input.pdf"
OUTPUT_DEFAULT = "/content/drive/MyDrive/chapters"

# Match TOC entries with page number at the end
PAGE_PATTERN = re.compile(r'(.+?)[\s:/]+(\d+)$')

# Main chapters only: PART, Roman numerals, or digits + dot
MAIN_CHAPTER_PATTERN = re.compile(r'^(PART\s+[IVXLC]+|[IVXLC]+\.\s+|\d+\.\s+)', re.IGNORECASE)

# Likely Index/Notes entries
INDEX_LIKE_PATTERN = re.compile(r',\s*\d+|\(cont\)', re.IGNORECASE)

MAX_FILENAME_LENGTH = 120  # safe truncation for long titles


def find_contents_start(doc):
    """Return the first page index containing the word 'Contents'"""
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if text.lower().strip().startswith("content"):
            return i
    return None


def clean_title(title):
    """Sanitize and truncate a title to use as a filename"""
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    if len(title) > MAX_FILENAME_LENGTH:
        title = title[:MAX_FILENAME_LENGTH]
    return title


def is_main_chapter(title):
    """Check if the line is a main chapter, not a subheading or index entry"""
    if INDEX_LIKE_PATTERN.search(title):
        return False
    if not MAIN_CHAPTER_PATTERN.match(title):
        return False
    return True


def extract_toc_entries(doc, start_index):
    """Parse multi-page TOC and return a list of (title, printed_page)"""
    entries = []
    buffer = ""
    last_page_number = -1

    for i in range(start_index, len(doc)):
        text = doc[i].get_text("text")
        lines = text.splitlines()

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line.lower().startswith("content"):
                continue

            # Merge buffer if needed
            candidate = f"{buffer} {line}".strip() if buffer else line
            match = PAGE_PATTERN.match(candidate)

            if match:
                title = match.group(1).strip()
                page_number = int(match.group(2))

                # Accept only main chapters
                if not is_main_chapter(title):
                    buffer = ""
                    continue

                # Enforce strictly increasing page numbers
                if page_number <= last_page_number:
                    buffer = ""
                    continue

                entries.append((title, page_number))
                last_page_number = page_number
                buffer = ""
            else:
                # Avoid runaway accumulation
                if len(candidate) > 250:
                    buffer = ""
                else:
                    buffer = candidate

        # Stop TOC parsing if page numbers jump unrealistically high
        if entries and last_page_number > len(doc) + 50:
            break

    return entries


def compute_offset(doc, first_printed_page):
    """Compute PDF index offset from printed page numbers"""
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if re.search(rf'\b{first_printed_page}\b', text):
            return i - (first_printed_page - 1)
    return 0


def split_pdf_by_toc(input_path, output_dir):
    """Split a PDF into chapters based on TOC"""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    doc = fitz.open(input_path)

    contents_start = find_contents_start(doc)
    if contents_start is None:
        raise ValueError("Contents section not found.")

    toc_entries = extract_toc_entries(doc, contents_start)
    if not toc_entries:
        raise ValueError("No valid main chapter entries detected in TOC.")

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

        safe_title = clean_title(title)
        filename = f"{i+1:02d}_{safe_title}.pdf"
        output_path = os.path.join(output_dir, filename)

        new_doc.save(output_path)
        new_doc.close()

        print(f"Saved: {output_path}")

    doc.close()
    print("Splitting complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Robust PDF chapter splitter using main printed TOC."
    )
    parser.add_argument("--input", default=INPUT_DEFAULT, help="Path to input PDF")
    parser.add_argument("--output", default=OUTPUT_DEFAULT, help="Output directory")
    args = parser.parse_args()

    try:
        split_pdf_by_toc(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()