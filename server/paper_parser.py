"""Deterministic NZQA PDF pairing and question segmentation. No model rewriting.

Run: python paper_parser.py DIRECTORY --output PRIVATE_DIRECTORY
Outputs contain copyrighted source excerpts; keep them outside the repository.
"""
import argparse
import json
import re
from pathlib import Path

import fitz

FILENAME = re.compile(r"^(\d{5})-(exm|ass)-(\d{2}|\d{4})\.pdf$", re.I)
HEADING = re.compile(r"^QUESTION\s+(ONE|TWO|THREE|FOUR|FIVE)\b")
NUMBERS = {"ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE": "5"}
LABEL = re.compile(r"^\s*\(([a-h]|[ivx]{1,4})\)(?:\s+|$)")


def cut_scores(text):
    heading = re.search(r"\bCut\s+Scores\b", text, re.I)
    if not heading:
        return None
    tail = text[heading.start():heading.start() + 1200]
    names = ("Not Achieved", "Achievement", "Achievement with Merit", "Achievement with Excellence")
    if not all(name.lower() in tail.lower() for name in names):
        return None
    positions = [tail.lower().find(name.lower()) for name in names]
    if positions != sorted(positions):
        return None
    ranges = [(int(a), int(b)) for a, b in re.findall(r"\b(\d{1,3})\s*[–−-]\s*(\d{1,3})\b", tail)]
    if len(ranges) != 4 or ranges[0][0] != 0 or any(a > b for a, b in ranges) or any(ranges[i][1] + 1 != ranges[i+1][0] for i in range(3)):
        return None
    return {"achieved": ranges[1][0], "merit": ranges[2][0], "excellence": ranges[3][0], "total": ranges[3][1], "quote": tail.strip()}


def file_identity(name):
    match = FILENAME.fullmatch(name)
    if not match:
        return None
    standard, kind, year = match.groups()
    year = int(year)
    return int(standard), (2000 + year if year < 100 else year), kind.lower()


def pair_files(directory):
    pairs = {}
    ignored = []
    for path in sorted(Path(directory).iterdir()):
        identity = file_identity(path.name)
        if identity is None:
            ignored.append(path.name)
            continue
        standard, year, kind = identity
        pairs.setdefault((standard, year), {})[kind] = path
    return pairs, ignored


def page_lines(page, ocr=False):
    """Keep physical lines and coordinates; exclude running headers and footer."""
    result = []
    textpage = None
    if ocr and not page.get_text().strip():
        textpage = page.get_textpage_ocr(language="eng", dpi=180, full=True)
    for block in page.get_text("dict", sort=True, textpage=textpage)["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            box = line["bbox"]
            if not text or box[1] < 30 or box[3] > page.rect.height - 28:
                continue
            if text in {"USE ONLY", "ASSESSOR'S", "ASSESSOR’S", "DO NOT WRITE IN THIS AREA"}:
                continue
            if re.fullmatch(r"\d+", text) or re.match(r"(?:Chemistry|Physics|Mathematics) 9\d{4}", text):
                continue
            result.append({"text": text, "bbox": list(box)})
    return result


def split_parts(lines):
    parts = []
    parent = ""
    for line in lines:
        match = LABEL.match(line["text"])
        if match:
            label = match[1]
            if label in "abcdefgh" and len(label) == 1:
                parent = label
                key = label
            else:
                key = f"{parent}({label})" if parent else label
            parts.append({"label": key, "lines": []})
        if not parts:
            parts.append({"label": "context", "lines": []})
        parts[-1]["lines"].append(line)
    return parts


def segment_paper(document, ocr=False):
    questions = []
    current = None
    for index, page in enumerate(document):
        lines = page_lines(page, ocr=ocr)
        for line in lines:
            match = HEADING.match(line["text"])
            if match:
                number = NUMBERS[match[1]]
                if current is None or current["question_number"] != number:
                    current = {"question_number": number, "paper_page": index + 1, "lines": [], "pages": []}
                    questions.append(current)
            if current is not None:
                # Printed additional-answer pages are not question continuations.
                if line["text"] == "QUESTION" or "Extra paper if required" in line["text"]:
                    current = None
                    continue
                current["lines"].append({**line, "page": index + 1})
                if index + 1 not in current["pages"]:
                    current["pages"].append(index + 1)
    for question in questions:
        question["parts"] = split_parts(question["lines"])
        question["question_text"] = "\n".join(line["text"] for line in question["lines"])
    return questions


def schedule_sections(document):
    sections = {}
    current = None
    for index, page in enumerate(document):
        for line in page_lines(page):
            text = line["text"]
            # A schedule heading is an isolated number word, optionally followed by a part.
            match = re.fullmatch(r"(ONE|TWO|THREE|FOUR|FIVE)(?:\s*\([a-hivx]+\))*", text, re.I)
            if match:
                current = NUMBERS[match[1].upper()]
                sections.setdefault(current, {"pages": [], "lines": []})
            if current:
                sections[current]["lines"].append({**line, "page": index + 1})
                if index + 1 not in sections[current]["pages"]:
                    sections[current]["pages"].append(index + 1)
    return sections


def parse_pair(paper_path, schedule_path, ocr=False, filenames=None):
    identity = file_identity(filenames[0] if filenames else Path(paper_path).name)
    other = file_identity(filenames[1] if filenames else Path(schedule_path).name)
    if not identity or not other or identity[:2] != other[:2] or identity[2] != "exm" or other[2] != "ass":
        raise ValueError("Paper and schedule filenames must match standard/year and exm/ass roles")
    with fitz.open(paper_path) as paper, fitz.open(schedule_path) as schedule:
        questions = segment_paper(paper, ocr=ocr)
        schedules = schedule_sections(schedule)
        warnings = []
        if any(not page.get_text().strip() for page in paper) and not ocr:
            warnings.append("Image-only pages need OCR; rerun with --ocr")
        numbers = [q['question_number'] for q in questions]
        if not 3 <= len(questions) <= 5 or numbers != [str(n) for n in range(1, len(questions) + 1)]:
            warnings.append(f"Missing or inconsistent whole question groups; found {numbers}")
        for q in questions:
            section = schedules.get(q["question_number"])
            q["schedule_text"] = "\n".join(line["text"] for line in section["lines"]) if section else ""
            q["schedule_pages"] = section["pages"] if section else []
            q["schedule_page"] = section["pages"][0] if section else None
            if not section:
                warnings.append(f"Question {q['question_number']}: schedule heading not identified; not safe to import")
            q["diagram_regions"] = []
            for number in q["pages"]:
                page = paper[number - 1]
                regions = [fitz.Rect(image["bbox"]) for image in page.get_image_info()] + list(page.cluster_drawings())
                for region in regions:
                    if region.width > 45 and region.height > 35 and region.get_area() < page.rect.get_area() * .7:
                        box = [max(0, region.x0 - 8), max(0, region.y0 - 8), min(page.rect.width, region.x1 + 8), min(page.rect.height, region.y1 + 8)]
                        q["diagram_regions"].append({"page": number, "bbox": box, "association": "geometric reading order; labels need checking"})
            for part in q['parts']:
                part['text'] = '\n'.join(line['text'] for line in part['lines'])
                part['diagrams'] = []
            for diagram in q['diagram_regions']:
                # Anchor by physical reading position, not a model's guess about diagram meaning.
                candidates = [(index, line) for index, part in enumerate(q['parts']) for line in part['lines']
                              if line['page'] == diagram['page'] and line['bbox'][1] <= diagram['bbox'][1]]
                if candidates:
                    owner = max(candidates, key=lambda pair: pair[1]['bbox'][1])[0]
                    q['parts'][owner]['diagrams'].append(diagram)
            for part in q['parts']:
                prose = []
                for line in part['lines']:
                    box = fitz.Rect(line['bbox'])
                    inside = any(line['page'] == d['page'] and (box & fitz.Rect(d['bbox'])).get_area() >= box.get_area() * .8
                                 for d in q['diagram_regions'])
                    if not inside:
                        prose.append(line['text'])
                part['text'] = '\n'.join(prose)
        return {"standard_number": identity[0], "year": identity[1], "parser": "pdf-layout", "human_verified": False,
                "warnings": warnings, "questions": questions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ocr", action="store_true", help="Recognise image-only paper pages using installed Tesseract")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    pairs, ignored = pair_files(args.directory)
    for (standard, year), files in sorted(pairs.items()):
        if not {"exm", "ass"} <= files.keys():
            print(f"{standard} {year}: missing paper or schedule")
            continue
        result = parse_pair(files["exm"], files["ass"], ocr=args.ocr)
        (args.output / f"{standard}-{year}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{standard} {year}: {len(result['questions'])} groups; {len(result['warnings'])} warnings")
    print(f"Ignored {len(ignored)} unrelated files")


if __name__ == "__main__":
    main()
