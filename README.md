# PDF Title & Heading Extraction Solution

This project extracts **titles** and **headings** from PDF documents using a hybrid approach that combines font-based analysis (via `pdfplumber`) and OCR-based fallback (via `Tesseract`) for image-based PDFs or scanned documents.

---

## Approach

### 1. Text-Based Extraction (via `pdfplumber`)
- Parses each page's character-level metadata including font size, font name, and position.
- Identifies headings based on heuristics such as:
  - Font size
  - Font weight (bold vs regular)
  - Font family (e.g., Arial)
- Filters overly long lines or noisy content.
- Determines heading levels (H1, H2, H3) based on font size thresholds.
- Extracts the document **title** using the largest and boldest text on the first page.

### 2. OCR-Based Fallback (via `Tesseract`)
- If a page has fewer than 10 text characters, it is assumed to be image-based.
- The page is converted into a high-resolution image using `pdf2image`.
- Text is extracted using `pytesseract` and grouped by line and font size to estimate headings.

### 3. Post-Processing
- Removes duplicate or repeated characters (e.g., "RReeqquueesstt" → "Request").
- Merges multi-line headings.
- Deduplicates and simplifies heading text.
- Applies final heuristics to assign heading levels.

---

## Libraries and Tools Used

- [pdfplumber](https://github.com/jsvine/pdfplumber) (PDF parsing)
- [pdf2image](https://github.com/Belval/pdf2image) (PDF to image conversion)
- [pytesseract](https://github.com/madmaze/pytesseract) (OCR interface for scanned pdf)
- [Pillow](https://python-pillow.org/) (Image processing)
- [poppler-utils](https://poppler.freedesktop.org/) (PDF rendering)
- [tesseract-ocr](https://github.com/tesseract-ocr/tesseract) (OCR engine)

---

## How to Build and Run (via Docker)

> This section is for documentation. The container should follow the expected execution behavior during testing.


**Note:** All dependencies and models are automatically installed within the Docker container during the build process. No additional downloads or setup required.

### Build the Docker Image
```
docker build --platform linux/amd64 -t adobe_pdf_extractor:latest .
```

### Run the Solution
```
docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output --network none adobe_pdf_extractor:latest
```

- Place your PDF files in the `input/` directory.
- The container will process all PDFs and write JSON outputs to the `output/` directory.

## Expected Execution
- All PDFs in `/app/input` are processed automatically.
- Each `filename.pdf` produces `filename.json` in `/app/output`.
