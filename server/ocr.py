"""Bounded, opt-in OCR for a single PNG image; not an extraction endpoint.

Run this in a sandbox when processing untrusted images: limits here do not
isolate native image decoders or constrain their memory use.
"""

import shutil
import struct
import subprocess
import tempfile
import threading


class OCRError(Exception):
    """OCR is unavailable, failed, or exceeded a limit."""


def extract_png(data: bytes) -> str:
    """Recognise one PNG with the trusted Tesseract binary on PATH."""
    # ponytail: PNG only, one page; add other formats through a sandboxed renderer.
    if not isinstance(data, bytes) or len(data) > 10 * 1024 * 1024 or len(data) < 24:
        raise OCRError("Invalid or oversized PNG")
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[8:16] != b"\x00\x00\x00\rIHDR":
        raise OCRError("Invalid PNG header")
    width, height = struct.unpack(">II", data[16:24])
    if not width or not height or width * height > 20_000_000:
        raise OCRError("PNG dimensions exceed OCR limits")
    binary = shutil.which("tesseract")
    if not binary:
        raise OCRError("Tesseract is unavailable")
    try:
        with tempfile.TemporaryFile() as source:
            source.write(data)
            source.seek(0)
            with subprocess.Popen([binary, "stdin", "stdout", "-l", "eng"], stdin=source,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
                timed_out = threading.Event()

                def stop():
                    timed_out.set()
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass

                timer = threading.Timer(20, stop)
                timer.start()
                try:
                    output = process.stdout.read(1_000_001)
                    if len(output) > 1_000_000:
                        process.kill()
                        raise OCRError("OCR output exceeds limit")
                    code = process.wait()
                finally:
                    timer.cancel()
                    timer.join()
                if timed_out.is_set():
                    raise OCRError("OCR timed out")
                if code:
                    raise OCRError(f"Tesseract failed (exit {code})")
    except OSError as exc:
        raise OCRError("Could not run Tesseract") from exc
    try:
        text = output.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise OCRError("Tesseract returned invalid UTF-8") from exc
    if "\x00" in text:
        raise OCRError("Tesseract returned null characters")
    return text
