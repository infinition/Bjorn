#!/usr/bin/env python3
"""Configure Bjorn's optional web authentication without plaintext arguments."""

import argparse
import getpass
import sys
from pathlib import Path

from web_auth import CredentialError, CredentialStore


REPOSITORY_ROOT = Path(__file__).resolve().parent
CREDENTIAL_FILE = REPOSITORY_ROOT / "config" / "web_auth.json"


def set_credentials(store, username, password_stdin=False):
    """Read a password securely, save its verifier, and enable authentication."""
    if password_stdin:
        password = sys.stdin.readline()
        if password == "":
            raise CredentialError("No password was provided on standard input.")
        password = password.rstrip("\r\n")
    else:
        password = getpass.getpass("New web password: ")
        confirmation = getpass.getpass("Confirm web password: ")
        if password != confirmation:
            raise CredentialError("Passwords do not match.")
    store.save(username, password, enabled=True)
    print(f"Web authentication enabled for user '{username}'.")


def build_parser():
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Configure optional authentication for Bjorn's web interface."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_parser = subparsers.add_parser(
        "set",
        help="set credentials and enable authentication",
    )
    set_parser.add_argument("username")
    set_parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="read one password line from standard input",
    )
    subparsers.add_parser("enable", help="enable existing credentials")
    subparsers.add_parser("disable", help="disable authentication")
    subparsers.add_parser("status", help="show authentication status")
    return parser


def main(argv=None):
    """Run the requested credential-management command."""
    arguments = build_parser().parse_args(argv)
    store = CredentialStore(CREDENTIAL_FILE)

    try:
        if arguments.command == "set":
            set_credentials(
                store,
                arguments.username,
                password_stdin=arguments.password_stdin,
            )
        elif arguments.command == "enable":
            store.set_enabled(True)
            print("Web authentication enabled.")
        elif arguments.command == "disable":
            if store.is_configured():
                store.set_enabled(False)
            elif store.path.exists():
                raise CredentialError(
                    "Credential file is invalid; run 'set' to replace it."
                )
            print("Web authentication disabled.")
        elif arguments.command == "status":
            configured = store.is_configured()
            enabled = store.auth_required()
            print(f"Credentials configured: {'yes' if configured else 'no'}")
            print(f"Authentication enabled: {'yes' if enabled else 'no'}")
    except CredentialError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
