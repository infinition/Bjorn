#!/usr/bin/env bash
# Validate that the combined stability and web-authentication state survives a
# real reboot. Preparation stores hashes and identifiers only, never passwords.

set -Eeuo pipefail

TARGET_DIR="/home/bjorn/Bjorn"
SERVICE_NAME="bjorn.service"
WEB_PORT=8000
TIMEOUT=120
THREAD_LIMIT=64
STATE_FILE="/var/tmp/bjorn-stability-web-auth-reboot.state"
MODE=""

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    GREEN=$'\033[0;32m'
    RED=$'\033[0;31m'
    BLUE=$'\033[0;34m'
    NC=$'\033[0m'
else
    GREEN=""
    RED=""
    BLUE=""
    NC=""
fi

usage() {
    cat <<'EOF'
Usage:
  sudo ./tests/run_reboot_persistence_validation.sh --prepare [options]
  sudo ./tests/run_reboot_persistence_validation.sh --verify  [options]

Options:
  --target PATH          Bjorn installation (default: /home/bjorn/Bjorn)
  --service NAME         systemd unit (default: bjorn.service)
  --port PORT            web port (default: 8000)
  --timeout SECONDS      post-reboot scan timeout (default: 120)
  --thread-limit COUNT   maximum accepted thread count (default: 64)
  --state-file PATH      persistent hand-off file under /var/tmp
EOF
}

fail() {
    printf '%s[FAIL]%s %s\n' "$RED" "$NC" "$*" >&2
    exit 1
}

success() {
    printf '%s[OK]%s %s\n' "$GREEN" "$NC" "$*"
}

http_status() {
    curl --silent --output /dev/null --write-out '%{http_code}' \
        --max-time 2 "http://127.0.0.1:${WEB_PORT}/" || true
}

credential_hash() {
    local credential_file="$TARGET_DIR/config/web_auth.json"
    if [[ -f "$credential_file" ]]; then
        sha256sum -- "$credential_file" | awk '{print $1}'
    else
        printf 'absent\n'
    fi
}

command_target() {
    if [[ -L /usr/local/sbin/http_auth ]]; then
        readlink -f -- /usr/local/sbin/http_auth
    elif [[ -e /usr/local/sbin/http_auth ]]; then
        printf 'regular-file\n'
    else
        printf 'absent\n'
    fi
}

while (($#)); do
    case "$1" in
        --prepare|--verify)
            [[ -z "$MODE" ]] || fail "choose only one mode"
            MODE="${1#--}"
            shift
            ;;
        --target)
            TARGET_DIR="$2"
            shift 2
            ;;
        --service)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --port)
            WEB_PORT="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --thread-limit)
            THREAD_LIMIT="$2"
            shift 2
            ;;
        --state-file)
            STATE_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "unknown argument: $1"
            ;;
    esac
done

[[ $EUID -eq 0 ]] || fail "run this validation with sudo"
[[ "$MODE" == "prepare" || "$MODE" == "verify" ]] || {
    usage
    exit 2
}
[[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]] || fail "timeout must be positive"
[[ "$THREAD_LIMIT" =~ ^[1-9][0-9]*$ ]] || \
    fail "thread limit must be positive"

prepare() {
    local current_http
    local current_boot
    local current_hash
    local current_command

    systemctl is-active --quiet "$SERVICE_NAME" || \
        fail "$SERVICE_NAME is not active"
    current_http="$(http_status)"
    [[ "$current_http" == "200" || "$current_http" == "401" ]] || \
        fail "web interface returned HTTP $current_http"
    current_boot="$(cat /proc/sys/kernel/random/boot_id)"
    current_hash="$(credential_hash)"
    current_command="$(command_target)"

    umask 077
    {
        printf 'OLD_BOOT_ID=%q\n' "$current_boot"
        printf 'EXPECTED_HTTP=%q\n' "$current_http"
        printf 'CREDENTIAL_HASH=%q\n' "$current_hash"
        printf 'COMMAND_TARGET=%q\n' "$current_command"
        printf 'TARGET_DIR=%q\n' "$TARGET_DIR"
        printf 'SERVICE_NAME=%q\n' "$SERVICE_NAME"
        printf 'WEB_PORT=%q\n' "$WEB_PORT"
    } >"$STATE_FILE"
    chmod 600 "$STATE_FILE"

    printf '\n%sBjorn reboot-persistence validation%s\n' "$BLUE" "$NC"
    success "Pre-reboot service and HTTP state captured"
    printf '     Boot ID: %s\n' "$current_boot"
    printf '     HTTP: %s, credentials: %s, command: %s\n' \
        "$current_http" "$current_hash" "$current_command"
    printf '\nMachine marker: REBOOT_PERSISTENCE_PREPARED\n'
    printf 'Next: sudo reboot\n'
}

verify() {
    local old_boot_id
    local expected_http
    local expected_hash
    local expected_command
    local new_boot_id
    local pid=""
    local initial_pid=""
    local current_http="000"
    local completed_scans=0
    local threads=0
    local max_threads=0
    local elapsed=0
    local journal_output

    [[ -f "$STATE_FILE" ]] || fail "preparation state is missing: $STATE_FILE"
    # The state is root-owned mode 0600 and contains shell-escaped scalar data.
    # shellcheck disable=SC1090
    source "$STATE_FILE"
    old_boot_id="$OLD_BOOT_ID"
    expected_http="$EXPECTED_HTTP"
    expected_hash="$CREDENTIAL_HASH"
    expected_command="$COMMAND_TARGET"
    new_boot_id="$(cat /proc/sys/kernel/random/boot_id)"

    [[ "$new_boot_id" != "$old_boot_id" ]] || \
        fail "boot ID did not change; a real reboot was not observed"

    printf '\n%sBjorn reboot-persistence validation%s\n' "$BLUE" "$NC"
    printf 'Waiting for service, HTTP, and one completed scan...\n'

    while ((elapsed <= TIMEOUT)); do
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            pid="$(systemctl show "$SERVICE_NAME" -p MainPID --value)"
            if [[ "$pid" =~ ^[1-9][0-9]*$ ]]; then
                [[ -n "$initial_pid" ]] || initial_pid="$pid"
                [[ "$pid" == "$initial_pid" ]] || \
                    fail "service PID changed during verification"
                current_http="$(http_status)"
                threads="$(ps -o nlwp= -p "$pid" | tr -d ' ' || true)"
                [[ "$threads" =~ ^[0-9]+$ ]] || threads=0
                ((threads > max_threads)) && max_threads="$threads"
                completed_scans="$({
                    journalctl -b _PID="$pid" --no-pager -o cat 2>/dev/null || true
                } | grep -cF 'Scan results cleaned up' || true)"
            fi
        fi

        printf '\rPost-reboot: %3d/%ds | HTTP %s | Threads %d | Scans %d' \
            "$elapsed" "$TIMEOUT" "$current_http" "$threads" \
            "$completed_scans"

        if [[ "$current_http" == "$expected_http" ]] && \
           ((completed_scans >= 1)); then
            break
        fi
        sleep 5
        ((elapsed += 5))
    done
    printf '\n'

    systemctl is-active --quiet "$SERVICE_NAME" || \
        fail "$SERVICE_NAME is not active after reboot"
    [[ "$current_http" == "$expected_http" ]] || \
        fail "HTTP changed from $expected_http to $current_http"
    ((completed_scans >= 1)) || fail "no completed scan after reboot"
    ((max_threads <= THREAD_LIMIT)) || \
        fail "thread peak $max_threads exceeds limit $THREAD_LIMIT"
    [[ "$(credential_hash)" == "$expected_hash" ]] || \
        fail "credential file changed across reboot"
    [[ "$(command_target)" == "$expected_command" ]] || \
        fail "http_auth command target changed across reboot"

    journal_output="$(journalctl -b _PID="$pid" --no-pager -o cat || true)"
    if grep -qiE \
        'cannot schedule new|can.t start new thread|pthread_create|fatal python error|error in scan|traceback' \
        <<<"$journal_output"; then
        grep -iE \
            'cannot schedule new|can.t start new thread|pthread_create|fatal python error|error in scan|traceback' \
            <<<"$journal_output" >&2
        fail "runtime errors found in the post-reboot journal"
    fi

    success "A real reboot was observed"
    success "Service, HTTP authentication, credentials, and command persisted"
    success "A scan completed without runtime errors"
    printf '     PID %s, HTTP %s, peak %d threads, %d completed scan(s)\n' \
        "$pid" "$current_http" "$max_threads" "$completed_scans"
    printf '\n%s[PASS]%s Reboot persistence validation completed successfully.\n' \
        "$GREEN" "$NC"
    printf 'Machine marker: REBOOT_PERSISTENCE_VALIDATION_OK\n'
    rm -f -- "$STATE_FILE"
}

case "$MODE" in
    prepare) prepare ;;
    verify) verify ;;
esac
