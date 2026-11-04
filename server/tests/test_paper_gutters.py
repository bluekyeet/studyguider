import fitz

from paper_parser import page_lines


def test_outer_gutter_fragments_are_not_question_text():
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((4, 100), 'WR', fontsize=5)
        page.insert_text((560, 120), 'EA', fontsize=5)
        page.insert_text((42.5, 80), 'QUESTION ONE: SYNTHETIC', fontsize=11)
        page.insert_text((42.5, 110), '(a) Define a real image.', fontsize=11)
        text = '\n'.join(line['text'] for line in page_lines(page))
        assert 'QUESTION ONE: SYNTHETIC' in text
        assert '(a) Define a real image.' in text
        assert 'WR' not in text and 'EA' not in text


def _page_with_table(rows):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 90), '(a) Use the table below.', fontsize=11)
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            box = fitz.Rect(100 + c * 120, 120 + r * 24, 220 + c * 120, 144 + r * 24)
            page.draw_rect(box, width=1)
            page.insert_text((box.x0 + 6, box.y0 + 16), cell, fontsize=10)
    page.insert_text((297, 25), '5', fontsize=9)
    return doc, page


def test_a_table_of_numbers_is_kept_as_a_markdown_table_and_a_page_number_is_not():
    doc, page = _page_with_table([['Bond', 'Energy'], ['C-C', '348'], ['C-H', '413']])
    with doc:
        texts = [line['text'] for line in page_lines(page)]
    assert texts == ['(a) Use the table below.', '| Bond | Energy |\n| --- | --- |\n| C-C | 348 |\n| C-H | 413 |']
