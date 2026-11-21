#!/bin/sh
# The test system (docs/test-system.md): a separate StudyGuider on port 8100 with made-up data, a test build of the phone app,
# and the problem reports testers send from both.
#   scripts/test-system.sh up        build and start it; the first time, create the test accounts and sample data
#   scripts/test-system.sh emulator  start the SG_Test Android emulator (its normal settings) if it is not running
#   scripts/test-system.sh apk       build StudyGuider Test and install it on the emulator (never on a physical phone)
#   scripts/test-system.sh reports   copy every problem report and screenshot to test-reports/
#   scripts/test-system.sh info      the addresses and sign-ins
#   scripts/test-system.sh down      stop it, keeping its data
#   scripts/test-system.sh reset     stop it and delete its data and reports (the next `up` seeds it afresh)
set -e
cd "$(dirname "$0")/.."
COMPOSE="docker compose -f compose.test.yaml"
ACCOUNTS=.env.test-accounts
SDK="${ANDROID_HOME:-$LOCALAPPDATA/Android/Sdk}"
ADB="$SDK/platform-tools/adb"
AVD=SG_Test
# The emulator reaches this PC as 10.0.2.2.
EMULATOR_SERVER=http://10.0.2.2:8100

emulator_serial() { "$ADB" devices | awk '$1 ~ /^emulator-/ && $2 == "device" { print $1; exit }'; }

lan_ip() {
  powershell.exe -NoProfile -Command "(Get-NetIPConfiguration | Where-Object { \$_.IPv4DefaultGateway -ne \$null -and \$_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1).IPv4Address.IPAddress" 2>/dev/null | tr -d '\r' \
    || hostname -I 2>/dev/null | cut -d' ' -f1
}

info() {
  ip=$(lan_ip)
  echo "Website on this PC:   http://localhost:8100"
  echo "Website on the phone: http://$ip:8100   (same Wi-Fi)"
  echo "Emulator app server:  $EMULATOR_SERVER   (already filled in by StudyGuider Test)"
  [ -f "$ACCOUNTS" ] && sed 's/^/  /' "$ACCOUNTS" || echo "  (no sign-ins saved yet: run up)"
}

case "${1:-}" in
  up)
    # The real stack's .env supplies the AI gateway settings; the test database has its own password.
    $COMPOSE --env-file .env up -d --build
    echo "Waiting for the server..."
    i=0; until curl -sf http://localhost:8100/health >/dev/null; do i=$((i+1)); [ $i -gt 60 ] && { echo "The server did not start; see: $COMPOSE logs api"; exit 1; }; sleep 2; done
    if [ ! -f "$ACCOUNTS" ]; then
      $COMPOSE exec -T -e STUDYGUIDER_SEED_OK=yes api python - < scripts/seed_test_system.py > "$ACCOUNTS.tmp"
      if [ -s "$ACCOUNTS.tmp" ]; then
        { echo "TESTER_USERNAME=tester   (administrator)"; grep TESTER_PASSWORD "$ACCOUNTS.tmp"; echo "LEARNER_USERNAME=learner"; grep LEARNER_PASSWORD "$ACCOUNTS.tmp"; } > "$ACCOUNTS"
      fi
      rm -f "$ACCOUNTS.tmp"
    fi
    info ;;
  emulator)
    if [ -n "$(emulator_serial)" ]; then echo "Emulator already running: $(emulator_serial)"; exit 0; fi
    "$SDK/emulator/emulator" -avd "$AVD" >/dev/null 2>&1 &
    "$ADB" wait-for-any-device >/dev/null; serial=""
    until [ -n "$serial" ] && [ "$("$ADB" -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '
')" = 1 ]; do sleep 3; serial=$(emulator_serial); done
    echo "Emulator $AVD running: $serial" ;;
  apk)
    # The build needs JDK 17 or 21 (README), not 25, and the SDK's location.
    jdk=$(ls -d "/c/Program Files/Eclipse Adoptium/jdk-21"* "/c/Program Files/Eclipse Adoptium/jdk-17"* 2>/dev/null | head -1)
    [ -n "$jdk" ] && export JAVA_HOME="$jdk"
    export ANDROID_HOME="$SDK"
    (cd android && ./gradlew --no-daemon -q assembleQa -PtestServer="$EMULATOR_SERVER")
    apk=android/app/build/outputs/apk/qa/app-qa.apk
    echo "Built $apk (StudyGuider Test, server $EMULATOR_SERVER)"
    serial=$(emulator_serial)
    if [ -n "$serial" ]; then "$ADB" -s "$serial" install -r "$apk" && echo "Installed on $serial"
    else echo "No emulator running: scripts/test-system.sh emulator, then apk again"; fi ;;
  reports)
    $COMPOSE exec -T api python - < scripts/export_test_reports.py
    rm -rf test-reports && $COMPOSE cp api:/tmp/test-reports ./test-reports
    echo "See test-reports/REPORTS.md" ;;
  info) info ;;
  down) $COMPOSE down ;;
  reset) $COMPOSE down --volumes && rm -f "$ACCOUNTS" && echo "Test system data deleted" ;;
  *) sed -n '2,11p' "$0"; exit 1 ;;
esac
