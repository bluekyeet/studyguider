import fitz

from paper_parser import file_identity, parse_pair, split_parts, cut_scores


def test_cut_scores_requires_complete_contiguous_ranges():
    heading = "Cut Scores\nNot Achieved  Achievement  Achievement with Merit  Achievement with Excellence\n"
    scores = cut_scores(heading + "0 – 07  08–13  14 – 18  19 – 24")
    assert scores['achieved'] == 8
    assert scores['merit'] == 14
    assert scores['excellence'] == 19
    assert scores['total'] == 24
    assert cut_scores(heading + "0–7 9–13 14–18 19–24") is None
    assert cut_scores(heading + "0–7 8–13 14–18") is None
    assert cut_scores("0–7 8–13 14–18 19–24") is None


def test_filename_and_parts():
    assert file_identity("90308-exm-05.pdf") == (90308, 2005, "exm")
    assert file_identity("91164-ass-2024.pdf") == (91164, 2024, "ass")
    assert file_identity("90308-rep-04.pdf") is None
    parts = split_parts([{"text": t} for t in ("Context", "(a) Describe", "(b)", "(i) Calculate", "(ii) Explain")])
    assert [p["label"] for p in parts] == ["context", "a", "b", "b(i)", "b(ii)"]


def test_question_continuations_and_schedule_pairing(tmp_path):
    for kind in ("exm", "ass"):
        doc = fitz.open()
        for heading in ("ONE", "TWO", "THREE"):
            page = doc.new_page()
            page.insert_text((50, 80), ("QUESTION " if kind == "exm" else "") + heading)
            page.insert_text((50, 110), "(a) Assistant-written sample explanation.")
            if kind == "exm":
                page = doc.new_page()
                page.insert_text((50, 80), "(b) Assistant-written continuation.")
        doc.save(tmp_path / f"91164-{kind}-2024.pdf")
        doc.close()
    result = parse_pair(tmp_path / "91164-exm-2024.pdf", tmp_path / "91164-ass-2024.pdf")
    assert not result["warnings"]
    assert len(result["questions"]) == 3
    assert result["questions"][0]["pages"] == [1, 2]
    assert result["questions"][1]["schedule_page"] == 2


def _paper(path, pages):
    doc = fitz.open()
    for lines in pages:
        page = doc.new_page()
        for y, (x, text) in enumerate(lines):
            page.insert_text((x, 80 + 24 * y), text)
    doc.save(path)
    doc.close()


def test_schedule_headings_beside_the_answer_or_as_q1_are_found(tmp_path):
    from paper_parser import schedule_heading
    width = 595
    assert schedule_heading("ONE", 50, width, None) == "1"
    assert schedule_heading("Q1   Expected coverage   Achievement   Merit", 48, width, None) == "1"
    assert schedule_heading("ONE     Se: [Ar]3d104s24p4", 59, width, None) == "1"
    assert schedule_heading("TWO (a)", 50, width, "1") == "2"
    # A criterion in a right-hand column, a sentence, an out-of-order number and a count are not headings.
    assert schedule_heading("TWO correct from (a).", 400, width, "1") is None
    assert schedule_heading("ONE answer", 50, width, "1") is None
    assert schedule_heading("THREE", 50, width, "1") is None
    assert schedule_heading("TWO", 50, width, None) is None
    _paper(tmp_path / "91578-exm-2019.pdf", [[(50, "QUESTION ONE"), (50, "(a) Differentiate y = x2.")],
                                              [(50, "QUESTION TWO"), (50, "(a) Integrate.")],
                                              [(50, "QUESTION THREE"), (50, "(a) Solve.")]])
    _paper(tmp_path / "91578-ass-2019.pdf", [[(48, "Q1   Expected coverage   Achievement"), (100, "2x")],
                                              [(48, "Q2   Expected coverage   Achievement"), (100, "x3/3 + c"), (104, "ONE answer correct")],
                                              [(48, "Q3   Expected coverage   Achievement"), (100, "x = 2")]])
    result = parse_pair(tmp_path / "91578-exm-2019.pdf", tmp_path / "91578-ass-2019.pdf")
    assert not result["warnings"]
    assert [q["schedule_page"] for q in result["questions"]] == [1, 2, 3]


def test_a_spare_grid_at_the_back_is_not_another_question(tmp_path):
    _paper(tmp_path / "91262-exm-2019.pdf", [[(50, "QUESTION ONE"), (50, "(a) Sketch y = f(x).")],
                                              [(50, "QUESTION TWO"), (50, "(a) Sketch the gradient function.")],
                                              [(50, "QUESTION THREE"), (50, "(a) Find the speed.")],
                                              [(50, "SPARE GRIDS"), (50, "QUESTION TWO"), (50, "(a) Sketch the gradient function.")]])
    _paper(tmp_path / "91262-ass-2019.pdf", [[(50, "ONE")], [(50, "TWO")], [(50, "THREE")]])
    result = parse_pair(tmp_path / "91262-exm-2019.pdf", tmp_path / "91262-ass-2019.pdf")
    assert [q["question_number"] for q in result["questions"]] == ["1", "2", "3"]
    assert result["questions"][1]["pages"] == [2]


def test_table_cells_join_subscripts_and_states_onto_their_formula():
    from paper_parser import _cell_text, _symbols
    assert _cell_text("Ammonia, NH\n3\n(ℓ)") == "Ammonia, NH3(ℓ)"
    assert _cell_text("Methanamine,\nCH NH (l)") == "Methanamine, CH NH (l)"
    assert _cell_text("Fe\n3+") == "Fe3+"
    assert _symbols("F S F") and _symbols("H") and not _symbols("3") and not _symbols("Boiling point")
