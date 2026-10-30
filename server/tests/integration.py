"""Run only against a disposable database: this replaces its password and sessions."""
import json
import os
import http.client
import io
import urllib.error
import urllib.request

import pymupdf
from docx import Document
from pptx import Presentation

from app import connect, hasher

assert os.environ.get("DISPOSABLE_TEST_DATABASE") == "yes"
with connect() as db:
    db.execute("INSERT INTO settings VALUES ('password_hash', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (hasher.hash("test-password-only"),))
    db.execute("DELETE FROM sessions")
    db.execute("DELETE FROM settings WHERE key IN ('login_failures', 'locked_until')")


def request(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request("http://api:8000" + path, data=None if data is None else json.dumps(data).encode(), headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as response:
        return response.code, json.load(response)


assert request("GET", "/subjects")[0] == 401
connection = http.client.HTTPConnection("api", 8000)
connection.putrequest("POST", "/topics/1/resources")
connection.putheader("Content-Length", str(51 * 1024 * 1024))
connection.endheaders()
assert connection.getresponse().status == 413
connection.close()
assert request("POST", "/login", {"password": "wrong"})[0] == 401
status, result = request("POST", "/login", {"password": "test-password-only"})
assert status == 200
token = result["token"]
status, subject = request("POST", "/subjects", {"name": " Physics ", "level": 2}, token)
assert status == 201 and subject["name"] == "Physics"
base = "/subjects/" + str(subject["id"])
status, topic = request("POST", base + "/topics", {"name": "Waves"}, token)
assert status == 201
status, review = request("POST", f'/topics/{topic["id"]}/review-questions', {"question": "What is frequency?", "due_date": "2020-01-01"}, token)
assert status == 201
assert any(item["id"] == review["id"] for item in request("GET", "/review-questions/due?as_of=2020-01-02", token=token)[1])
assert request("POST", f'/review-questions/{review["id"]}/answers', {"answer": "Cycles per second", "confidence": 4}, token)[0] == 201
assert request("GET", "/review-questions/due?as_of=2020-01-02", token=token)[1] == []
assert request("PUT", "/standards/91170", {"title": "Waves", "description": "Example criteria"}, token)[0] == 200
standard_path = f'/topics/{topic["id"]}/standards/91170'
assert request("PUT", standard_path, token=token)[0] == 200
assert request("PUT", standard_path, token=token)[0] == 200
assert request("GET", f'/topics/{topic["id"]}/standards', token=token)[1][0]["number"] == 91170
assert request("DELETE", standard_path, token=token)[0] == 200
assert request("GET", f'/topics/{topic["id"]}/standards', token=token)[1] == []
boundary = "studyguider-test-boundary"
payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="sample.txt"\r\nContent-Type: text/plain\r\n\r\nhello\r\n--{boundary}--\r\n').encode()
upload = urllib.request.Request(f'http://api:8000/topics/{topic["id"]}/resources', data=payload, headers={"Authorization": "Bearer " + token, "Content-Type": "multipart/form-data; boundary=" + boundary}, method="POST")
with urllib.request.urlopen(upload) as response:
    resource = json.load(response)
    assert response.status == 201 and resource["status"] == "pending"
with urllib.request.urlopen(urllib.request.Request(f'http://api:8000/resources/{resource["id"]}/download', headers={"Authorization": "Bearer " + token})) as response:
    assert response.read() == b"hello"
assert request("GET", f'/topics/{topic["id"]}/resources', token=token)[1][0]["filename"] == "sample.txt"
assert request("POST", f'/resources/{resource["id"]}/extract', token=token)[1] == {"status": "extracted", "characters": 5, "warnings": []}
assert request("GET", f'/resources/{resource["id"]}/text', token=token)[1] == {"content": "hello"}
assert request("GET", f'/resources/{resource["id"]}/pages', token=token)[1] == [{"page": 1, "content": "hello"}]
assert request("GET", f'/topics/{topic["id"]}/resources', token=token)[1][0]["status"] == "extracted"
with pymupdf.open() as document:
    document.new_page().insert_text((72, 72), "Physics example")
    pdf = document.tobytes()
pdf_payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="sample.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode() + pdf + (f'\r\n--{boundary}--\r\n').encode()
pdf_upload = urllib.request.Request(f'http://api:8000/topics/{topic["id"]}/resources', data=pdf_payload, headers={"Authorization": "Bearer " + token, "Content-Type": "multipart/form-data; boundary=" + boundary}, method="POST")
with urllib.request.urlopen(pdf_upload) as response:
    pdf_resource = json.load(response)
assert request("POST", f'/resources/{pdf_resource["id"]}/extract', token=token)[0] == 200
assert "Physics example" in request("GET", f'/resources/{pdf_resource["id"]}/pages', token=token)[1][0]["content"]
status, results = request("GET", f'/topics/{topic["id"]}/search?q=physics', token=token)
assert status == 200 and len(results) == 1 and results[0]["resource_id"] == pdf_resource["id"] and results[0]["page"] == 1
assert request("GET", f'/topics/{topic["id"]}/search?q=nonexistent', token=token)[1] == []
document = Document()
document.add_paragraph("Chemistry example")
doc_bytes = io.BytesIO()
document.save(doc_bytes)
presentation = Presentation()
presentation.slides.add_slide(presentation.slide_layouts[1]).shapes.title.text = "Waves example"
ppt_bytes = io.BytesIO()
presentation.save(ppt_bytes)
for filename, content, expected in [("sample.docx", doc_bytes.getvalue(), "Chemistry example"), ("sample.pptx", ppt_bytes.getvalue(), "Waves example")]:
    payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n\r\n').encode() + content + (f'\r\n--{boundary}--\r\n').encode()
    upload = urllib.request.Request(f'http://api:8000/topics/{topic["id"]}/resources', data=payload, headers={"Authorization": "Bearer " + token, "Content-Type": "multipart/form-data; boundary=" + boundary}, method="POST")
    with urllib.request.urlopen(upload) as response:
        doc_resource = json.load(response)
    assert request("POST", f'/resources/{doc_resource["id"]}/extract', token=token)[0] == 200
    assert expected in request("GET", f'/resources/{doc_resource["id"]}/pages', token=token)[1][0]["content"]
    assert request("DELETE", f'/resources/{doc_resource["id"]}', token=token)[0] == 200
assert request("DELETE", base + "/topics/" + str(topic["id"]), token=token)[0] == 409
# Keep the resource and topic: this check uses a disposable database and volume.
assert request("DELETE", base, token=token)[0] == 409
topic_path = base + "/topics/" + str(topic["id"])
assert request("PUT", topic_path, {"name": "Mechanics"}, token)[1]["name"] == "Mechanics"
assert request("GET", base + "/topics", token=token)[1][0]["name"] == "Mechanics"
status, note = request("POST", f'/topics/{topic["id"]}/notes', {"content": "Review these equations"}, token)
assert status == 201
assert request("GET", f'/topics/{topic["id"]}/notes', token=token)[1][0]["content"] == "Review these equations"
assert request("DELETE", f'/resources/{resource["id"]}', token=token)[0] == 200
assert request("GET", f'/resources/{resource["id"]}/text', token=token)[0] == 404
assert request("DELETE", f'/resources/{pdf_resource["id"]}', token=token)[0] == 200
assert request("DELETE", topic_path, token=token)[0] == 409
assert request("DELETE", f'/topics/{topic["id"]}/notes/{note["id"]}', token=token)[0] == 200
assert request("DELETE", topic_path, token=token)[0] == 409
assert request("GET", "/exam-questions")[0] == 401
assert request("PUT", standard_path, token=token)[0] == 200
exam_resources = []
for filename in ("paper.txt", "schedule.txt"):
    payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n\r\noriginal\r\n--{boundary}--\r\n').encode()
    upload = urllib.request.Request(f'http://api:8000/topics/{topic["id"]}/resources', data=payload, headers={"Authorization": "Bearer " + token, "Content-Type": "multipart/form-data; boundary=" + boundary}, method="POST")
    with urllib.request.urlopen(upload) as response:
        exam_resources.append(json.load(response)["id"])
question = {"topic_id": topic["id"], "standard_number": 91170, "year": 2020, "question_number": " 1 ", "paper_resource_id": exam_resources[0], "paper_page": 1, "schedule_resource_id": exam_resources[1], "schedule_page": 2, "verified_against_originals": True}
assert request("POST", "/exam-questions", {**question, "verified_against_originals": False}, token)[0] == 422
status, created = request("POST", "/exam-questions", question, token)
assert status == 201 and created["question_number"] == "1"
assert any(item["id"] == created["id"] for item in request("GET", f'/exam-questions?topic_id={topic["id"]}', token=token)[1])
for resource_id in exam_resources:
    assert request("DELETE", f'/resources/{resource_id}', token=token)[0] == 409
    with urllib.request.urlopen(urllib.request.Request(f'http://api:8000/resources/{resource_id}/download', headers={"Authorization": "Bearer " + token})) as response:
        assert response.read() == b"original"
assert request("POST", "/logout", token=token)[0] == 200
assert request("GET", "/subjects", token=token)[0] == 401
for _ in range(5):
    assert request("POST", "/login", {"password": "wrong"})[0] == 401
assert request("POST", "/login", {"password": "test-password-only"})[0] == 429
print("Integration checks passed")
