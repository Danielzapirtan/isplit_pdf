import os
import re
from pypdf import PdfReader, PdfWriter

INPUT_PATH = "/content/drive/MyDrive/input.pdf"
OUTPUT_DIR = "/content/drive/MyDrive/chapters"

# Regex patterns that commonly represent page numbers in headers
PAGE_NUMBER_PATTERNS = [
    r"\b\d+\b",            # plain numbers
    r"Page\s*\d+",         # "Page 12"
    r"P\s*\d+",            # "P 12"
    r"\d+\s*/\s*\d+",      # "12/300"
]

def clean_header(text):
    """
    Remove page numbers from header text so only the chapter name remains.
    """
    cleaned = text
    for pattern in PAGE_NUMBER_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

def extract_header_text(page):
    """
    Extract the header text from a page.
    Assumes the first line is the header.
    """
    text = page.extract_text() or ""
    lines = text.split("\n")
    if not lines:
        return ""
    return clean_header(lines[0])

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    reader = PdfReader(INPUT_PATH)
    num_pages = len(reader.pages)

    chapters = []
    current_chapter = None
    current_pages = []

    for i in range(num_pages):
        # Only check even pages (left pages): i % 2 == 1
        if i % 2 == 1:
            header = extract_header_text(reader.pages[i])

            if current_chapter is None:
                # First chapter
                current_chapter = header
                current_pages.extend([i - 1, i])
            else:
                if header == current_chapter:
                    # Same chapter
                    current_pages.extend([i - 1, i])
                else:
                    # New chapter begins
                    chapters.append((current_chapter, sorted(set(current_pages))))
                    current_chapter = header
                    current_pages = [i - 1, i]

    # Save last chapter
    if current_chapter is not None:
        chapters.append((current_chapter, sorted(set(current_pages))))

    # Write output PDFs
    for idx, (chapter_name, pages) in enumerate(chapters, start=1):
        writer = PdfWriter()
        for p in pages:
            if 0 <= p < num_pages:
                writer.add_page(reader.pages[p])

        safe_name = chapter_name.replace("/", "_").replace("\\", "_") or f"Chapter_{idx}"
        out_path = os.path.join(OUTPUT_DIR, f"{idx:02d}_{safe_name}.pdf")

        with open(out_path, "wb") as f:
            writer.write(f)

        print(f"Saved chapter: {chapter_name} → {out_path}")

if __name__ == "__main__":
    main()