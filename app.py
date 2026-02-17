import PyPDF2
import re
from pathlib import Path
import os
from typing import List, Tuple, Optional
import argparse

class PDFChapterSplitter:
    def __init__(self, pdf_path: str, output_dir: str = None):
        """
        Initialize the PDF Chapter Splitter
        
        Args:
            pdf_path: Path to the input PDF file
            output_dir: Directory where chapter PDFs will be saved (default: same as input)
        """
        self.pdf_path = Path(pdf_path)
        
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Set output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = self.pdf_path.parent / f"{self.pdf_path.stem}_chapters"
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Store chapters information
        self.chapters = []  # List of (chapter_title, start_page, end_page)
        
    def extract_even_page_headers(self) -> List[Tuple[int, str]]:
        """
        Extract headers from even-numbered pages
        
        Returns:
            List of tuples (page_number, header_text)
        """
        headers = []
        
        with open(self.pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num in range(len(pdf_reader.pages)):
                # Check if page number is even (1-based indexing, so page 2 is even)
                if (page_num + 1) % 2 == 0:
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    
                    if text:
                        # Try to extract header (first line of the page)
                        lines = text.split('\n')
                        if lines:
                            # Clean up the header text
                            header = lines[0].strip()
                            
                            # Skip if header is too short or looks like page number
                            if len(header) > 3 and not header.replace(' ', '').isdigit():
                                headers.append((page_num + 1, header))
        
        return headers
    
    def identify_chapters(self, headers: List[Tuple[int, str]]) -> List[Tuple[str, int, int]]:
        """
        Identify chapter boundaries based on headers
        
        Args:
            headers: List of (page_number, header_text) from even pages
            
        Returns:
            List of (chapter_title, start_page, end_page)
        """
        chapters = []
        
        if not headers:
            print("No headers found on even pages!")
            return chapters
        
        # Get total number of pages
        with open(self.pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
        
        # Process headers to find chapter boundaries
        # We'll consider a header as a chapter title if it changes significantly
        # from the previous header
        
        prev_header = None
        chapter_start = 1  # Start from page 1
        
        for i, (page_num, header) in enumerate(headers):
            # If this is a new header (significantly different from previous)
            if prev_header and self._is_new_chapter(prev_header, header):
                # End previous chapter at page_num - 1
                chapters.append((prev_header, chapter_start, page_num - 1))
                chapter_start = page_num
            
            prev_header = header
            
            # If this is the last header
            if i == len(headers) - 1:
                chapters.append((header, chapter_start, total_pages))
        
        return chapters
    
    def _is_new_chapter(self, prev_header: str, current_header: str) -> bool:
        """
        Determine if the header change indicates a new chapter
        
        Args:
            prev_header: Previous page's header
            current_header: Current page's header
            
        Returns:
            True if this is a new chapter, False otherwise
        """
        # Remove common words and normalize
        common_words = ['page', 'chapter', 'contents', 'index', 'appendix']
        
        prev_clean = self._normalize_header(prev_header, common_words)
        current_clean = self._normalize_header(current_header, common_words)
        
        # If headers are significantly different, consider it a new chapter
        if len(prev_clean) > 0 and len(current_clean) > 0:
            # Check if they're different enough (not just minor variations)
            similarity = self._calculate_similarity(prev_clean, current_clean)
            return similarity < 0.7  # Threshold for considering it a new chapter
        
        return prev_clean != current_clean
    
    def _normalize_header(self, header: str, common_words: List[str]) -> str:
        """Normalize header text for comparison"""
        header = header.lower()
        for word in common_words:
            header = header.replace(word, '')
        return re.sub(r'[^\w\s]', '', header).strip()
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ratio between two texts"""
        # Simple similarity based on common words
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def split_pdf_by_chapters(self):
        """Split the PDF into chapter-based PDF files"""
        
        print(f"Processing PDF: {self.pdf_path}")
        print("Extracting headers from even pages...")
        
        # Extract headers from even pages
        headers = self.extract_even_page_headers()
        
        if not headers:
            print("No headers found on even pages. Trying alternative approach...")
            # Alternative: Try to find headers on all pages that look like chapter titles
            headers = self._find_chapter_titles_all_pages()
        
        print(f"Found {len(headers)} potential chapter headers")
        
        # Identify chapters
        self.chapters = self.identify_chapters(headers)
        
        if not self.chapters:
            print("No chapters identified!")
            return
        
        print(f"\nIdentified {len(self.chapters)} chapters:")
        for i, (title, start, end) in enumerate(self.chapters, 1):
            print(f"  Chapter {i}: '{title}' (pages {start}-{end})")
        
        # Split the PDF
        self._write_chapter_pdfs()
    
    def _find_chapter_titles_all_pages(self) -> List[Tuple[int, str]]:
        """
        Alternative method: Find potential chapter titles on all pages
        """
        potential_headers = []
        chapter_patterns = [
            r'^chapter\s+\d+',
            r'^\d+\.\s+[A-Z]',
            r'^[A-Z][A-Z\s]{5,}',
        ]
        
        with open(self.pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                if text:
                    lines = text.split('\n')
                    for line in lines[:3]:  # Check first few lines
                        line = line.strip()
                        for pattern in chapter_patterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                potential_headers.append((page_num + 1, line))
                                break
        
        return potential_headers
    
    def _write_chapter_pdfs(self):
        """Write each chapter to a separate PDF file"""
        
        with open(self.pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            for i, (title, start_page, end_page) in enumerate(self.chapters, 1):
                # Create a new PDF for this chapter
                pdf_writer = PyPDF2.PdfWriter()
                
                # Add pages (convert to 0-based indexing)
                for page_num in range(start_page - 1, end_page):
                    pdf_writer.add_page(pdf_reader.pages[page_num])
                
                # Generate filename from title
                safe_title = re.sub(r'[^\w\s-]', '', title)
                safe_title = re.sub(r'[-\s]+', '_', safe_title)
                filename = f"Chapter_{i:02d}_{safe_title[:50]}.pdf"
                output_path = self.output_dir / filename
                
                # Write the chapter PDF
                with open(output_path, 'wb') as output_file:
                    pdf_writer.write(output_file)
                
                print(f"Created: {output_path}")

def main():
    parser = argparse.ArgumentParser(description='Split PDF into chapters based on even page headers')
    parser.add_argument('pdf_path', nargs='?', 
                       default='/content/drive/MyDrive/input.pdf',
                       help='Path to the input PDF file')
    parser.add_argument('-o', '--output-dir', 
                       help='Output directory for chapter PDFs')
    
    args = parser.parse_args()
    
    try:
        # Create splitter instance
        splitter = PDFChapterSplitter(args.pdf_path, args.output_dir)
        
        # Split the PDF
        splitter.split_pdf_by_chapters()
        
        print(f"\n✅ PDF successfully split into chapters!")
        print(f"Chapter files saved in: {splitter.output_dir}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())