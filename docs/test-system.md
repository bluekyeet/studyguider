# Test system

A separate StudyGuider for trying things out on the website and the phone and reporting what goes wrong. It has its own database
and uploads (Docker project `studyguider-test`, port 8100), made-up sample data and two test accounts, and never touches the real
stack. AI features use the gateway in `.env`, so lessons, marking and imports cost model calls as usual.

## Start it

```sh
scripts/test-system.sh up       # build and start; the first time it also creates the accounts and sample data
scripts/test-system.sh info     # addresses and sign-ins again
```

The sign-ins are saved in `.env.test-accounts` (not committed): `tester` is an administrator, `learner` is not. Both start
with the same invented material: NCEA Mathematics level 1 with Algebra (91027) and Graphs (91028), each a Learning topic with a
sample notes PDF, a note and an exam in six weeks; and a university paper TEST101 with two Learning outcomes and a practical
test due in a week.

- **Website:** http://localhost:8100 on this PC, or `http://<this PC's address>:8100` from a phone browser on the same Wi-Fi.
  A banner at the top says it is the test system.
- **App, on the emulator:** `scripts/test-system.sh emulator` starts the `SG_Test` Android emulator with its normal settings,
  then `scripts/test-system.sh apk` builds **StudyGuider Test** (`nz.studyguider.test`) with the server already filled in
  (`http://10.0.2.2:8100`, which is this PC as the emulator sees it) and installs it there. It is only ever installed on an
  emulator, never on a plugged-in phone, and it sits beside the real app rather than replacing it.

The server also answers on this PC's Wi-Fi address (Docker Desktop's firewall rule allows the port on a private network), so a
phone browser on the same Wi-Fi can use the website too.

## Report a problem

Signed in on the test system, a **Report a problem** button sits at the bottom right of the website, and a **Report** bubble on
the left of the app (drag it out of the way if it covers something). Write what you did, what happened and what you expected.
It also sends:

- the screen you were on, your browser or phone, screen size, theme and app version;
- the last failed requests and script errors (website) or failed requests and the app's own recent log (phone);
- a screenshot: the app takes one just before the form opens (untick it to leave it out); on the website attach one, paste
  one with Ctrl+V, or use Capture screen.

If the test app crashes, the next start offers to report the crash with its details.

Everyone sees their own reports under My reports; an administrator sees all of them under All reports and can mark each
Fixed or Won't fix with a note.

## Reading reports

```sh
scripts/test-system.sh reports    # writes test-reports/REPORTS.md and report-<id>.png (not committed)
```

Saying "look at the test reports" to Claude means: run that, read `test-reports/REPORTS.md` and the screenshots, and work
through the open ones.

## Stop or start over

```sh
scripts/test-system.sh down     # stop, keeping data and reports
scripts/test-system.sh reset    # delete the test system's data, reports and sign-ins; the next up seeds it afresh
```

Reports only exist where `STUDYGUIDER_TEST_SYSTEM=yes` (set in `compose.test.yaml`); the real server has no button and answers
404 on `/reports`. The test server speaks plain HTTP on the local network, so use only the test accounts on it.
