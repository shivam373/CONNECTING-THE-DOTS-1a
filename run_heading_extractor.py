import os
import json
from pdf_utils import extract_headings

INPUT_DIR = "input"
OUTPUT_DIR = "output"

def process_pdf_dir(input_dir=INPUT_DIR, output_dir=OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".pdf"):
            input_path = os.path.join(input_dir, filename)
            base_name = os.path.splitext(filename)[0]
            output_path = os.path.join(output_dir, f"{base_name}.json")
            print(f"Processing: {filename}")
            result = extract_headings(input_path)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

def main():
    process_pdf_dir()

if __name__ == "__main__":
    main()
