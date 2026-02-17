import os
from pypdf import PdfReader, PdfWriter

INPUT_PATH = "/content/drive/MyDrive/input.pdf"
OUTPUT_DIR = "/content/drive/MyDrive/chapters"

def extract_header_text(page):
    """
    Extracts the header text from a page.
    You may adjust this depending on how your PDF is structured.
    """
    text = page.extract_text() or ""
    lines = text.split("\n")
    if lines:
        return lines[0].strip()  # assume header is first line
    return ""

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    reader = PdfReader(INPUT_PATH)
    num_pages = len(reader.pages)

    chapters = []  # list of (chapter_name, [page_indices])
    current_chapter = None
    current_pages = []

    for i in range(num_pages):
        page = reader.pages[i]

        # Check only even-numbered pages (1-based left pages)
        if i % 2 == 1:
            header = extract_header_text(page)

            if current_chapter is None:
                # first chapter
                current_chapter = header
                current_pages.append(i - 1 if i > 0 else i)
                current_pages.append(i)
            else:
                if header == current_chapter:
                    # same chapter
                    current_pages.append(i - 1 if i > 0 else i)
                    current_pages.append(i)
                else:
                    # chapter changed → save previous
                    chapters.append((current_chapter, sorted(set(current_pages))))
                    current_chapter = header
                    current_pages = [i - 1 if i > 0 else i, i]

    # Save last chapter
    if current_chapter is not None:
        chapters.append((current_chapter, sorted(set(current_pages))))

    # Write PDFs
    for idx, (chapter_name, pages) in enumerate(chapters, start=1):
        writer = PdfWriter()
        for p in pages:
            writer.add_page(reader.pages[p])

        safe_name = chapter_name.replace("/", "_").replace("\\", "_")
        out_path = os.path.join(OUTPUT_DIR, f"{idx:02d}_{safe_name}.pdf")

        with open(out_path, "wb") as f:
            writer.write(f)

        print(f"Saved chapter: {chapter_name} → {out_path}")

if __name__ == "__main__":
    main()