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
    for module in ('web-home', 'web-library', 'web-settings'):
        assert client.get(f'/{module}.js').status_code == 200
    assert client.get('/manage').status_code == 200
    assert client.get('/web-common.js').status_code == 200
    assert client.get('/not-a-module.js').status_code == 404
    assert client.get('/assets/katex/katex.min.js').status_code == 200
    assert client.get('/branding/favicon.png').status_code == 200
    assert client.get('/branding/wordmark.png').status_code == 200
