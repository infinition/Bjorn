"""Optional HTTP Basic authentication for Bjorn's web interface."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import posixpath
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit


class CredentialError(ValueError):
    """Raised when credentials cannot be created or updated safely."""


class CredentialStore:
    """Store a salted password verifier without persisting plaintext secrets."""

    VERSION = 1
    ALGORITHM = "scrypt"
    SCRYPT_N = 2**14
    SCRYPT_R = 8
    SCRYPT_P = 1
    KEY_LENGTH = 32

    def __init__(self, path):
        self.path = Path(path)

    @staticmethod
    def validate_username(username):
        """Validate a Basic authentication username."""
        if not isinstance(username, str):
            raise CredentialError("Username must be a string.")
        if not 1 <= len(username) <= 64:
            raise CredentialError("Username must contain between 1 and 64 characters.")
        if ":" in username or any(ord(char) < 33 or ord(char) > 126 for char in username):
            raise CredentialError(
                "Username must use printable ASCII characters except ':'."
            )

    @staticmethod
    def validate_password(password):
        """Require a reasonable minimum password length."""
        if not isinstance(password, str) or len(password) < 12:
            raise CredentialError("Password must contain at least 12 characters.")

    @classmethod
    def _derive_key(cls, password, salt, parameters=None):
        parameters = parameters or {
            "n": cls.SCRYPT_N,
            "r": cls.SCRYPT_R,
            "p": cls.SCRYPT_P,
        }
        return hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=parameters["n"],
            r=parameters["r"],
            p=parameters["p"],
            dklen=cls.KEY_LENGTH,
        )

    def _write_record(self, record):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file_descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=self.path.parent,
            text=True,
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def save(self, username, password, enabled=True):
        """Create or replace credentials and enable protection by default."""
        self.validate_username(username)
        self.validate_password(password)
        salt = os.urandom(16)
        password_hash = self._derive_key(password, salt)
        record = {
            "version": self.VERSION,
            "enabled": bool(enabled),
            "username": username,
            "algorithm": self.ALGORITHM,
            "salt": base64.b64encode(salt).decode("ascii"),
            "password_hash": base64.b64encode(password_hash).decode("ascii"),
            "scrypt": {
                "n": self.SCRYPT_N,
                "r": self.SCRYPT_R,
                "p": self.SCRYPT_P,
            },
        }
        self._write_record(record)

    def _load(self):
        with self.path.open(encoding="utf-8") as handle:
            record = json.load(handle)

        if not isinstance(record, dict):
            raise CredentialError("Credential file must contain a JSON object.")
        if record.get("version") != self.VERSION:
            raise CredentialError("Unsupported credential file version.")
        if record.get("algorithm") != self.ALGORITHM:
            raise CredentialError("Unsupported password hashing algorithm.")
        self.validate_username(record.get("username"))

        parameters = record.get("scrypt", {})
        if not isinstance(parameters, dict):
            raise CredentialError("Invalid scrypt parameters.")
        try:
            n = int(parameters.get("n", 0))
            r = int(parameters.get("r", 0))
            p = int(parameters.get("p", 0))
        except (TypeError, ValueError) as exc:
            raise CredentialError("Invalid scrypt parameters.") from exc
        if n < 2**14 or n > 2**20 or n & (n - 1):
            raise CredentialError("Invalid scrypt N parameter.")
        if not 1 <= r <= 32 or not 1 <= p <= 16:
            raise CredentialError("Invalid scrypt work parameters.")

        try:
            salt = base64.b64decode(record["salt"], validate=True)
            password_hash = base64.b64decode(
                record["password_hash"],
                validate=True,
            )
        except (KeyError, binascii.Error, TypeError) as exc:
            raise CredentialError("Invalid credential encoding.") from exc

        if len(salt) < 16 or len(password_hash) != self.KEY_LENGTH:
            raise CredentialError("Invalid credential lengths.")

        record["_salt"] = salt
        record["_password_hash"] = password_hash
        record["_parameters"] = {"n": n, "r": r, "p": p}
        return record

    def auth_required(self):
        """Return whether authentication is required, failing closed on corruption."""
        if not self.path.exists():
            return False
        try:
            return bool(self._load().get("enabled", False))
        except (CredentialError, OSError, json.JSONDecodeError):
            return True

    def is_configured(self):
        """Return whether the credential file contains a valid verifier."""
        try:
            self._load()
            return True
        except (CredentialError, OSError, json.JSONDecodeError):
            return False

    def set_enabled(self, enabled):
        """Enable or disable an existing valid credential record."""
        try:
            record = self._load()
        except (OSError, json.JSONDecodeError) as exc:
            raise CredentialError("No valid credentials are configured.") from exc

        for transient_key in (
            "_salt",
            "_password_hash",
            "_parameters",
        ):
            record.pop(transient_key, None)
        record["enabled"] = bool(enabled)
        self._write_record(record)

    def verify(self, username, password):
        """Verify a username and password using constant-time comparisons."""
        try:
            record = self._load()
            candidate = self._derive_key(
                password,
                record["_salt"],
                record["_parameters"],
            )
        except (
            CredentialError,
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            return False

        username_matches = hmac.compare_digest(
            username.encode("utf-8"),
            record["username"].encode("utf-8"),
        )
        password_matches = hmac.compare_digest(
            candidate,
            record["_password_hash"],
        )
        return username_matches and password_matches

    def file_signature(self):
        """Return a signature that changes with content or access metadata."""
        try:
            stat_result = self.path.stat()
            return (
                stat_result.st_mtime_ns,
                stat_result.st_size,
                stat_result.st_mode,
                stat_result.st_uid,
                stat_result.st_gid,
            )
        except OSError:
            return None


def is_credential_file_request(request_target):
    """Recognize the private credential path after URL normalization."""
    if "://" in request_target:
        request_path = urlsplit(request_target).path
    else:
        request_path = request_target.partition("?")[0].partition("#")[0]
    request_path = unquote(request_path).replace("\\", "/")
    normalized_path = "/" + posixpath.normpath(request_path).lstrip("/")
    return normalized_path == "/config/web_auth.json"


class BasicAuthGate:
    """Parse an Authorization header and verify it against a credential store."""

    def __init__(self, credential_store, cache_seconds=30):
        self.credential_store = credential_store
        self.cache_seconds = cache_seconds
        self._cache_lock = threading.Lock()
        self._cached_header_digest = None
        self._cached_file_signature = None
        self._cache_expires = 0

    @staticmethod
    def _decode_header(authorization_header):
        """Return a username/password tuple from a valid Basic header."""
        if not authorization_header:
            return None

        scheme, separator, encoded = authorization_header.partition(" ")
        if separator != " " or scheme.lower() != "basic" or not encoded:
            return None

        try:
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return None

        username, separator, password = decoded.partition(":")
        if not separator:
            return None
        return username, password

    def is_authorized(self, authorization_header):
        """Return whether a Basic Authorization header is valid."""
        if not authorization_header:
            return False

        header_digest = hashlib.sha256(
            authorization_header.encode("utf-8")
        ).digest()
        file_signature = self.credential_store.file_signature()
        with self._cache_lock:
            cache_matches = (
                self._cached_header_digest is not None
                and hmac.compare_digest(
                    header_digest,
                    self._cached_header_digest,
                )
                and file_signature == self._cached_file_signature
                and time.monotonic() < self._cache_expires
            )
        if cache_matches:
            return True

        credentials = self._decode_header(authorization_header)
        if credentials is None:
            return False
        username, password = credentials
        if not self.credential_store.verify(username, password):
            return False

        with self._cache_lock:
            self._cached_header_digest = header_digest
            self._cached_file_signature = file_signature
            self._cache_expires = time.monotonic() + self.cache_seconds
        return True
