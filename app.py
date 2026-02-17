import os
import re
from typing import List, Tuple
import PyPDF2
from pathlib import Path

class PDFChapterSplitter:
    def __init__(self, pdf_path: str, output_dir: str = None):
        """
        Initialize the PDF Chapter Splitter.
        
        Args:
            pdf_path: Path to the input PDF file
            output_dir: Directory to save the split chapters (default: same as input file)
        """
        self.pdf_path = pdf_path
        
        if output_dir is None:
            # Default output directory: same as input file, with "_chapters" suffix
            pdf_dir = os.path.dirname(pdf_path)
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            self.output_dir = os.path.join(pdf_dir, f"{pdf_name}_chapters")
        else:
            self.output_dir = output_dir
            
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
    def extract_text_from_pdf(self) -> str:
        """Extract text from the PDF file."""
        text = ""
        try:
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- PAGE {page_num + 1} ---\n"
                        text += page_text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""
        return text
    
    def detect_chapters(self, text: str) -> List[Tuple[int, str, int]]:
        """
        Detect chapters based on common patterns.
        Returns list of tuples: (page_number, chapter_title, confidence_score)
        """
        chapters = []
        
        # Common chapter patterns (you can customize these)
        chapter_patterns = [
            r'chapter\s+(\d+|[IVXLC]+)[\.\s]*(.+?)(?=\n|$)',
            r'CHAPTER\s+(\d+|[IVXLC]+)[\.\s]*(.+?)(?=\n|$)',
            r'Chapter\s+(\d+|[IVXLC]+)[\.\s]*(.+?)(?=\n|$)',
            r'^\s*(\d+)[\.\s]*(.+?)(?=\n|$)',  # Just numbers at start of line
            r'PART\s+(\d+|[IVXLC]+)[\.\s]*(.+?)(?=\n|$)',
        ]
        
        lines = text.split('\n')
        current_page = 1
        
        for i, line in enumerate(lines):
            # Check if this line indicates a page break
            if '--- PAGE ' in line:
                current_page = int(line.replace('--- PAGE ', '').replace(' ---', ''))
                continue
                
            # Check for chapter patterns
            for pattern in chapter_patterns:
                match = re.search(pattern, line)
                if match:
                    # Simple confidence score based on position and formatting
                    confidence = 0.5
                    
                    # Higher confidence if line is at top of page (likely chapter start)
                    if i > 0 and '--- PAGE' in lines[i-1]:
                        confidence += 0.3
                    
                    # Higher confidence if line is standalone (not part of paragraph)
                    if i > 0 and len(lines[i-1].strip()) < 10:
                        confidence += 0.2
                    
                    # Lower confidence if it's just a number without context
                    if pattern == r'^\s*(\d+)[\.\s]*(.+?)(?=\n|$)' and not match.group(2):
                        confidence -= 0.2
                    
                    chapter_title = line.strip()
                    chapters.append((current_page, chapter_title, confidence))
                    break
        
        return chapters
    
    def split_by_chapters(self, chapters: List[Tuple[int, str, int]], min_confidence: float = 0.5):
        """
        Split the PDF into chapters based on detected chapter boundaries.
        """
        if not chapters:
            print("No chapters detected. Please check the PDF format or customize chapter patterns.")
            return []
        
        # Filter chapters by confidence
        chapters = [(page, title, conf) for page, title, conf in chapters if conf >= min_confidence]
        
        if not chapters:
            print(f"No chapters found with confidence >= {min_confidence}")
            return []
        
        # Sort chapters by page number
        chapters.sort(key=lambda x: x[0])
        
        try:
            # Open the PDF
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                # Create chapter PDFs
                output_files = []
                
                for i, (start_page, title, _) in enumerate(chapters):
                    # Determine end page
                    if i < len(chapters) - 1:
                        end_page = chapters[i + 1][0] - 1
                    else:
                        end_page = total_pages
                    
                    # Create PDF writer for this chapter
                    pdf_writer = PyPDF2.PdfWriter()
                    
                    # Add pages (convert to 0-based indexing)
                    for page_num in range(start_page - 1, end_page):
                        pdf_writer.add_page(pdf_reader.pages[page_num])
                    
                    # Generate filename from chapter title
                    safe_title = re.sub(r'[^\w\s-]', '', title)
                    safe_title = re.sub(r'[-\s]+', '_', safe_title)
                    filename = f"chapter_{i+1:02d}_{safe_title[:50]}.pdf"
                    filepath = os.path.join(self.output_dir, filename)
                    
                    # Save chapter
                    with open(filepath, 'wb') as output_file:
                        pdf_writer.write(output_file)
                    
                    output_files.append(filepath)
                    print(f"Created chapter {i+1}: {title} (pages {start_page}-{end_page})")
                
                return output_files
                
        except Exception as e:
            print(f"Error splitting PDF: {e}")
            return []
    
    def process(self, min_confidence: float = 0.5):
        """
        Main processing function to extract chapters and split PDF.
        """
        print(f"Processing PDF: {self.pdf_path}")
        print("Extracting text...")
        
        # Extract text from PDF
        text = self.extract_text_from_pdf()
        if not text:
            print("Failed to extract text from PDF.")
            return None
        
        print("Detecting chapters...")
        
        # Detect chapters
        chapters = self.detect_chapters(text)
        
        if not chapters:
            print("No chapters detected. You might want to:")
            print("1. Check if the PDF has clear chapter headings")
            print("2. Customize the chapter_patterns in detect_chapters()")
            print("3. Lower the confidence threshold")
            return None
        
        print(f"Found {len(chapters)} potential chapters:")
        for page, title, conf in chapters:
            print(f"  Page {page}: '{title}' (confidence: {conf:.2f})")
        
        # Split the PDF
        print(f"\nSplitting PDF into chapters...")
        output_files = self.split_by_chapters(chapters, min_confidence)
        
        if output_files:
            print(f"\nSuccess! Created {len(output_files)} chapters in:")
            print(f"  {self.output_dir}")
        else:
            print("\nFailed to split PDF.")
        
        return output_files

def main():
    # Define input path (update this to your actual path)
    input_path = "/content/drive/MyDrive/input.pdf"
    
    # Check if file exists
    if not os.path.exists(input_path):
        print(f"Error: PDF file not found at {input_path}")
        print("Please make sure the file exists at the specified path.")
        return
    
    # Create splitter and process
    splitter = PDFChapterSplitter(input_path)
    
    # You can adjust the confidence threshold if needed
    # Lower = more chapters detected, but may include false positives
    # Higher = fewer chapters, but more accurate
    output_files = splitter.process(min_confidence=0.5)
    
    if output_files:
        print("\nAll chapters saved successfully!")
    else:
        print("\nFailed to split PDF into chapters.")

if __name__ == "__main__":
    main()