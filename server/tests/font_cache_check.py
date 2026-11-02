"""Run inside the built image as its default user; no database/model needed.

Get-Content server/tests/font_cache_check.py -Raw | docker run --rm -i studylarper-api python -
"""
import os
import subprocess
import sys

assert os.getuid() != 0, "Check must exercise the unprivileged image user"
assert os.access(os.environ["XDG_CACHE_HOME"], os.W_OK)
code = """
from diagrams import _render
image = _render('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100"><text x="10" y="50" font-size="20">Frequency / Hz</text></svg>')
assert image.startswith(b'\\x89PNG\\r\\n\\x1a\\n')
print('PNG_BYTES', len(image))
"""
result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=20)
assert "Fontconfig error" not in result.stderr, result.stderr
print(result.stdout.strip())
print("PASS: non-root text rendering with writable cache and no Fontconfig error")
