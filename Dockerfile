FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
        && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Set environment variables for Tesseract and Poppler paths
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# Entrypoint: process all PDFs from /app/input to /app/output
ENTRYPOINT ["python", "run_heading_extractor.py"] 