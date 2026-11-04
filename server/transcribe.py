"""Speech to text for uploaded recordings (mp3, mp4, m4a, wav), done on this server.

A recording becomes a resource like any document: its transcript is the resource's text, split into five-minute "pages" with
timestamps so lessons can cite where something was said. The original recording is deleted once the transcript is saved
(see app.extract_resource); only the transcript is kept.

Transcription uses faster-whisper on the CPU. The model is baked into the image at build time (WHISPER_MODEL, default "base");
WHISPER_LANGUAGE pins the spoken language (default English) and WHISPER_THREADS caps CPU use. One recording is transcribed at
a time, whichever account it belongs to.
"""
import os
import threading
from pathlib import Path

MEDIA_SUFFIXES = {".mp3", ".mp4", ".m4a", ".wav"}
MAX_MEDIA_BYTES = 500 * 1024 * 1024
MAX_SECONDS = 2 * 60 * 60          # the whole recording is decoded into memory first (about 230 MB per hour at 16 kHz)
PAGE_SECONDS = 5 * 60
MODEL_DIR = os.environ.get("WHISPER_MODEL_DIR", "/app/models")

_lock = threading.Lock()
_model = None


def is_media(filename):
    return Path(filename).suffix.lower() in MEDIA_SUFFIXES


def clock(seconds):
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}" if seconds >= 3600 else f"{seconds // 60}:{seconds % 60:02d}"


def duration(path):
    """Length in seconds read from the container header, without decoding the audio. None if it cannot be read."""
    import av
    try:
        with av.open(str(path)) as container:
            if container.duration:
                return container.duration / 1_000_000
            streams = [s for s in container.streams if s.type == "audio" and s.duration and s.time_base]
            return float(streams[0].duration * streams[0].time_base) if streams else None
    except av.error.FFmpegError as error:
        raise ValueError("The recording could not be read; it may be damaged or not really audio or video") from error


def pages_from(segments):
    """Group (start, end, text) segments into five-minute pages: [(page, text)], each line starting with its timestamp."""
    windows = {}
    for start, _end, text in segments:
        text = " ".join(str(text).split())
        if text:
            windows.setdefault(int(start // PAGE_SECONDS), []).append(f"[{clock(start)}] {text}")
    pages = []
    for number, window in enumerate(sorted(windows), 1):
        heading = f"Recording {clock(window * PAGE_SECONDS)} to {clock((window + 1) * PAGE_SECONDS)}"
        pages.append((number, heading + "\n\n" + "\n".join(windows[window])))
    return pages


def _load():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        threads = int(os.environ.get("WHISPER_THREADS", "0") or 0) or max(1, (os.cpu_count() or 2) // 2)
        _model = WhisperModel(os.environ.get("WHISPER_MODEL", "base"), device="cpu", compute_type="int8",
                              download_root=MODEL_DIR, cpu_threads=threads)
    return _model


def hint(subject="", topic=""):
    """A short lead-in that steers recognition towards the course's vocabulary (whisper's initial prompt; not part of the output)."""
    about = " ".join(part for part in (subject, topic) if part)
    return (f"NCEA {about} lesson. " if about else "NCEA lesson. ") + "Units such as kilojoules per mole, metres per second, newtons and moles per litre."


def transcribe(path, prompt=None):
    """[(page, text)] for one recording. Raises ValueError with a reason a learner can act on."""
    length = duration(path)
    if length is not None and length > MAX_SECONDS:
        raise ValueError(f"Recordings can be at most {MAX_SECONDS // 3600} hours long; this one is {clock(length)}. Split it and upload the parts.")
    with _lock:
        model = _load()
        segments, _info = model.transcribe(str(path), language=os.environ.get("WHISPER_LANGUAGE", "en") or None,
                                           vad_filter=True, beam_size=1, condition_on_previous_text=False, initial_prompt=prompt or hint())
        found = [(s.start, s.end, s.text) for s in segments]
    pages = pages_from(found)
    if not pages:
        raise ValueError("No speech was found in the recording")
    return pages
