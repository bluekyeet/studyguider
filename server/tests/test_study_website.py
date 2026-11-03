from fastapi.testclient import TestClient
from app import app


def test_study_site_is_at_root_and_advanced_tools_remain_separate():
    client = TestClient(app)
    response = client.get('/')
    assert response.status_code == 200
    assert 'StudyGuider' in response.text and '/web.js' in response.text
    # Library and Settings are part of the site itself, not a separate page.
    assert 'href="#home"' in response.text and 'href="#library"' in response.text and 'href="#settings"' in response.text
    assert 'Advanced tools' in response.text
    assert client.get('/web.css').status_code == 200
    for module in ('web-home', 'web-library', 'web-settings', 'web-rapid', 'web-exam-shared'):
        assert client.get(f'/{module}.js').status_code == 200
    assert client.get('/manage').status_code == 200
    assert client.get('/web-common.js').status_code == 200
    assert client.get('/not-a-module.js').status_code == 404
    assert client.get('/assets/katex/katex.min.js').status_code == 200
    assert client.get('/branding/favicon.png').status_code == 200
    assert client.get('/branding/wordmark.png').status_code == 200


def test_every_website_request_with_a_json_body_declares_json():
    """A string body without a Content-Type is sent as text/plain, which FastAPI rejects with a 422."""
    import re
    from pathlib import Path

    for path in sorted(Path(__file__).resolve().parents[1].glob("web*.js")):
        source = path.read_text(encoding="utf-8")
        for match in re.finditer(r"JSON\.stringify\(", source):
            line_start = source.rfind(chr(10), 0, match.start()) + 1
            context = source[max(0, line_start - 200):source.find(chr(10), match.end()) + 1]
            if "localStorage" in context or "documentAnswer" in context:
                continue
            assert "Content-Type" in context, f"{path.name}: JSON body without Content-Type near {context.strip()[:80]!r}"


def test_a_text_plain_json_body_is_rejected_which_is_why_the_header_matters():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pydantic import BaseModel

    class Body(BaseModel):
        topic_id: int

    app = FastAPI()

    @app.post("/x")
    def handler(body: Body):
        return body

    client = TestClient(app)
    assert client.post("/x", content='{"topic_id": 1}', headers={"Content-Type": "text/plain;charset=UTF-8"}).status_code == 422
    assert client.post("/x", content='{"topic_id": 1}', headers={"Content-Type": "application/json"}).status_code == 200


def test_dockerfile_copies_every_server_module():
    """The image copies modules one by one; a new module that is not listed only fails once deployed."""
    from pathlib import Path

    server = Path(__file__).resolve().parents[1]
    dockerfile = (server / "Dockerfile").read_text(encoding="utf-8")
    copied = set()
    for line in dockerfile.splitlines():
        if line.startswith("COPY ") and "--from" not in line:
            copied.update(token for token in line.split()[1:-1])
    missing = [path.name for path in server.glob("*.py") if path.name not in copied]
    assert not missing, f"Add to the Dockerfile: {missing}"
