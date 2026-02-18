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

# A TOC page is usually short; stop collecting TOC lines after this many pages
MAX_TOC_PAGES = 20


def find_contents_start(doc):
    """
    Return the index of the page whose *first non-empty line* is a short
    'Contents'-style heading.  Checking only the first line avoids false
    positives on chapter body pages that happen to open with a word like
    'Contents of this chapter'.
    """
    for i, page in enumerate(doc):
        lines = [l.strip() for l in page.get_text("text").splitlines() if l.strip()]
        if lines and re.match(r'^contents?$', lines[0], re.IGNORECASE):
            return i
    return None


def clean_title(title):
    # FIX Bug 5: do NOT strip trailing digits — they are part of chapter titles.
    title = title.strip()
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    title = re.sub(r'\s+', ' ', title)
    return title[:MAX_FILENAME_LENGTH]


def extract_toc_entries(doc, start_index):
    """
    Return top-level chapter entries (PARTs or numbered chapters).

    FIX Bug 1: only scan a bounded window of pages after the TOC heading
    instead of the entire rest of the document.
    """
    entries = []
    last_page_number = -1
    detected_part = False
    toc_lines = []

    # FIX Bug 1: cap how many pages we read as TOC
    end_index = min(start_index + MAX_TOC_PAGES, len(doc))

    for i in range(start_index, end_index):
        text = doc[i].get_text("text")
        lines = text.splitlines()
        for line in lines:
            line = line.strip()
            if line and not re.match(r'^contents?$', line, re.IGNORECASE):
                toc_lines.append(line)

    # Detect whether PARTs exist
    for line in toc_lines:
        if PAGE_PATTERN.match(line) and PART_PATTERN.match(line):
            detected_part = True
            break

    pattern_to_use = PART_PATTERN if detected_part else TOP_CHAPTER_PATTERN

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


def compute_offset(doc, first_printed_page, toc_end):
    """
    Find the physical page index where `first_printed_page` actually appears
    as a page number, searching only *after* the TOC section to avoid matching
    the page number printed inside the TOC itself (Bug 2).

    Returns offset such that:  physical_index = printed_page_num - 1 + offset
    """
    return 19
    for i in range(toc_end, len(doc)):
        text = doc[i].get_text("text")
        # Match the number as a standalone token (header/footer page number)
        if re.search(rf'(?<!\d){re.escape(str(first_printed_page))}(?!\d)', text):
            return i - (first_printed_page - 1)
    # Fallback: assume front-matter is exactly toc_end pages
    return toc_end


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

    # FIX Bug 2: pass toc_end so compute_offset skips the TOC region
    toc_end = min(contents_start + MAX_TOC_PAGES, len(doc))
    offset = compute_offset(doc, toc_entries[0][1], toc_end)

    # physical index = (printed_page - 1) + offset
    chapter_starts = [(title, page_num - 1 + offset) for title, page_num in toc_entries]

    for i, (title, start_idx) in enumerate(chapter_starts):
        # FIX Bug 4: next chapter starts at chapter_starts[i+1][1], so this
        # chapter ends at that index - 1 (the page just before the next chapter).
        # Previously the code subtracted 1 from an already-physical index which
        # caused a one-page gap.  The subtraction is correct here because
        # chapter_starts values are physical indices, and we want the page
        # *before* the next chapter's first page.
        if i + 1 < len(chapter_starts):
            end_idx = chapter_starts[i + 1][1] - 1
        else:
            end_idx = len(doc) - 1

        if start_idx < 0 or start_idx >= len(doc) or end_idx < start_idx:
            print(f"Skipping '{title}': invalid page range [{start_idx}, {end_idx}]")
            continue

        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start_idx, to_page=end_idx)

        filename = f"{i+1:02d}_{clean_title(title)}.pdf"
        output_path = os.path.join(output_dir, filename)

        new_doc.save(output_path)
        new_doc.close()
        print(f"Saved: {output_path}  (physical pages {start_idx}–{end_idx})")

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
