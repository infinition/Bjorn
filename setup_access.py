#!/usr/bin/env python3

import hmac
import json
import os
import secrets
import socket
from datetime import datetime, timezone
from http.cookies import SimpleCookie


AUTH_COOKIE_NAME = "bjorn_setup_auth"


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_boot_id():
    try:
        with open("/proc/sys/kernel/random/boot_id", "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return socket.gethostname()


def get_device_suffix():
    for interface_name in ("wlan0", "eth0"):
        address_path = os.path.join("/sys/class/net", interface_name, "address")
        try:
            with open(address_path, "r", encoding="utf-8") as handle:
                mac_address = handle.read().strip().replace(":", "").lower()
        except OSError:
            continue

        if len(mac_address) >= 6:
            return mac_address[-6:]

    hostname = "".join(char for char in socket.gethostname().lower() if char.isalnum())
    return (hostname[-6:] or "bj0rn0").rjust(6, "0")


def get_effective_setup_ap_password(configured_password):
    password = str(configured_password or "").strip()
    if password and password != "bjornsetup":
        return password
    return f"bjorn{get_device_suffix()}"


class SetupAccessManager:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.state_path = os.path.join(base_dir, "config", "setup_access.json")
        self.current_boot_id = get_boot_id()
        self.load_state()

    def _generate_state(self):
        return {
            "token": f"{secrets.randbelow(1_000_000):06d}",
            "updated_at": utc_now_iso(),
            "boot_id": self.current_boot_id,
        }

    def _normalize_state(self, state):
        token = str(state.get("token", "")).strip()
        if len(token) == 6 and token.isdigit():
            return {
                "token": token,
                "updated_at": state.get("updated_at", utc_now_iso()),
                "boot_id": str(state.get("boot_id", "")).strip(),
            }
        return self._generate_state()

    def load_state(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        try:
            with open(self.state_path, "r", encoding="utf-8") as handle:
                state = self._normalize_state(json.load(handle))
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
            state = self._generate_state()
            self.save_state(state)
            return state

        if state.get("boot_id") != self.current_boot_id:
            state = self._generate_state()
            self.save_state(state)
        return state

    def save_state(self, state):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        temp_path = f"{self.state_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
        os.replace(temp_path, self.state_path)

    def get_token(self):
        return self.load_state()["token"]

    def verify_token(self, candidate):
        value = str(candidate or "").strip()
        if not value:
            return False
        return hmac.compare_digest(value, self.get_token())

    def is_authenticated(self, handler):
        cookie_header = handler.headers.get("Cookie", "")
        if not cookie_header:
            return False

        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header)
        except Exception:
            return False

        morsel = cookie.get(AUTH_COOKIE_NAME)
        if not morsel:
            return False
        return self.verify_token(morsel.value)

    def write_auth_cookie(self, handler):
        cookie = SimpleCookie()
        cookie[AUTH_COOKIE_NAME] = self.get_token()
        cookie[AUTH_COOKIE_NAME]["path"] = "/"
        cookie[AUTH_COOKIE_NAME]["httponly"] = True
        cookie[AUTH_COOKIE_NAME]["samesite"] = "Strict"
        cookie[AUTH_COOKIE_NAME]["max-age"] = 3600
        for morsel in cookie.values():
            handler.send_header("Set-Cookie", morsel.OutputString())

    def clear_auth_cookie(self, handler):
        cookie = SimpleCookie()
        cookie[AUTH_COOKIE_NAME] = ""
        cookie[AUTH_COOKIE_NAME]["path"] = "/"
        cookie[AUTH_COOKIE_NAME]["httponly"] = True
        cookie[AUTH_COOKIE_NAME]["samesite"] = "Strict"
        cookie[AUTH_COOKIE_NAME]["max-age"] = 0
        for morsel in cookie.values():
            handler.send_header("Set-Cookie", morsel.OutputString())
