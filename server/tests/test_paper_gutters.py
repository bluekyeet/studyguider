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
