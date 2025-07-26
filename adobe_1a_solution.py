import os
import json
import pdfplumber
from collections import defaultdict
import re
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
import platform  # ✅ for OS check

# --- Path Setup ---
# Use Tesseract and Poppler only on Windows; Linux/Docker uses system installations
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"model\Tesseract-OCR\tesseract.exe"
    poppler_path = r"additional_requirements\poppler-24.08.0\Library\bin"
else:
    poppler_path = None  # Let pdf2image find poppler automatically

INPUT_DIR = "input"
OUTPUT_DIR = "output"

# --- Utility Functions ---
def is_bold(font_name):
    return 'bold' in font_name.lower() or 'bd' in font_name.lower()

def extract_font_family(font_name):
    return font_name.split("-")[0] if "-" in font_name else font_name.split(",")[0]

def clean_line_text(text):
    text = text.strip()
    if text.endswith('.') and not text.endswith('..'):
        return ""
    match = re.search(r"\.{3,}", text)
    if match:
        return text[:match.start()].strip()
    return text

def split_on_large_gaps(line_chars, gap_threshold=50):
    segments = []
    current_segment = []
    line_chars.sort(key=lambda c: c["x0"])
    for i in range(len(line_chars)):
        current_segment.append(line_chars[i])
        if i < len(line_chars) - 1:
            cur_end = line_chars[i]["x1"]
            next_start = line_chars[i + 1]["x0"]
            gap = next_start - cur_end
            if gap > gap_threshold:
                segments.append(current_segment)
                current_segment = []
    if current_segment:
        segments.append(current_segment)
    return segments

def reconstruct_text(chars, space_threshold=1.5):
    chars = sorted(chars, key=lambda c: c["x0"])
    text = ""
    for i, c in enumerate(chars):
        if i > 0:
            gap = c["x0"] - chars[i - 1]["x1"]
            if gap > space_threshold:
                text += " "
        text += c["text"]
    return text

def merge_similar_headings(lines, y_gap=40):
    if not lines:
        return []
    lines.sort(key=lambda x: x["top"])
    merged = [lines[0]]
    for line in lines[1:]:
        last = merged[-1]
        if (
            abs(line["top"] - last["top"]) <= y_gap or abs(line["top"] - (last["top"] + last["height"])) <= y_gap
        ) and (
            line["font_size"] == last["font_size"] and
            line["style"] == last["style"] and
            line["font_family"] == last["font_family"] and
            line["font_size"] >= 15
        ):
            merged[-1]["text"] += " " + line["text"]
        else:
            merged.append(line)
    return merged

def deduplicate_and_simplify(text):
    return re.sub(r'(\w)\1+', r'\1', text).strip()

def ocr_extract_headings(img, page_num):
    ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    words = []
    for i in range(len(ocr_data['text'])):
        text = ocr_data['text'][i].strip()
        if text:
            x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
            words.append({
                'text': text,
                'left': x,
                'top': y,
                'right': x + w,
                'bottom': y + h,
                'height': h,
                'font_size': h
            })

    def group_by_line(words, y_thresh=200, font_size_thresh=7):
        words.sort(key=lambda w: (w['top'], w['left']))
        lines, current = [], []
        for word in words:
            if not current:
                current.append(word)
            else:
                last = current[-1]
                same_line = abs(word['top'] - last['top']) <= y_thresh
                font_size_close = abs(word['font_size'] - last['font_size']) < font_size_thresh
                if same_line and font_size_close:
                    current.append(word)
                else:
                    lines.append(current)
                    current = [word]
        if current:
            lines.append(current)
        return lines

    lines = group_by_line(words)
    headings = []
    for line in lines:
        line_text = " ".join(w['text'] for w in sorted(line, key=lambda w: w['left']))
        avg_font = round(sum(w['font_size'] for w in line) / len(line), 1)
        headings.append({
            'text': deduplicate_and_simplify(line_text),
            'font_size': avg_font,
            'style': 'ocr',
            'font_family': 'OCR',
            'top': min(w['top'] for w in line),
            'height': max(w['height'] for w in line),
            'page': page_num
        })
    return headings

def extract_headings(pdf_path, poppler_path=poppler_path):
    result = {"title": "", "outline": []}
    all_headings, page_heading_map = [], {}
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        if poppler_path:
            images = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)
        else:
            images = convert_from_path(pdf_path, dpi=300)
        for page_num, page in enumerate(pdf.pages, start=1):
            line_map = defaultdict(list)
            has_text = bool(page.chars)
            chars_count = len(page.chars) if page.chars else 0
            if not has_text or chars_count < 10:
                try:
                    ocr_headings = ocr_extract_headings(images[page_num-1], page_num)
                    page_heading_map[page_num] = ocr_headings
                    all_headings.extend(ocr_headings)
                except Exception as e:
                    print(f"Page {page_num}: OCR failed - {e}")
                    page_heading_map[page_num] = []
                continue
            for char in page.chars:
                text = char.get("text", "").strip()
                if not text:
                    continue
                font_size = round(char.get("size", 2), 2)
                font_name = char.get("fontname", "")
                font_family = extract_font_family(font_name)
                weight = "bold" if is_bold(font_name) else "regular"
                top = round(char["top"], 1)
                height = round(char["height"], 1)
                x0, x1 = char["x0"], char["x1"]
                line_map[top].append({
                    "x0": x0, "x1": x1, "text": text,
                    "weight": weight, "font_size": font_size,
                    "font_family": font_family, "top": top, "height": height
                })
            headings = []
            for line_chars in line_map.values():
                if not line_chars:
                    continue
                segments = split_on_large_gaps(line_chars)
                for segment in segments:
                    segment.sort(key=lambda c: c["x0"])
                    reconstructed_text = reconstruct_text(segment)
                    cleaned_text = clean_line_text(reconstructed_text)
                    if not cleaned_text or len(cleaned_text.split()) > 12:
                        continue
                    weights = {c["weight"] for c in segment}
                    families = {c["font_family"] for c in segment}
                    avg_size = round(sum(c["font_size"] for c in segment) / len(segment), 2)
                    top, height = segment[0]["top"], segment[0]["height"]
                    if len(weights) == 1:
                        style = weights.pop()
                        font_family = families.pop() if len(families) == 1 else "Mixed"
                        if font_family.lower() == "arial" and avg_size > 9:
                            headings.append({
                                "text": cleaned_text, "font_size": avg_size,
                                "style": style, "font_family": font_family,
                                "top": top, "height": height, "page": page_num
                            })
                        elif (style == "bold" and avg_size >= 11.5) or (style == "regular" and avg_size > 12.5):
                            headings.append({
                                "text": cleaned_text, "font_size": avg_size,
                                "style": style, "font_family": font_family,
                                "top": top, "height": height, "page": page_num
                            })
            all_headings.extend(headings)
            page_heading_map[page_num] = headings

    regular_headings = [h for h in all_headings if h["style"] == "regular" and h["font_size"] <= 15]
    if len(regular_headings) > len(page_heading_map) + 10:
        for page in page_heading_map:
            page_heading_map[page] = [h for h in page_heading_map[page]
                                      if h["style"] != "regular" or h["font_size"] > 15]

    first_page_lines = page_heading_map.get(1, [])
    if first_page_lines:
        max_font_size = max(h["font_size"] for h in first_page_lines)
        largest_lines = [h for h in first_page_lines if h["font_size"] == max_font_size]
        merged_title = None
        if 2 <= len(largest_lines) <= 3:
            largest_lines_sorted = sorted(largest_lines, key=lambda x: x["top"])
            all_bold = all(h["style"] == "bold" for h in largest_lines_sorted)
            consecutive = all(
                abs(largest_lines_sorted[i+1]["top"] - (largest_lines_sorted[i]["top"] + largest_lines_sorted[i]["height"])) < 40
                for i in range(len(largest_lines_sorted)-1)
            )
            if all_bold and consecutive:
                merged_title = " ".join(deduplicate_and_simplify(h["text"]) for h in largest_lines_sorted)
        if merged_title:
            result["title"] = merged_title
            page_heading_map[1] = [h for h in first_page_lines if h not in largest_lines]
        else:
            top_font = max(first_page_lines, key=lambda x: x["font_size"])
            result["title"] = deduplicate_and_simplify(top_font["text"])
            page_heading_map[1] = [h for h in first_page_lines if h != top_font]

    for page_num in sorted(page_heading_map.keys()):
        lines = merge_similar_headings(page_heading_map[page_num])
        for i, line in enumerate(lines):
            if page_num == 1 and i == 0:
                continue
            level = "H1" if line["font_size"] >= 18 else "H2" if line["font_size"] >= 14 else "H3"
            result["outline"].append({
                "level": level,
                "text": deduplicate_and_simplify(line["text"]),
                "page": page_num
            })
    return result

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


