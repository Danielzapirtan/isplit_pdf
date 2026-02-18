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

# Minimum fraction of lines on a page that must look like TOC entries
TOC_LINE_RATIO_THRESHOLD = 0.15


def find_contents_start(doc):
    """
    Return the index of the page whose *first non-empty line* is a short
    'Contents'-style heading.  Checking only the first line avoids false
    positives on chapter body pages that happen to open with a word like
    'Contents of this chapter'.
    """
    for i, page in enumerate(doc):
        lines = [l.strip() for l in page.get_text("text").splitlines() if l.strip()]
        # BUG 1: Only check first line, but need to handle multi-word headings like "Table of Contents"
        if lines and re.match(r'^(contents?|table\s+of\s+contents)$', lines[0], re.IGNORECASE):
            return i
    return None


def clean_title(title):
    # BUG 5: Need to handle trailing digits in chapter titles
    # But also need to clean up other problematic characters
    title = title.strip()
    # Remove problematic filename characters
    title = re.sub(r'[\\/*?:"<>|]', "", title)
    # Normalize whitespace
    title = re.sub(r'\s+', ' ', title)
    # Remove any trailing dots or spaces (but keep digits)
    title = title.rstrip('. ')
    return title[:MAX_FILENAME_LENGTH]


def is_toc_page(page):
    """
    Return True if this page looks like it is still part of the TOC.
    We count how many non-empty lines match PAGE_PATTERN (title ... number)
    and require that fraction to exceed a threshold.
    """
    lines = [l.strip() for l in page.get_text("text").splitlines() if l.strip()]
    if not lines:
        return False
    # BUG 2: PAGE_PATTERN might not match all TOC line formats
    matched = sum(1 for l in lines if PAGE_PATTERN.match(l))
    return (matched / len(lines)) >= TOC_LINE_RATIO_THRESHOLD


def collect_toc_lines(doc, start_index):
    """
    Walk pages from start_index onward, accumulating lines from every page
    that still looks like a TOC page.
    """
    toc_lines = []
    toc_end = start_index  # Initialize properly

    for i in range(start_index, len(doc)):
        page = doc[i]
        # Always include the heading page; after that, test each page
        if i == start_index or is_toc_page(page):
            page_text = page.get_text("text")
            for line in page_text.splitlines():
                line = line.strip()
                # Skip empty lines and the Contents heading itself
                if line and not re.match(r'^(contents?|table\s+of\s+contents)$', line, re.IGNORECASE):
                    toc_lines.append(line)
            toc_end = i + 1
        else:
            break  # left the TOC section

    return toc_lines, toc_end


def extract_toc_entries(doc, start_index):
    """
    Return (entries, toc_end) where entries is a list of (title, printed_page)
    for top-level chapters, and toc_end is the physical index of the first
    page after the TOC.
    """
    entries = []
    last_page_number = -1
    detected_part = False

    toc_lines, toc_end = collect_toc_lines(doc, start_index)

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
        # BUG 3: Handle page numbers that might have Roman numerals or other formats
        try:
            page_number = int(match.group(2))
        except ValueError:
            continue  # Skip non-integer page numbers

        # Skip index-like entries
        if INDEX_LIKE_PATTERN.search(title):
            continue
        
        # Check if this is a top-level entry
        if not pattern_to_use.match(title):
            continue
        
        # Skip duplicate or out-of-order page numbers
        if page_number <= last_page_number:
            continue

        entries.append((title, page_number))
        last_page_number = page_number

    return entries, toc_end


def compute_offset(doc, first_printed_page, toc_end):
    """
    Find the physical page index where `first_printed_page` actually appears
    as a page number, searching only *after* the TOC section.
    """
    # BUG 2: Need to be more robust in page number detection
    for i in range(toc_end, min(toc_end + 50, len(doc))):  # Limit search range
        text = doc[i].get_text("text")
        # Look for the page number with various possible formats
        patterns = [
            rf'\b{re.escape(str(first_printed_page))}\b',  # Word boundary
            rf'\n\s*{re.escape(str(first_printed_page))}\s*\n',  # Isolated on line
            rf'Page\s+{re.escape(str(first_printed_page))}',  # "Page X" format
        ]
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return i - (first_printed_page - 1)
    
    # Fallback: assume front-matter is exactly toc_end pages
    print(f"Warning: Could not find page {first_printed_page}, using offset {toc_end}")
    return toc_end


def split_pdf_by_toc(input_path, output_dir):
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    doc = fitz.open(input_path)
    print(f"Opened PDF with {len(doc)} pages")

    contents_start = find_contents_start(doc)
    if contents_start is None:
        # BUG 4: Try alternative search for TOC
        print("Warning: Contents page not found, searching for TOC pattern...")
        for i, page in enumerate(doc):
            if i < 10:  # Check first 10 pages
                text = page.get_text("text")
                if re.search(r'chapter.*\d+', text, re.IGNORECASE):
                    contents_start = i
                    break
        
        if contents_start is None:
            raise ValueError("Contents section not found.")

    print(f"Contents found on page {contents_start}")

    toc_entries, toc_end = extract_toc_entries(doc, contents_start)
    if not toc_entries:
        raise ValueError("No top-level chapters detected in TOC.")

    print(f"Found {len(toc_entries)} chapters")
    os.makedirs(output_dir, exist_ok=True)

    # Calculate offset
    offset = compute_offset(doc, toc_entries[0][1], toc_end)
    print(f"Calculated offset: {offset}")

    # BUG 5: Fix physical index calculation
    chapter_starts = []
    for title, page_num in toc_entries:
        phys_idx = page_num - 1 + offset
        # Ensure physical index is valid
        if phys_idx < 0:
            phys_idx = 0
        elif phys_idx >= len(doc):
            phys_idx = len(doc) - 1
        chapter_starts.append((title, phys_idx))

    for i, (title, start_idx) in enumerate(chapter_starts):
        # Determine end index
        if i + 1 < len(chapter_starts):
            # End just before the next chapter starts
            end_idx = chapter_starts[i + 1][1] - 1
        else:
            # Last chapter goes to the end of the document
            end_idx = len(doc) - 1

        # Validate indices
        if start_idx < 0 or start_idx >= len(doc):
            print(f"Skipping '{title}': invalid start index {start_idx}")
            continue
        
        if end_idx < start_idx:
            print(f"Warning: '{title}' has end index {end_idx} < start index {start_idx}, adjusting")
            end_idx = start_idx

        # Create new PDF for this chapter
        new_doc = fitz.open()
        try:
            new_doc.insert_pdf(doc, from_page=start_idx, to_page=end_idx)
            
            # Create filename
            clean_title_text = clean_title(title)
            filename = f"{i+1:02d}_{clean_title_text}.pdf"
            # Ensure filename isn't too long
            if len(filename) > 255:  # Filesystem limit
                filename = filename[:250] + ".pdf"
            
            output_path = os.path.join(output_dir, filename)
            
            # Save
            new_doc.save(output_path)
            print(f"Saved: {output_path}  (physical pages {start_idx}–{end_idx})")
            
        except Exception as e:
            print(f"Error saving chapter '{title}': {e}")
        finally:
            new_doc.close()

    doc.close()
    print("Splitting complete.")


def main():
    parser = argparse.ArgumentParser(description="Split PDF by top-level chapters")
    parser.add_argument("--input", default=INPUT_DEFAULT, help="Input PDF path")
    parser.add_argument("--output", default=OUTPUT_DEFAULT, help="Output folder")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    try:
        if args.debug:
            print(f"Input: {args.input}")
            print(f"Output: {args.output}")
        split_pdf_by_toc(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()