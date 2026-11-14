import variants

ORIGINAL = "A 2.0 kg trolley moving at 3.0 m/s hits a stationary 1.0 kg trolley and they stick together. Calculate their speed."


def test_a_version_must_change_the_numbers():
    assert variants.acceptable(ORIGINAL, {"question": ORIGINAL.replace("2.0", "4.0").replace("3.0", "1.5"), "expected_answer": "v = 4.0 x 1.5 / 5.0 = 1.2 m/s"})
    # Same numbers in a new order of words: the answer could be remembered.
    same = "A stationary 1.0 kg trolley is hit by a 2.0 kg trolley moving at 3.0 m/s and they stick together. Calculate their speed."
    assert not variants.acceptable(ORIGINAL, {"question": same, "expected_answer": "2.0 m/s"})
    assert not variants.acceptable(ORIGINAL, {"question": ORIGINAL, "expected_answer": "2.0 m/s"})


def test_a_version_must_be_a_whole_problem():
    assert not variants.acceptable(ORIGINAL, {"question": "Find v.", "expected_answer": "2"})
    assert not variants.acceptable(ORIGINAL, {"question": "A 5 kg trolley at $3 m/s hits a 1 kg trolley and sticks. Find the speed.", "expected_answer": "2.5 m/s"})
    assert not variants.acceptable(ORIGINAL, None)
    assert not variants.acceptable(ORIGINAL, {"question": ORIGINAL.replace("2.0", "6.0")})
