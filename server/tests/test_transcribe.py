"""Recording transcripts: which files count as recordings, how timestamps read, and how speech is grouped into five-minute pages.
The speech model itself is not run here (see the end-to-end check in the change notes)."""
import transcribe


def test_recordings_are_recognised_by_their_extension():
    assert all(transcribe.is_media(name) for name in ("talk.mp3", "Lecture.MP4", "memo.m4a", "a.wav"))
    assert not any(transcribe.is_media(name) for name in ("notes.pdf", "clip.mov", "song.mp3.txt"))


def test_clock_shows_hours_only_when_needed():
    assert [transcribe.clock(s) for s in (0, 65, 599, 3600, 3725)] == ["0:00", "1:05", "9:59", "1:00:00", "1:02:05"]


def test_speech_is_grouped_into_five_minute_pages_with_timestamps():
    segments = [(2, 5, " Welcome to   the lesson. "), (290, 296, "Enthalpy is heat."), (301, 310, "Bond energies next."), (930, 940, " "), (935, 941, "Last point.")]
    pages = transcribe.pages_from(segments)
    assert [number for number, _ in pages] == [1, 2, 3]                       # empty windows are skipped, pages stay consecutive
    assert pages[0][1] == "Recording 0:00 to 5:00\n\n[0:02] Welcome to the lesson.\n[4:50] Enthalpy is heat."
    assert pages[1][1].startswith("Recording 5:00 to 10:00\n\n[5:01] Bond energies next.")
    assert pages[2][1] == "Recording 15:00 to 20:00\n\n[15:35] Last point."  # blank speech is dropped
    assert transcribe.pages_from([]) == []


def test_hint_names_the_course_and_common_units():
    assert transcribe.hint("Chemistry", "Enthalpy").startswith("NCEA Chemistry Enthalpy lesson.")
    assert "kilojoules per mole" in transcribe.hint()
