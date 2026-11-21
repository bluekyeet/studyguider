"""Write the test system's problem reports to /tmp/test-reports inside its api container (docs/test-system.md).

  docker compose -f compose.test.yaml exec -T api python - < scripts/export_test_reports.py
REPORTS.md lists every report, newest first, open ones flagged; each screenshot is saved as report-<id>.png beside it.
"""
import json
import os
import shutil

from app import connect_account

OUT = "/tmp/test-reports"
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT)
with connect_account() as db:
    rows = db.execute("""SELECT id, username, client, app_version, device, screen, description, context, screenshot, status, note, created_at
        FROM problem_reports ORDER BY id DESC""").fetchall()
lines = ["# Test system problem reports", "", f"{sum(r[9] == 'open' for r in rows)} open, {len(rows)} in all.", ""]
for (report_id, username, client, version, device, screen, description, context, screenshot, status, note, created) in rows:
    lines += [f"## #{report_id} [{status}] {screen or 'unknown screen'} ({client})", "",
              f"- From **{username}**, {created:%Y-%m-%d %H:%M} UTC, app {version or '?'}, {device or 'device not given'}", ""]
    lines += ["> " + line for line in description.splitlines()] + [""]
    if note:
        lines += [f"Note: {note}", ""]
    if screenshot is not None:
        with open(f"{OUT}/report-{report_id}.png", "wb") as file:
            file.write(bytes(screenshot))
        lines += [f"![screenshot](report-{report_id}.png)", ""]
    if context:
        lines += ["<details><summary>Context</summary>", "", "```json", json.dumps(context, indent=2, default=str)[:20000], "```", "", "</details>", ""]
with open(f"{OUT}/REPORTS.md", "w", encoding="utf-8") as file:
    file.write("\n".join(lines))
print(f"{len(rows)} reports exported")
