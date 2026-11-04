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


def page_tables(page):
    """[(bbox, markdown)] for the ruled tables of plain text on a page (a table of bond energies, a data table). A table whose
    cells hold several lines is a drawing of molecules or labels, not data, and is left to the figure handling."""
    found = []
    try:
        tables = page.find_tables().tables
    except Exception:
        return found
    for table in tables:
        rows = [[(cell or "").strip() for cell in row] for row in table.extract()]
        flat = [cell for row in rows for cell in row]
        if len(rows) < 2 or len(rows[0]) < 2 or any("\n" in cell for cell in flat):
            continue
        if not all(rows[0]) or sum(1 for cell in flat if cell) < len(flat) * .4:
            continue
        line = lambda row: "| " + " | ".join(cell.replace("|", "\\|") for cell in row) + " |"
        found.append((list(table.bbox), "\n".join([line(rows[0]), line(["---"] * len(rows[0]))] + [line(row) for row in rows[1:]])))
    return found


ELEMENT = re.compile(r"(?:H|He|Li|Be|B|C|N|O|F|Ne|Na|Mg|Al|Si|P|S|Cl|Ar|K|Ca|Br|I|Xe|Fe|Cu|Zn|Pd|Ag|Sn|Pb)\d*[+\-–]?")


def structure_regions(page):
    """Boxes around Lewis and structural formulae drawn as atom symbols joined by bond lines ("H   S   H", "O   C   O").
    Their symbols are text but the structure is a picture, so they are shown as a figure instead of running into the sentence.
    Atom symbols that sit close together form one structure; the bond lines drawn around them are included."""
    atoms = []
    for line in page_lines(page):
        tokens = line["text"].split()
        if tokens and all(ELEMENT.fullmatch(token) for token in tokens):
            atoms.append(fitz.Rect(line["bbox"]))
    groups = []
    for box in atoms:
        near = [g for g in groups if any(abs(box.x0 - o.x1) < 30 and abs(box.y0 - o.y1) < 28 or (box + (-30, -28, 30, 28)).intersects(o) for o in g)]
        merged = [box] + [o for g in near for o in g]
        groups = [g for g in groups if g not in near] + [merged]
    width, height = page.rect.width, page.rect.height
    bonds = [d["rect"] + (-1, -1, 1, 1) for d in page.get_drawings()
             if d["rect"].x1 >= width * .1 and d["rect"].x0 <= width * .9 and d["rect"].width < width * .5 and d["rect"].height < height * .3
             and not (d.get("type") == "f" and len(d.get("items", ())) >= 20)]
    regions = []
    for group in groups:
        if len(group) < 2 and len(page.get_text("text", clip=group[0]).split()) < 2:
            continue    # a lone symbol is more likely a word than a structure
        box = fitz.Rect(group[0])
        for other in group[1:]:
            box |= other
        for bond in bonds:
            if (box + (-20, -20, 20, 20)).intersects(bond):
                box |= bond
        regions.append(box)
    return regions


def page_lines(page, ocr=False):
    """Keep physical lines and coordinates; exclude running headers and footer. Ruled tables of plain text become one
    Markdown table in the line where they start."""
    result = []
    textpage = None
    if ocr and not page.get_text().strip():
        textpage = page.get_textpage_ocr(language="eng", dpi=180, full=True)
    for block in page.get_text("dict", sort=True, textpage=textpage)["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            box = line["bbox"]
            # NZQA's patterned no-writing gutters contain hundreds of tiny text
            # fragments, not one removable phrase. Exclude only outer-gutter lines;
            # retain question labels/body beginning just inside the content edge.
            if box[2] <= 40 or box[0] >= page.rect.width - 40:
                continue
            if not text or box[1] < 30 or box[3] > page.rect.height - 28:
                continue
            if re.fullmatch(r"[#$%&*!?@^~+=<>\/|_.,;:'\"-]{3,}", text):
                continue    # the printed symbol pattern of the no-writing area ("#$%&*!!?") is not question text
            if text in {"USE ONLY", "ASSESSOR'S", "ASSESSOR’S", "DO NOT WRITE IN THIS AREA"}:
                continue
            # A printed page number sits in the top or bottom margin; a number inside a table is data.
            if (re.fullmatch(r"\d+", text) and (box[1] < 50 or box[3] > page.rect.height - 50)) or re.match(r"(?:Chemistry|Physics|Mathematics) 9\d{4}", text):
                continue
            result.append({"text": text, "bbox": list(box)})
    for bbox, markdown in page_tables(page):
        area = fitz.Rect(bbox)
        inside = [i for i, line in enumerate(result) if (fitz.Rect(line["bbox"]) & area).get_area() >= fitz.Rect(line["bbox"]).get_area() * .8]
        if inside:
            first = inside[0]
            result[first] = {"text": markdown, "bbox": bbox}
            result = [line for i, line in enumerate(result) if i not in inside[1:]]
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


ANSWER_AREA = re.compile(r"continues\s+on\s+the\s+next\s+page|extra\s+space|if\s+you\s+need\s+to\s+redraw|write\s+your\s+answer", re.I)


def drawing_regions(page):
    """Boxes around the vector drawings on a page (graphs, diagrams), without the page's own furniture.

    NCEA papers print a decorative pattern along one edge and ruled answer lines across the page. Clustering them with
    the real drawings joins everything into one page-sized box, which the size filter then discards, so a graph drawn as
    vectors was never found. Leave out thin full-width lines and anything inside the outer tenth of the page's width."""
    width, height = page.rect.width, page.rect.height
    kept = []
    for drawing in page.get_drawings():
        box = drawing["rect"]
        if box.height <= 1.5 and box.width > width * 0.7:
            continue
        if box.x1 < width * 0.1 or box.x0 > width * 0.9:
            continue
        if box.width > width * 0.9 and box.height > height * 0.9:
            continue
        if drawing.get("type") == "f" and len(drawing.get("items", ())) >= 20:
            continue    # the decorative edge pattern is made of large many-segment filled shapes that cross into the page
        kept.append(drawing)
    regions = []
    for region in page.cluster_drawings(drawings=kept, x_tolerance=20, y_tolerance=20):
        inside = [d for d in kept if region.contains(d["rect"]) or d["rect"].intersects(region)]
        if inside and all(d["rect"].height <= 1.5 for d in inside):
            continue    # only ruled answer lines
        if ANSWER_AREA.search(page.get_text("text", clip=region)):
            continue    # the answer area with its "Question Three continues on the next page" box
        regions.append(region)
    return regions


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
                tables = [fitz.Rect(bbox) + (-10, -10, 10, 10) for bbox, _ in page_tables(page)]
                regions = [fitz.Rect(image["bbox"]) for image in page.get_image_info()] + drawing_regions(page)
                # The ruling of a table that was read as a table is not a figure.
                regions = [r for r in regions if not any((r & t).get_area() >= r.get_area() * .6 for t in tables)]
                structures = [r for r in structure_regions(page) if not any((r & d).get_area() >= r.get_area() * .5 for d in regions)]
                for region in regions + structures:
                    if region in structures or (region.width > 45 and region.height > 35) and region.get_area() < page.rect.get_area() * .7:
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
