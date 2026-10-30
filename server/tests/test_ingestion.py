import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import TextHTMLParser, extract_xlsx


def workbook(path, sheet_xml):
    with ZipFile(path, "w") as archive:
        archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Biology" r:id="r1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def test_html_ignores_active_content():
    parser = TextHTMLParser()
    parser.feed('<h1>Plants &amp; cells</h1><script>bad()</script><style>bad</style><p>Leaves</p>')
    assert "Plants & cells" in "".join(parser.parts)
    assert "Leaves" in "".join(parser.parts)
    assert "bad" not in "".join(parser.parts)


def test_xlsx_preserves_sheet_and_cell_reference(tmp_path):
    path = tmp_path / "book.xlsx"
    workbook(path, '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="inlineStr"><is><t>Cells</t></is></c><c r="B1"><f>1+1</f><v>2</v></c></row></sheetData></worksheet>')
    assert extract_xlsx(path) == [(1, "Sheet: Biology\nA1: Cells\nB1: [formula; cached value] 2")]


def test_xlsx_rejects_oversized_archive(tmp_path):
    path = tmp_path / "large.xlsx"
    with ZipFile(path, "w") as archive:
        for i in range(2001):
            archive.writestr(str(i), "")
    with pytest.raises(HTTPException, match="archive extraction limits"):
        extract_xlsx(path)
