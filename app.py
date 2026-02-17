import fitz
import re
import os
import argparse
import sys

INPUT_DEFAULT = "/content/drive/MyDrive/input.pdf"
OUTPUT_DEFAULT = "/content/drive/MyDrive/chapters"

PAGE_PATTERN = re.compile(r'(.+?)[\s:/]+(\d+)$')
CHAPTER_START_PATTERN = re.compile(
    r'^(PART\s+[IVXLC]+|[IVXLC]+\.\s+|\d+\.\s+)', re.IGNORECASE
)
INDEX_LIKE_PATTERN = re.compile(r',\s*\d+')
MAX_FILENAME_LENGTH = 120


def find_contents_start(doc):
    for i in range(len(doc)):
        text = doc[i].get_text("text")
        if text.lower().strip().startswith("content"):
            return i
    return None


def clean_title(title):
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    if len(title) > MAX_FILENAME_LENGTH:
        title = title[:MAX_FILENAME_LENGTH]
    return title


def is_valid_chapter_title(title):
    if INDEX_LIKE_PATTERN.search(title):
        return False
    if "(cont" in title.lower():
        return False
    if not CHAPTER_START_PATTERN.match(title):
        return False
    return True


def extract_full_toc(doc, start_index):
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

            candidate = f"{buffer} {line}".strip() if buffer else line
            match = PAGE_PATTERN.match(candidate)

            if match:
                title = match.group(1).strip()
                page_number = int(match.group(2))

                if not is_valid_chapter_title(title):
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
                if len(candidate) > 250:
                    buffer = ""
                else:
                    buffer = candidate

        # Hard stop if page numbers become unrealistic
        if entries and last_page_number > len(doc) + 50:
            break

    return entries


def compute_offset(doc, first_printed_page):
    for i in range(len(doc)):
        text = doc[i].get_text("text")
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

    toc_entries = extract_full_toc(doc, contents_start)
    if not toc_entries:
        raise ValueError("No valid chapter entries detected in TOC.")

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
        description="Robust PDF chapter splitter using printed multi-page TOC."
    )
    parser.add_argument("--input", default=INPUT_DEFAULT)
    parser.add_argument("--output", default=OUTPUT_DEFAULT)
    args = parser.parse_args()

    try:
        split_pdf_by_toc(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()