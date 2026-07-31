#!/usr/bin/env bash
#
# Exercise the optional fresh-install web-authentication flow end to end in an
# isolated temporary root. No live Bjorn files or system command paths change.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
TEST_ROOT="$(mktemp -d)"

cleanup() {
    rm -rf -- "$TEST_ROOT"
}
trap cleanup EXIT

export BJORN_USER
BJORN_USER="$(id -un)"
export BJORN_PATH="$TEST_ROOT/Bjorn"
export HTTP_AUTH_COMMAND_PATH="$TEST_ROOT/bin/http_auth"
export LOG_DIR="$TEST_ROOT/log"
export LOG_FILE="$LOG_DIR/integration.log"

if python3 -c 'raise SystemExit(0)' >/dev/null 2>&1; then
    TEST_PYTHON="$(command -v python3)"
elif python -c 'raise SystemExit(0)' >/dev/null 2>&1; then
    TEST_PYTHON="$(command -v python)"
else
    echo "FAIL: no working Python 3 interpreter found" >&2
    exit 1
fi

mkdir -p "$BJORN_PATH/config" "$LOG_DIR" "$TEST_ROOT/python-bin"
cat >"$TEST_ROOT/python-bin/python3" <<EOF
#!/usr/bin/env bash
exec "$TEST_PYTHON" "\$@"
EOF
chmod 755 "$TEST_ROOT/python-bin/python3"
export PATH="$TEST_ROOT/python-bin:$PATH"

cp -- "$PROJECT_DIR/configure_web_auth.py" "$BJORN_PATH/"
cp -- "$PROJECT_DIR/web_auth.py" "$BJORN_PATH/"

# Sourcing is deliberately supported so this test can exercise the exact
# installer function without starting the full machine installer.
# shellcheck source=../install_bjorn.sh
source "$PROJECT_DIR/install_bjorn.sh"

printf '[1/5] Decline optional tool installation\n'
printf 'n\n' | configure_web_auth
[[ ! -e "$HTTP_AUTH_COMMAND_PATH" && \
   ! -L "$HTTP_AUTH_COMMAND_PATH" ]] || {
    echo "FAIL: declining tools still created the management command" >&2
    exit 1
}

printf '[2/5] Install the tool but defer credential setup\n'
printf 'y\nn\n' | configure_web_auth
if [[ -L "$HTTP_AUTH_COMMAND_PATH" ]]; then
    [[ "$(readlink -f -- "$HTTP_AUTH_COMMAND_PATH")" == \
       "$BJORN_PATH/configure_web_auth.py" ]] || {
        echo "FAIL: management command points to the wrong helper" >&2
        exit 1
    }
    command_layout="symlink"
elif [[ "$OSTYPE" == msys* ]] && \
     cmp -s -- "$HTTP_AUTH_COMMAND_PATH" \
         "$BJORN_PATH/configure_web_auth.py"; then
    # Git Bash copies the target when native Windows symlinks are unavailable.
    # Linux remains strict: the Raspberry Pi must create and verify a symlink.
    command_layout="git-bash-copy-emulation"
    cat >"$HTTP_AUTH_COMMAND_PATH" <<EOF
#!/usr/bin/env bash
exec "$BJORN_PATH/configure_web_auth.py" "\$@"
EOF
    chmod 755 "$HTTP_AUTH_COMMAND_PATH"
else
    echo "FAIL: management command symlink was not created" >&2
    exit 1
fi
[[ ! -e "$BJORN_PATH/config/web_auth.json" ]] || {
    echo "FAIL: deferred setup unexpectedly created credentials" >&2
    exit 1
}

printf '[3/5] Configure real test credentials through the installed command\n'
TEST_PASSWORD="$(
    "$TEST_PYTHON" -c \
        'import secrets; print("Bjorn-test-" + secrets.token_urlsafe(24))'
)"
printf '%s\n' "$TEST_PASSWORD" |
    "$HTTP_AUTH_COMMAND_PATH" set integration-user --password-stdin
[[ -f "$BJORN_PATH/config/web_auth.json" ]] || {
    echo "FAIL: credential file was not created" >&2
    exit 1
}
credential_mode="$(stat -c '%a' -- "$BJORN_PATH/config/web_auth.json")"
if [[ "$OSTYPE" == msys* ]]; then
    permission_check="ntfs-mode-$credential_mode"
elif [[ "$credential_mode" == "600" ]]; then
    permission_check="mode-600"
else
    echo "FAIL: credential file mode is $credential_mode, expected 600" >&2
    exit 1
fi
if grep -qF "$TEST_PASSWORD" "$BJORN_PATH/config/web_auth.json"; then
    echo "FAIL: plaintext password was written to the credential file" >&2
    exit 1
fi

printf '[4/5] Verify status, disable, and enable management\n'
status_output="$("$HTTP_AUTH_COMMAND_PATH" status)"
grep -qxF 'Credentials configured: yes' <<<"$status_output"
grep -qxF 'Authentication enabled: yes' <<<"$status_output"
"$HTTP_AUTH_COMMAND_PATH" disable >/dev/null
grep -qxF 'Authentication enabled: no' \
    <<<"$("$HTTP_AUTH_COMMAND_PATH" status)"
"$HTTP_AUTH_COMMAND_PATH" enable >/dev/null
grep -qxF 'Authentication enabled: yes' \
    <<<"$("$HTTP_AUTH_COMMAND_PATH" status)"

printf '[5/5] Verify the salted verifier accepts only the test password\n'
PYTHONPATH="$BJORN_PATH" python3 - \
    "$BJORN_PATH/config/web_auth.json" "$TEST_PASSWORD" <<'PY'
import sys

from web_auth import CredentialStore

credential_file, password = sys.argv[1:]
store = CredentialStore(credential_file)
if not store.verify("integration-user", password):
    raise SystemExit("FAIL: correct test credentials were rejected")
if store.verify("integration-user", password + "-wrong"):
    raise SystemExit("FAIL: incorrect test credentials were accepted")
PY

printf '\nFRESH_INSTALLER_INTEGRATION_OK\n'
printf 'Management command layout: %s\n' "$command_layout"
printf 'Credential permission check: %s\n' "$permission_check"
printf 'Isolated root removed automatically: %s\n' "$TEST_ROOT"
