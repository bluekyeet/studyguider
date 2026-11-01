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
