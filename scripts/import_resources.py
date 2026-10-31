"""Upload a local study folder into a running StudyGuider server.

The folder is not part of this repository. This script only sends files that
already belong to the user; it never downloads or generates papers.

Usage:
    STUDYGUIDER_PASSWORD=... python scripts/import_resources.py ROOT [--base URL]
"""
import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

STANDARDS = {
    "91170": ("Physics", "Waves", "Demonstrate understanding of waves"),
    "91171": ("Physics", "Mechanics", "Demonstrate understanding of mechanics"),
    "91173": ("Physics", "Electricity and electromagnetism",
              "Demonstrate understanding of electricity and electromagnetism"),
    "91164": ("Chemistry", "Structure and bonding",
              "Demonstrate understanding of bonding, structure, properties and energy changes"),
    "91165": ("Chemistry", "Organic chemistry",
              "Demonstrate understanding of the properties of selected organic compounds"),
    "91166": ("Chemistry", "Chemical reactivity",
              "Demonstrate understanding of chemical reactivity"),
}
CATEGORIES = {"exam_paper", "exam_answers", "slides", "extra"}


def request(base, path, token=None, data=None, method=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    payload = None if data is None else json.dumps(data).encode()
    req = urllib.request.Request(base + path, data=payload, headers=headers,
                                 method=method or ("POST" if data is not None else "GET"))
    with urllib.request.urlopen(req, timeout=120) as response:
        body = response.read()
    return json.loads(body) if body else None


def login(base, password):
    return request(base, "/login", data={"password": password})["token"]


def multipart(path, category):
    boundary = "----studyguider" + uuid.uuid4().hex
    name = path.name.replace('"', "_")
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    body = bytearray()
    body += f'--{boundary}\r\nContent-Disposition: form-data; name="category"\r\n\r\n{category}\r\n'.encode()
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
             f'Content-Type: {mime}\r\n\r\n').encode()
    body += path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()
    return bytes(body), "multipart/form-data; boundary=" + boundary


def upload(base, token, topic_id, path, category):
    body, content_type = multipart(path, category)
    req = urllib.request.Request(base + f"/topics/{topic_id}/resources", data=body, method="POST",
                                 headers={"Authorization": "Bearer " + token,
                                          "Content-Type": content_type})
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        return {"filename": path.name, "error": exc.read().decode(errors="replace")[:500]}


def classify(path):
    name = path.name.lower()
    if "-ass-" in name or "answer" in name or "schedule" in name:
        return "exam_answers"
    if "-exm-" in name or "past exams" in str(path).lower():
        return "exam_paper"
    if path.suffix.lower() in {".pptx", ".ppt"}:
        return "slides"
    return "extra"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--extract", action="store_true", help="Extract every upload immediately")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    password = os.environ.get("STUDYGUIDER_PASSWORD")
    if not password:
        sys.exit("Set STUDYGUIDER_PASSWORD")
    token = login(args.base, password)
    subjects = {s["name"]: s["id"] for s in request(args.base, "/subjects", token)}
    for subject in {value[0] for value in STANDARDS.values()}:
        if subject not in subjects:
            subjects[subject] = request(args.base, "/subjects", token,
                                        {"name": subject, "level": 2})["id"]

    topic_ids = {}
    for number, (subject, topic, title) in STANDARDS.items():
        request(args.base, f"/standards/{number}", token, {"title": title, "description": ""},
                method="PUT")
        existing = request(args.base, f"/subjects/{subjects[subject]}/topics", token)
        match = next((item for item in existing if item["name"] == topic), None)
        topic_id = match["id"] if match else request(
            args.base, f"/subjects/{subjects[subject]}/topics", token, {"name": topic})["id"]
        request(args.base, f"/topics/{topic_id}/standards/{number}", token, method="PUT")
        topic_ids[number] = topic_id

    jobs = []
    for number, (subject, topic, _) in STANDARDS.items():
        folder = args.root / subject / "Externals"
        matches = [item for item in folder.glob(f"{number}*") if item.is_dir()]
        if not matches:
            print(f"Missing folder for {number}")
            continue
        for path in sorted(matches[0].rglob("*")):
            if path.is_file() and path.suffix.lower() in {
                    ".pdf", ".docx", ".pptx", ".ppt", ".xlsx", ".csv", ".txt", ".md", ".html",
                    ".png", ".jpg", ".jpeg"}:
                jobs.append((topic_ids[number], path, classify(path)))

    print(f"Uploading {len(jobs)} files")
    uploaded = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(upload, args.base, token, topic_id, path, category)
                   for topic_id, path, category in jobs]
        for index, future in enumerate(futures, 1):
            result = future.result()
            if "error" in result:
                print(f"[{index}/{len(jobs)}] FAILED {result.get('filename')}: {result['error']}")
            else:
                uploaded.append(result)
                if index % 25 == 0:
                    print(f"[{index}/{len(jobs)}] uploaded")

    duplicates = sum(1 for item in uploaded if item.get("duplicate"))
    print(f"Uploaded {len(uploaded)} resources ({duplicates} duplicates)")

    if args.extract:
        print("Extracting")
        def extract(item):
            req = urllib.request.Request(
                args.base + f"/resources/{item['id']}/extract",
                headers={"Authorization": "Bearer " + token}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=900) as response:
                    return item["filename"], "ok", json.loads(response.read())
            except urllib.error.HTTPError as exc:
                return item["filename"], "failed", exc.read().decode(errors="replace")[:300]
            except Exception as exc:  # network or timeout
                return item["filename"], "error", str(exc)[:300]

        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for index, (name, status, detail) in enumerate(pool.map(extract, uploaded), 1):
                if status != "ok":
                    print(f"EXTRACT {status}: {name}: {detail}")
                elif index % 25 == 0:
                    print(f"[{index}/{len(uploaded)}] extracted")
    print("Done")


if __name__ == "__main__":
    main()
