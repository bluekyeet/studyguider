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


def test_atom_symbols_of_a_structural_formula_become_a_figure_not_a_sentence():
    from paper_parser import structure_regions
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((100, 200), 'The Lewis structure is shown below.', fontsize=11)
        page.insert_text((200, 300), 'H   S   H', fontsize=11)
        page.draw_line((214, 297), (226, 297))
        page.draw_line((243, 297), (258, 297))
        page.insert_text((100, 400), 'Water is H2O and I think so.', fontsize=11)
        regions = structure_regions(page)
    assert len(regions) == 1 and regions[0].x0 <= 201 and regions[0].x1 >= 258 and regions[0].y0 < 300 < regions[0].y1


def test_the_printed_symbol_pattern_is_not_question_text():
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((60, 90), '#$%&*!!?', fontsize=11)
        page.insert_text((60, 120), 'Calculate the force.', fontsize=11)
        assert [line['text'] for line in page_lines(page)] == ['Calculate the force.']
