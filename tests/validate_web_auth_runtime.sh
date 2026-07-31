#!/usr/bin/env bash
#
# Validate Bjorn web authentication against a live local service.

set -Eeuo pipefail

TARGET_DIR="/home/bjorn/Bjorn"
SERVICE_NAME="bjorn.service"
COMMAND_PATH="/usr/local/sbin/http_auth"
WEB_PORT=8000
TEST_USERNAME="bjorn-validation"
TEMP_DIR=""
CREDENTIAL_BACKUP=""
CREDENTIAL_FILE=""
RESTORE_PENDING=0

usage() {
    cat <<'EOF'
Usage:
  sudo ./tests/validate_web_auth_runtime.sh [options]

Options:
  --target PATH       Live Bjorn directory (default: /home/bjorn/Bjorn)
  --service UNIT      Systemd service (default: bjorn.service)
  --command PATH      Management command (default: /usr/local/sbin/http_auth)
  --port PORT         Web port (default: 8000)
  -h, --help          Show this help

The test temporarily replaces the credential verifier, exercises set, status,
disable, and enable, checks authenticated and unauthenticated HTTP requests,
performs an incomplete-POST regression test and restores the original verifier
on success, failure, or interruption. No plaintext password is printed or
stored in the Bjorn configuration.
EOF
}

fail() {
    echo "WEB_AUTH_RUNTIME_FAIL: $*" >&2
    exit 1
}

require_value() {
    local option="$1"
    local value="${2:-}"
    [[ -n "$value" ]] || fail "$option requires a value"
}

while (($#)); do
    case "$1" in
        --target)
            require_value "$1" "${2:-}"
            TARGET_DIR="$2"
            shift 2
            ;;
        --service)
            require_value "$1" "${2:-}"
            SERVICE_NAME="$2"
            shift 2
            ;;
        --command)
            require_value "$1" "${2:-}"
            COMMAND_PATH="$2"
            shift 2
            ;;
        --port)
            require_value "$1" "${2:-}"
            WEB_PORT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "unknown option: $1"
            ;;
    esac
done

[[ $EUID -eq 0 ]] || fail "run this runtime test with sudo"
[[ "$WEB_PORT" =~ ^[1-9][0-9]*$ ]] || \
    fail "--port requires a positive integer"

TARGET_DIR="$(readlink -f -- "$TARGET_DIR")"
COMMAND_PATH="$(readlink -f -- "$COMMAND_PATH")"
CREDENTIAL_FILE="$TARGET_DIR/config/web_auth.json"

[[ -x "$COMMAND_PATH" ]] || \
    fail "management command is not executable: $COMMAND_PATH"
[[ -f "$TARGET_DIR/web_auth.py" ]] || \
    fail "web_auth.py not found in target: $TARGET_DIR"
[[ -f "$CREDENTIAL_FILE" ]] || \
    fail "credential verifier not found: $CREDENTIAL_FILE"
systemctl is-active --quiet "$SERVICE_NAME" || \
    fail "service is not active: $SERVICE_NAME"

SERVICE_PID="$(systemctl show "$SERVICE_NAME" -p MainPID --value)"
[[ "$SERVICE_PID" =~ ^[1-9][0-9]*$ ]] || \
    fail "invalid service PID: $SERVICE_PID"
INITIAL_HTTP="$(
    curl --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
)"
[[ "$INITIAL_HTTP" == "200" || "$INITIAL_HTTP" == "401" ]] || \
    fail "initial web response is HTTP $INITIAL_HTTP"

TEMP_DIR="$(mktemp -d)"
CREDENTIAL_BACKUP="$TEMP_DIR/web_auth.json.original"
cp -a -- "$CREDENTIAL_FILE" "$CREDENTIAL_BACKUP"
RESTORE_PENDING=1

restore_credentials() {
    if ((RESTORE_PENDING == 1)); then
        rm -f -- "$CREDENTIAL_FILE"
        cp -a -- "$CREDENTIAL_BACKUP" "$CREDENTIAL_FILE"
        RESTORE_PENDING=0
    fi
}

cleanup() {
    restore_credentials
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        rm -f -- \
            "$TEMP_DIR/web_auth.json.original" \
            "$TEMP_DIR/curl-valid.conf" \
            "$TEMP_DIR/curl-wrong.conf" \
            "$TEMP_DIR/journal.log"
        rmdir -- "$TEMP_DIR" 2>/dev/null || true
    fi
}

trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

TEST_STARTED_AT="$(date '+%Y-%m-%d %H:%M:%S')"
TEST_PASSWORD="$(
    python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
)"

printf '%s\n' "$TEST_PASSWORD" |
    "$COMMAND_PATH" set "$TEST_USERNAME" --password-stdin >/dev/null

STATUS_OUTPUT="$("$COMMAND_PATH" status)"
grep -q 'Credentials configured: yes' <<<"$STATUS_OUTPUT" || \
    fail "status did not report configured credentials"
grep -q 'Authentication enabled: yes' <<<"$STATUS_OUTPUT" || \
    fail "status did not report enabled authentication"
echo "COMMAND_SET_STATUS_OK"

VALID_CURL_CONFIG="$TEMP_DIR/curl-valid.conf"
WRONG_CURL_CONFIG="$TEMP_DIR/curl-wrong.conf"
printf 'user = "%s:%s"\n' \
    "$TEST_USERNAME" "$TEST_PASSWORD" >"$VALID_CURL_CONFIG"
printf 'user = "%s:%s"\n' \
    "$TEST_USERNAME" "definitely-wrong-password" >"$WRONG_CURL_CONFIG"
chmod 600 "$VALID_CURL_CONFIG" "$WRONG_CURL_CONFIG"

UNAUTHENTICATED_HTTP="$(
    curl --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
)"
VALID_HTTP="$(
    curl --config "$VALID_CURL_CONFIG" \
        --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
)"
WRONG_HTTP="$(
    curl --config "$WRONG_CURL_CONFIG" \
        --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
)"
PRIVATE_HTTP="$(
    curl --config "$VALID_CURL_CONFIG" \
        --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 2 \
        "http://127.0.0.1:$WEB_PORT/config/web_auth.json" || true
)"

[[ "$UNAUTHENTICATED_HTTP" == "401" ]] || \
    fail "headerless request returned HTTP $UNAUTHENTICATED_HTTP"
[[ "$VALID_HTTP" == "200" ]] || \
    fail "valid credentials returned HTTP $VALID_HTTP"
[[ "$WRONG_HTTP" == "401" ]] || \
    fail "wrong credentials returned HTTP $WRONG_HTTP"
[[ "$PRIVATE_HTTP" == "404" ]] || \
    fail "private credential path returned HTTP $PRIVATE_HTTP"
echo "HTTP_AUTHORIZATION_OK"

"$COMMAND_PATH" disable >/dev/null
DISABLED_STATUS="$("$COMMAND_PATH" status)"
grep -q 'Authentication enabled: no' <<<"$DISABLED_STATUS" || \
    fail "disable command did not update status"
DISABLED_HTTP="$(
    curl --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
)"
[[ "$DISABLED_HTTP" == "200" ]] || \
    fail "disabled authentication returned HTTP $DISABLED_HTTP"

"$COMMAND_PATH" enable >/dev/null
ENABLED_STATUS="$("$COMMAND_PATH" status)"
grep -q 'Authentication enabled: yes' <<<"$ENABLED_STATUS" || \
    fail "enable command did not update status"
ENABLED_HTTP="$(
    curl --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
)"
[[ "$ENABLED_HTTP" == "401" ]] || \
    fail "re-enabled authentication returned HTTP $ENABLED_HTTP"
echo "COMMAND_DISABLE_ENABLE_OK"

for _ in {1..30}; do
    STRESS_HTTP="$(
        curl --silent --output /dev/null --write-out '%{http_code}' \
            --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
    )"
    [[ "$STRESS_HTTP" == "401" ]] || \
        fail "challenge stress request returned HTTP $STRESS_HTTP"
done
echo "HEADERLESS_CHALLENGE_STRESS_OK requests=30"

python3 - "$WEB_PORT" <<'PY'
import socket
import sys
import time

port = int(sys.argv[1])
headers = (
    "POST /save_config HTTP/1.1\r\n"
    f"Host: 127.0.0.1:{port}\r\n"
    "Content-Type: application/json\r\n"
    "Content-Length: 1048576\r\n"
    "Connection: keep-alive\r\n"
    "\r\n"
).encode("ascii")

started = time.monotonic()
with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
    client.settimeout(2)
    client.sendall(headers)
    response = client.recv(4096)
elapsed = time.monotonic() - started

if b" 401 " not in response:
    raise SystemExit("incomplete POST did not receive HTTP 401")
if b"Connection: close\r\n" not in response:
    raise SystemExit("incomplete POST response did not close the connection")
if elapsed >= 2:
    raise SystemExit(f"incomplete POST response took {elapsed:.3f}s")
print(f"INCOMPLETE_POST_OK elapsed={elapsed:.3f}s")
PY

[[ "$(systemctl is-active "$SERVICE_NAME" || true)" == "active" ]] || \
    fail "service stopped during runtime validation"
CURRENT_PID="$(systemctl show "$SERVICE_NAME" -p MainPID --value)"
[[ "$CURRENT_PID" == "$SERVICE_PID" ]] || \
    fail "service PID changed from $SERVICE_PID to $CURRENT_PID"

JOURNAL_FILE="$TEMP_DIR/journal.log"
journalctl "_PID=$SERVICE_PID" \
    --since "$TEST_STARTED_AT" \
    --no-pager \
    -o cat >"$JOURNAL_FILE"
ERROR_PATTERN='Fatal Python error|Traceback|Exception in thread|Unexpected web server thread error|can.t start new thread'
if grep -qiE "$ERROR_PATTERN" "$JOURNAL_FILE"; then
    grep -iE "$ERROR_PATTERN" "$JOURNAL_FILE" >&2 || true
    fail "web or thread errors found in journal"
fi
INVALID_WARNING_COUNT="$(
    grep -c 'Rejected invalid web credentials' "$JOURNAL_FILE" || true
)"
[[ "$INVALID_WARNING_COUNT" =~ ^[1-9][0-9]*$ ]] || \
    fail "invalid credentials were not recorded in the journal"
echo "JOURNAL_AUDIT_OK invalid_warnings=$INVALID_WARNING_COUNT"

restore_credentials
RESTORED_HTTP="$(
    curl --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 2 "http://127.0.0.1:$WEB_PORT/" || true
)"
[[ "$RESTORED_HTTP" == "$INITIAL_HTTP" ]] || \
    fail "restored credentials returned HTTP $RESTORED_HTTP, expected $INITIAL_HTTP"

echo "CREDENTIAL_RESTORE_OK HTTP=$RESTORED_HTTP"
printf 'WEB_AUTH_RUNTIME_OK PID=%s INITIAL_HTTP=%s\n' \
    "$SERVICE_PID" "$INITIAL_HTTP"
