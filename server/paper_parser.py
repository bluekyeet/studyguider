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


_SUBSCRIPT = re.compile(r"\d{1,2}[+\-–]?|[+\-–]|\((?:s|l|ℓ|g|aq)\)")


def _symbols(line):
    """True for a line made only of atom symbols ("F", "F S F"), as in a structure drawn inside a table cell."""
    tokens = line.split()
    return bool(tokens) and len(line.strip()) < 12 and all(ELEMENT.fullmatch(token) and not token[0].isdigit() for token in tokens)


def _cell_text(cell):
    """One line of text for a table cell: wrapped lines joined with a space, a subscript, charge or state symbol that the PDF
    set on its own line joined straight onto what it belongs to ("NH" / "3" / "(l)" is NH3(l))."""
    text = ""
    for line in (part.strip() for part in cell.split("\n")):
        if not line:
            continue
        glue = bool(text) and (_SUBSCRIPT.fullmatch(line) or (text[-1].isdigit() and line[0] == "(" and len(line) <= 4))
        text += line if glue or not text else " " + line
    return " ".join(text.split())


def page_tables(page):
    """[(bbox, markdown)] for the ruled tables of plain text on a page (a table of bond energies, a data table, a table to fill in,
    whose empty cells stay empty). A table whose cells hold atom symbols on separate lines is a drawing of molecules, not data,
    and is left to the figure handling."""
    found = []
    try:
        tables = page.find_tables().tables
    except Exception:
        return found
    for table in tables:
        rows = [[(cell or "").strip() for cell in row] for row in table.extract()]
        flat = [cell for row in rows for cell in row]
        # The top-left cell may be blank when the rows have labels of their own ("| | SF4 | SF3- |" over "Lewis structure").
        if len(rows) < 2 or len(rows[0]) < 2 or not all(rows[0][1:]) or not (rows[0][0] or all(row[0] for row in rows[1:])):
            continue
        # Wrapped words ("Carbon monoxide," / "CO(s)") are one cell; a cell of lone atom symbols on separate lines is a drawn
        # structure. A subscript or charge the PDF sets on its own line ("NH" / "3" / "(l)") is neither.
        if any(_symbols(line) for cell in flat if "\n" in cell for line in cell.split("\n")):
            continue
        rows = [[_cell_text(cell) for cell in row] for row in rows]
        flat = [cell for row in rows for cell in row]
        # An answer grid: labels down the first column and empty cells for the learner to fill in.
        grid = all(row[0] for row in rows[1:]) and any(not cell for row in rows[1:] for cell in row[1:])
        if not grid and sum(1 for cell in flat if cell) < len(flat) * .4:
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


def page_lines(page, ocr=False, tables=True):
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
    for bbox, markdown in page_tables(page) if tables else ():
        area = fitz.Rect(bbox)
        inside = [i for i, line in enumerate(result) if (fitz.Rect(line["bbox"]) & area).get_area() >= fitz.Rect(line["bbox"]).get_area() * .8]
        if inside:
            first = inside[0]
            result[first] = {"text": markdown, "bbox": bbox}
            result = [line for i, line in enumerate(result) if i not in inside[1:]]
    return result


SPARE = re.compile(r"^\s*SPARE (?:GRIDS?|DIAGRAMS?|GRAPHS?|COPY|COPIES|AXES|TABLES?)\b", re.I)


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
    spare = False
    for index, page in enumerate(document):
        lines = page_lines(page, ocr=ocr)
        for line in lines:
            # Spare grids and diagrams at the back repeat a question's heading and figure for a second attempt; they are not
            # more of the paper, and nothing after them is either.
            if SPARE.search(line["text"]):
                spare, current = True, None
            if spare:
                continue
            match = HEADING.match(line["text"])
            if match:
                number = NUMBERS[match[1]]
                if any(q["question_number"] == number for q in questions) and (current is None or current["question_number"] != number):
                    current = None      # an earlier question's heading again: a spare copy without the "spare" title
                    continue
                if current is None or current["question_number"] != number:
                    current = {"question_number": number, "paper_page": index + 1, "lines": [], "pages": []}
                    questions.append(current)
            if current is not None:
                # Printed additional-answer pages are not question continuations.
                if line["text"] == "QUESTION" or re.search(r"Extra (?:paper|space) if required", line["text"]):
                    current = None
                    continue
                current["lines"].append({**line, "page": index + 1})
                if index + 1 not in current["pages"]:
                    current["pages"].append(index + 1)
    for question in questions:
        question["parts"] = split_parts(question["lines"])
        question["question_text"] = "\n".join(line["text"] for line in question["lines"])
    return questions


# Schedules head each question in the left column in one of three ways: the number word alone ("ONE", "TWO (a)"), the number
# word with the first answer beside it ("ONE   Se: [Ar]3d10..."), or "Q1" above the column titles ("Q1   Expected coverage").
SCHEDULE_HEADING = re.compile(r"(?:(ONE|TWO|THREE|FOUR|FIVE)|Q(?:UESTION)?\s*([1-5]))(?=\s|\(|$)(?:\s*\([a-hivx]+\))*(.*)", re.I)
DIGITS = {"1": "ONE", "2": "TWO", "3": "THREE", "4": "FOUR", "5": "FIVE"}


def schedule_heading(text, x0, page_width, current):
    """The question number a schedule line starts, or None. A heading sits at the left edge and numbers run in order, so
    "ONE correct answer" in a criteria column, or a stray "Q2" after Question Three, is not taken for one."""
    match = SCHEDULE_HEADING.match(text.strip())
    if not match or x0 > page_width * 0.2:
        return None
    word = (match[1] or DIGITS[match[2]]).upper()
    if match[1] and not match[1].isupper() and match[3].strip():
        return None             # "One ..." is a sentence; headings are capitals
    rest = match[3].strip()
    # Beside the word: nothing, a part label, column titles, or answer content set off by the column gap.
    if rest and match[2] is None and re.match(r"[a-z]|(?:OF|CORRECT|ANSWERS?|FROM|VALID|OR|AND)\b", rest):
        return None             # "ONE of the following", "TWO correct": a criterion, not a heading
    if rest and match[2] is not None and not re.match(r"(?:Expected|Evidence|Achievement|Question|\(|$)", rest, re.I):
        return None
    number = NUMBERS[word]
    if current is not None and int(number) not in (int(current), int(current) + 1):
        return None
    if current is None and number != "1":
        return None
    return number


def schedule_sections(document, ocr=False):
    sections = {}
    current = None
    for index, page in enumerate(document):
        # A schedule is one ruled table per question; read as plain lines so the heading in its first cell is still a line.
        for line in page_lines(page, ocr=ocr, tables=False):
            text = line["text"]
            number = schedule_heading(text, line["bbox"][0], page.rect.width, current)
            if number:
                current = number
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


def scan_regions(page, lines):
    """Boxes around the figures on a scanned page, which is one picture with no drawings to cluster. What is left of the
    page's ink after the prose (the OCR lines that read as sentences), the ruled answer lines and the margins are taken out
    is grouped into blocks; a block big enough to be a diagram is a figure, with its short labels ("Speaker 1", "5.00 m")."""
    try:
        import numpy
    except ImportError:
        return []
    scale = 100 / 72
    pix = page.get_pixmap(dpi=100, colorspace=fitz.csGRAY, alpha=False)
    ink = numpy.frombuffer(pix.samples, dtype=numpy.uint8).reshape(pix.height, pix.width) < 150
    ink = ink.copy()
    width, height = page.rect.width, page.rect.height
    px = lambda value: max(0, int(value * scale))
    ink[:px(40)] = False
    ink[px(height - 40):] = False
    ink[:, :px(40)] = False
    ink[:, px(width - 45):] = False
    for line in lines:
        text = line["text"]
        if len(text.split()) >= 4 or LABEL.match(text) or HEADING.match(text) or ANSWER_AREA.search(text):
            x0, y0, x1, y1 = line["bbox"]
            ink[px(y0 - 2):px(y1 + 2), px(x0 - 2):px(x1 + 2)] = False
    cell = px(6)
    rows, cols = pix.height // cell, pix.width // cell
    grid = ink[:rows * cell, :cols * cell].reshape(rows, cell, cols, cell).sum(axis=(1, 3)) > 1
    seen = numpy.zeros_like(grid)
    blocks = []
    for r0, c0 in zip(*numpy.nonzero(grid)):
        if seen[r0, c0]:
            continue
        stack, cells = [(r0, c0)], []
        seen[r0, c0] = True
        while stack:
            r, c = stack.pop()
            cells.append((r, c))
            # Cells up to three apart (about 18 points) belong together, so a diagram's separate parts are one figure.
            for rr in range(max(0, r - 3), min(rows, r + 4)):
                for cc in range(max(0, c - 3), min(cols, c + 4)):
                    if grid[rr, cc] and not seen[rr, cc]:
                        seen[rr, cc] = True
                        stack.append((rr, cc))
        top, left = min(r for r, _ in cells), min(c for _, c in cells)
        bottom, right = max(r for r, _ in cells) + 1, max(c for _, c in cells) + 1
        box = fitz.Rect(left * cell / scale, top * cell / scale, right * cell / scale, bottom * cell / scale)
        blocks.append((box, len(cells)))
    # A diagram, not a stray word or a stain: big enough, and inked over more than a sliver of its box.
    regions = [box for box, cells in blocks if box.width > 60 and box.height > 32 and cells >= 25]
    small = [box for box, _ in blocks if box not in regions]
    grown = True
    while grown:        # labels, dots and arrowheads that stand a little apart from a diagram are part of it
        grown = False
        for index, region in enumerate(regions):
            for box in [b for b in small if (region + (-30, -30, 30, 30)).intersects(b)]:
                region = regions[index] = region | box
                small.remove(box)
                grown = True
    merged = []
    for region in regions:
        other = next((i for i, m in enumerate(merged) if (m + (-30, -30, 30, 30)).intersects(region)), None)
        if other is not None:
            merged[other] = merged[other] | region
        else:
            merged.append(region)
    kept = []
    for region in merged:
        inside = ink[px(region.y0):px(region.y1), px(region.x0):px(region.x1)]
        # Ruled answer lines (pale on most scans, so usually not ink at all) are a few thin rows and nothing else.
        if region.get_area() < page.rect.get_area() * .7 and inside.size and (inside.sum(axis=1) > 0).mean() > .2:
            kept.append(region)
    return kept


def figure_boxes(page, lines=None, ocr=False):
    """[x0, y0, x1, y1] for each figure on a page: its pictures, vector drawings and drawn chemical structures, or on a
    scanned page the diagrams found in the page image. `lines` are the page's text lines when the caller already has them."""
    tables = [fitz.Rect(bbox) + (-10, -10, 10, 10) for bbox, _ in page_tables(page)]
    regions = [fitz.Rect(image["bbox"]) for image in page.get_image_info()] + drawing_regions(page)
    if ocr and not page.get_text().strip():
        regions = scan_regions(page, lines or page_lines(page, ocr=True))
    # The ruling of a table that was read as a table is not a figure.
    regions = [r for r in regions if not any((r & t).get_area() >= r.get_area() * .6 for t in tables)]
    structures = [r for r in structure_regions(page) if not any((r & d).get_area() >= r.get_area() * .5 for d in regions)]
    boxes = []
    for region in regions + structures:
        if region in structures or (region.width > 45 and region.height > 30) and region.get_area() < page.rect.get_area() * .7:
            boxes.append([max(0, region.x0 - 8), max(0, region.y0 - 8), min(page.rect.width, region.x1 + 8), min(page.rect.height, region.y1 + 8)])
    return boxes


def parse_pair(paper_path, schedule_path, ocr=False, filenames=None):
    identity = file_identity(filenames[0] if filenames else Path(paper_path).name)
    other = file_identity(filenames[1] if filenames else Path(schedule_path).name)
    if not identity or not other or identity[:2] != other[:2] or identity[2] != "exm" or other[2] != "ass":
        raise ValueError("Paper and schedule filenames must match standard/year and exm/ass roles")
    with fitz.open(paper_path) as paper, fitz.open(schedule_path) as schedule:
        questions = segment_paper(paper, ocr=ocr)
        schedules = schedule_sections(schedule, ocr=ocr)
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
                for box in figure_boxes(paper[number - 1], [line for line in q["lines"] if line["page"] == number], ocr):
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
