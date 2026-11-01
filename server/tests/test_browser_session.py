from unittest.mock import patch

from fastapi.testclient import TestClient

from app import app


def test_cookie_session_and_cross_site_protection():
    class Database:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, params=()): return self
        def fetchone(self): return (1,)

    with patch('app.connect', Database):
        client = TestClient(app)
        assert client.get('/session').status_code == 401
        client.cookies.set('studyguider_session', 'sample-test-session', domain='testserver.local', path='/')
        assert client.get('/session').status_code == 200
        assert client.post('/logout', headers={'Origin': 'https://untrusted.example'}).status_code == 403
        response = client.post('/logout')
        assert response.status_code == 200
        assert 'Max-Age=0' in response.headers['set-cookie']
        assert client.get('/session').status_code == 401
