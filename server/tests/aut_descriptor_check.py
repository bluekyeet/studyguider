"""Live check of the AUT descriptor import against real course codes (needs internet; not part of the unit suite).

Run with the current source mounted: python - < server/tests/aut_descriptor_check.py
Each paper must give a title, 15 points, numbered learning outcomes and an assessment plan whose weights add to 100%.
"""
import curriculum

CODES = ("COMP500", "COMP501", "COMP503", "ENGE501", "CHEM501", "PHYS501", "GESC600", "MATH502")

for code in CODES:
    url, data = curriculum.fetch_aut_descriptor(code)
    draft = curriculum.parse_aut_descriptor(data)
    weights = sum(a["weight_pct"] for a in draft["assessments"])
    assert draft["code"] == code and draft["title"] and draft["points"] == 15.0, (code, draft["code"], draft["title"], draft["points"])
    assert len(draft["outcomes"]) >= 3 and all(o["title"] for o in draft["outcomes"]), (code, draft["outcomes"])
    assert abs(weights - 100) < 0.01, (code, weights)
    codes = {o["code"] for o in draft["outcomes"]}
    assert all(set(a["outcome_codes"]) <= codes for a in draft["assessments"]), (code, draft["assessments"])
    print("PASS", code, draft["title"], f"{len(draft['outcomes'])} outcomes,",
          ", ".join(f"{a['title']} {a['weight_pct']:g}%" for a in draft["assessments"]))
try:
    curriculum.fetch_aut_descriptor("MATH604")
    raise AssertionError("MATH604 has no descriptor and should be refused")
except curriculum.HTTPException as error:
    assert error.status_code == 404
    print("PASS a code with no descriptor is reported, not guessed")
