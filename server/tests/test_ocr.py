import io
import struct
import subprocess

import pytest

import ocr


PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + struct.pack(">II", 100, 100)


def test_validation_and_unavailable(monkeypatch):
    with pytest.raises(ocr.OCRError, match="PNG"):
        ocr.extract_png(b"bad")
    with pytest.raises(ocr.OCRError, match="dimensions"):
        ocr.extract_png(PNG[:16] + struct.pack(">II", 100000, 100000))
    monkeypatch.setattr(ocr.shutil, "which", lambda _: None)
    with pytest.raises(ocr.OCRError, match="unavailable"):
        ocr.extract_png(PNG)


def test_bounded_output_and_failure(monkeypatch):
    monkeypatch.setattr(ocr.shutil, "which", lambda _: "trusted-tesseract")
    class Process:
        output = b"hello"
        code = 0
        def __init__(self, args, **kwargs):
            assert args == ["trusted-tesseract", "stdin", "stdout", "-l", "eng"]
            assert kwargs["stdin"].read() == PNG
            self.stdout = io.BytesIO(self.output)
        def __enter__(self): return self
        def __exit__(self, *args): self.stdout.close()
        def wait(self): return self.code
        def kill(self): pass

    monkeypatch.setattr(subprocess, "Popen", Process)
    assert ocr.extract_png(PNG) == "hello"
    Process.output = b"x" * 1_000_001
    with pytest.raises(ocr.OCRError, match="output exceeds"):
        ocr.extract_png(PNG)
    Process.output = b""
    Process.code = 3
    with pytest.raises(ocr.OCRError, match="exit 3"):
        ocr.extract_png(PNG)
